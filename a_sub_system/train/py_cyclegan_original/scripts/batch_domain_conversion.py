"""
批次 CycleGAN 域轉換腳本
=======================

自動針對 MongoDB 中符合 Domain B 查詢條件的所有分析任務，將 Step 2
(Mafaulda) 特徵批次轉換為 Step 6 (CPC) 並寫回資料庫。
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import torch
from pymongo import MongoClient
from pymongo.collection import Collection

# 確保可以匯入專案模組
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models import CycleGANModule
from utils import (  # noqa: E402
    get_data_config,
    get_inference_config,
    get_mongodb_config,
    setup_logger,
)

# 預設設定，可透過環境變數覆寫
DEFAULT_CHECKPOINT = Path(
    os.getenv("BATCH_CONVERSION_CHECKPOINT", "checkpoints/best.ckpt")
)
DEFAULT_INPUT_STEP = int(os.getenv("BATCH_CONVERSION_INPUT_STEP", "2"))
DEFAULT_OUTPUT_STEP = int(os.getenv("BATCH_CONVERSION_OUTPUT_STEP", "6"))
DEFAULT_DEVICE = os.getenv("BATCH_CONVERSION_DEVICE", get_inference_config()["device"])

logger = setup_logger("batch_conversion")


def build_analysis_container() -> Dict[str, Any]:
    """建立 analyze_features 預設容器"""
    return {
        "active_analysis_id": None,
        "latest_analysis_id": None,
        "latest_summary_index": None,
        "total_runs": 0,
        "last_requested_at": None,
        "last_started_at": None,
        "last_completed_at": None,
        "runs": [],
    }


def ensure_analysis_container(collection: Collection, record: Dict[str, Any]) -> Dict[str, Any]:
    """確保資料庫紀錄採用新的 analyze_features 結構"""
    analyze_uuid = record.get("AnalyzeUUID")
    analyze_features = record.get("analyze_features")

    container = build_analysis_container()

    if isinstance(analyze_features, dict) and "runs" in analyze_features:
        container.update({k: v for k, v in analyze_features.items() if k != "metadata"})
        legacy_metadata = analyze_features.get("metadata")
        if isinstance(legacy_metadata, dict):
            container["total_runs"] = legacy_metadata.get("total_runs", container["total_runs"])
            container["last_requested_at"] = legacy_metadata.get("last_requested_at")
            container["last_started_at"] = legacy_metadata.get("last_started_at")
            container["last_completed_at"] = legacy_metadata.get("last_completed_at")
    elif isinstance(analyze_features, list) and analyze_features:
        legacy_id = f"legacy-{analyze_uuid}"
        legacy_run = {
            "analysis_id": legacy_id,
            "run_index": 1,
            "analysis_summary": record.get("analysis_summary", {}),
            "analysis_context": {"imported_from": "legacy"},
            "steps": analyze_features,
            "requested_at": record.get("created_at"),
            "started_at": record.get("processing_started_at") or record.get("created_at"),
            "completed_at": record.get("updated_at"),
            "error_message": record.get("error_message"),
        }
        container["runs"] = [legacy_run]
        container["latest_analysis_id"] = legacy_id
        container["latest_summary_index"] = 1
        container["total_runs"] = 1
        container["last_requested_at"] = legacy_run["requested_at"]
        container["last_started_at"] = legacy_run["started_at"]
        container["last_completed_at"] = legacy_run["completed_at"]

    update_doc: Dict[str, Any] = {"$set": {"analyze_features": container}}
    if record.get("analysis_summary") is not None:
        update_doc.setdefault("$unset", {})["analysis_summary"] = ""

    collection.update_one({"AnalyzeUUID": analyze_uuid}, update_doc)
    record["analyze_features"] = container
    return container


def select_analysis_run(record: Dict[str, Any], preferred_run_id: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """根據設定選擇要使用的分析 run"""
    analyze_features = record.get("analyze_features", {})
    runs = analyze_features.get("runs", []) if isinstance(analyze_features, dict) else []

    if not runs:
        return None, None

    run_doc = None
    if preferred_run_id:
        run_doc = next((run for run in runs if run.get("analysis_id") == preferred_run_id), None)
        if not run_doc:
            logger.warning("記錄 %s 找不到指定的 run %s，將改用最新 run", record.get("AnalyzeUUID"), preferred_run_id)

    if run_doc is None:
        latest_index = record.get("analyze_features", {}).get("latest_summary_index")
        if latest_index:
            run_doc = next((run for run in runs if run.get("run_index") == latest_index), None)

    if run_doc is None:
        run_doc = runs[-1]

    return run_doc, run_doc.get("analysis_id")


def extract_step_from_run(run_doc: Optional[Dict[str, Any]], step: int) -> Optional[Dict[str, Any]]:
    """從指定 run 內取得步驟資料"""
    if not run_doc:
        return None

    for step_doc in run_doc.get("steps", []):
        if step_doc.get("features_step") == step and step_doc.get("features_state") == "completed":
            return step_doc
    return None


def has_completed_step(container: Dict[str, Any], step: int) -> bool:
    """檢查紀錄中是否已存在目標步驟"""
    runs = container.get("runs", []) if isinstance(container, dict) else []
    for run in runs:
        if extract_step_from_run(run, step):
            return True
    return False


def remove_previous_conversion_runs(collection: Collection, analyze_uuid: str, output_step: int) -> None:
    """移除舊的轉換 run（僅限本腳本寫入者）"""
    collection.update_one(
        {"AnalyzeUUID": analyze_uuid},
        {
            "$pull": {
                "analyze_features.runs": {
                    "analysis_context.source": "batch_domain_conversion",
                    "analysis_context.output_step": output_step,
                }
            }
        },
    )


def append_conversion_run(
    collection: Collection,
    analyze_uuid: str,
    step_id: int,
    converted: List[List[List[float]]],
    metadata: Dict[str, Any],
    context: Dict[str, Any],
    overwrite: bool,
) -> None:
    """以新的 run 方式寫入轉換結果"""
    if overwrite:
        remove_previous_conversion_runs(collection, analyze_uuid, step_id)

    converted_at = metadata["converted_at"]
    analysis_id = context.get("analysis_id") or f"domain_conversion_{uuid4().hex[:8]}"

    current_doc = collection.find_one(
        {"AnalyzeUUID": analyze_uuid},
        {"analyze_features.runs.run_index": 1, "analyze_features.runs": 1}
    )
    existing_runs = current_doc.get("analyze_features", {}).get("runs", []) if current_doc else []
    existing_indices = [run.get("run_index") for run in existing_runs if run.get("run_index")]
    if existing_indices:
        run_index = max(existing_indices) + 1
    else:
        run_index = len(existing_runs) + 1

    step_doc = {
        "features_step": step_id,
        "features_state": "completed",
        "features_name": f"Domain Conversion Step {step_id}",
        "features_data": converted,
        "processor_metadata": metadata,
        "error_message": None,
        "started_at": converted_at,
        "completed_at": converted_at,
    }

    run_doc = {
        "analysis_id": analysis_id,
        "run_index": run_index,
        "analysis_summary": {},
        "analysis_context": context,
        "steps": [step_doc],
        "requested_at": converted_at,
        "started_at": converted_at,
        "completed_at": converted_at,
        "error_message": None,
    }

    update_doc = {
        "$push": {"analyze_features.runs": run_doc},
        "$set": {
            "analyze_features.latest_analysis_id": analysis_id,
            "analyze_features.active_analysis_id": None,
            "analysis_status": "completed",
            "current_step": step_id,
            "updated_at": converted_at,
            "analyze_features.total_runs": run_index,
            "analyze_features.last_requested_at": converted_at,
            "analyze_features.last_started_at": converted_at,
            "analyze_features.last_completed_at": converted_at,
        },
    }

    collection.update_one({"AnalyzeUUID": analyze_uuid}, update_doc)


def load_model(checkpoint: Path, device_name: str) -> Tuple[CycleGANModule, torch.device, Dict[str, np.ndarray]]:
    """載入 CycleGAN 檢查點並返回模型、裝置與正規化參數。"""
    if device_name == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA 不可用，自動改用 CPU")
        device_name = "cpu"

    device = torch.device(device_name)
    logger.info("載入模型檢查點 %s 至裝置 %s", checkpoint, device)

    model = CycleGANModule.load_from_checkpoint(str(checkpoint))
    model.to(device)
    model.eval()

    # 載入正規化參數
    import json
    normalization_path = checkpoint.parent / 'normalization_params.json'
    normalization_params = {}

    if normalization_path.exists():
        logger.info("載入正規化參數 %s", normalization_path)
        with open(normalization_path, 'r', encoding='utf-8') as f:
            params = json.load(f)

        # 轉換為 numpy array
        for key, value in params.items():
            normalization_params[key] = np.array(value, dtype=np.float32)

        # 注意：使用統一歸一化時，mean_a = mean_b, std_a = std_b
        # 但為了向後兼容性，我們仍然保留所有參數
        logger.info(
            "正規化參數已載入 - Domain A: mean=%.4f, std=%.4f | Domain B: mean=%.4f, std=%.4f",
            normalization_params['mean_a'].mean(),
            normalization_params['std_a'].mean(),
            normalization_params['mean_b'].mean(),
            normalization_params['std_b'].mean(),
        )
    else:
        logger.warning("⚠ 未找到正規化參數檔案 %s，將不進行正規化（可能導致轉換結果不佳）", normalization_path)

    return model, device, normalization_params


def get_collection() -> Collection:
    """建立 MongoDB 連線並取得目標集合。"""
    cfg = get_mongodb_config()
    client = MongoClient(cfg["uri"])
    return client[cfg["database"]][cfg["collection"]]


def build_query(base_query: Dict[str, Any], input_step: int, run_id: Optional[str]) -> Dict[str, Any]:
    """組合 Domain B 查詢條件與 Step 條件（支援新版 run 結構）。"""
    step_condition = {"features_step": input_step, "features_state": "completed"}

    legacy_filter = {"analyze_features": {"$elemMatch": step_condition}}
    run_filter: Dict[str, Any] = {
        "analyze_features.runs": {
            "$elemMatch": {
                "steps": {"$elemMatch": step_condition}
            }
        }
    }
    if run_id:
        run_filter["analyze_features.runs"]["$elemMatch"]["analysis_id"] = run_id

    step_filter = {"$or": [legacy_filter, run_filter]}

    if base_query:
        return {"$and": [copy.deepcopy(base_query), step_filter]}
    return step_filter


def iter_documents(
    collection: Collection,
    query: Dict[str, Any],
    limit: Optional[int],
) -> Iterable[Dict[str, Any]]:
    """
    遍歷符合條件的分析任務。

    Args:
        collection: MongoDB 集合。
        query: 完整查詢條件。
        limit: 最大處理數量（None 表示不限制）。
    """
    cursor = collection.find(
        query,
        {
            "_id": 0,
            "AnalyzeUUID": 1,
            "analyze_features": 1,
            "analysis_status": 1,
            "current_step": 1,
            "analysis_summary": 1,
            "created_at": 1,
            "processing_started_at": 1,
            "updated_at": 1,
            "error_message": 1,
        },
    )

    if limit:
        cursor = cursor.limit(limit)

    return cursor


def parse_features(step_data: Dict[str, Any]) -> List[np.ndarray]:
    """將步驟中的 features_data 轉換為 numpy 陣列列表並驗證形狀。"""
    features_raw = step_data.get("features_data")
    if not features_raw:
        raise ValueError("features_data 為空")

    features_list: List[np.ndarray] = []
    for idx, sample in enumerate(features_raw):
        array = np.asarray(sample, dtype=np.float32)
        if array.ndim == 1 and array.shape[0] == 40:
            array = array.reshape(1, 40)
        if array.ndim != 2 or array.shape[1] != 40:
            raise ValueError(f"第 {idx} 筆樣本形狀為 {array.shape}，應為 (seq_len, 40)")
        features_list.append(array)

    return features_list


def convert_features(
    model: CycleGANModule,
    device: torch.device,
    features_list: List[np.ndarray],
    normalization_params: Dict[str, np.ndarray],
) -> List[List[List[float]]]:
    """執行 Domain B → Domain A 轉換。"""
    converted: List[List[List[float]]] = []

    # 取得正規化參數（B→A 方向：輸入用 B，輸出用 A）
    has_norm = bool(normalization_params)
    if has_norm:
        mean_input = normalization_params['mean_b']
        std_input = normalization_params['std_b']
        mean_output = normalization_params['mean_a']
        std_output = normalization_params['std_a']

    with torch.no_grad():
        for sample in features_list:
            # 正規化輸入
            if has_norm:
                sample_normalized = (sample - mean_input) / std_input
            else:
                sample_normalized = sample

            tensor = torch.tensor(sample_normalized, dtype=torch.float32, device=device).unsqueeze(0)
            translated = model.convert_B_to_A(tensor)
            translated_np = translated.squeeze(0).cpu().numpy()

            # 反正規化輸出
            if has_norm:
                translated_np = translated_np * std_output + mean_output

            converted.append(translated_np.tolist())

    return converted


def main() -> None:
    data_cfg = get_data_config()
    domain_b_cfg = copy.deepcopy(data_cfg["domain_b"])

    parser = argparse.ArgumentParser(description="批次將 Domain B 特徵轉換為 Domain A")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="CycleGAN 檢查點路徑")
    parser.add_argument("--device", type=str, default=DEFAULT_DEVICE, choices=["cpu", "cuda"], help="推論裝置")
    parser.add_argument("--input-step", type=int, default=DEFAULT_INPUT_STEP, help="來源步驟編號（預設 2）")
    parser.add_argument("--output-step", type=int, default=DEFAULT_OUTPUT_STEP, help="輸出步驟編號（預設 6）")
    parser.add_argument("--limit", type=int, default=domain_b_cfg.get("max_samples"), help="最大處理筆數（預設使用 config 中的 max_samples）")
    parser.add_argument("--device-id", type=str, help="覆寫 domain_b 設備 ID 查詢")
    parser.add_argument("--source-run-id", type=str, help="指定來源分析 run ID（預設使用最新）")
    parser.add_argument("--overwrite", action="store_true", help="若目標步驟已存在則覆寫")
    parser.add_argument("--dry-run", action="store_true", help="僅顯示將處理的任務，不寫回資料庫")
    args = parser.parse_args()

    if args.device_id:
        domain_b_cfg["mongo_query"]["info_features.device_id"] = args.device_id

    mongo_query = build_query(domain_b_cfg["mongo_query"], args.input_step, args.source_run_id)
    collection = get_collection()
    model, device, normalization_params = load_model(args.checkpoint, args.device)

    total = converted = skipped = failures = 0
    last_uuid: Optional[str] = None

    for doc in iter_documents(collection, mongo_query, args.limit):
        total += 1
        analyze_uuid = doc.get("AnalyzeUUID")
        last_uuid = analyze_uuid

        container = ensure_analysis_container(collection, doc)
        run_doc, source_run_id = select_analysis_run(doc, args.source_run_id)
        if not run_doc:
            logger.warning("分析任務 %s 沒有符合條件的分析 run，跳過", analyze_uuid)
            skipped += 1
            continue

        input_step_data = extract_step_from_run(run_doc, args.input_step)
        if not input_step_data:
            logger.warning("分析任務 %s 的 run %s 缺少步驟 %s，跳過", analyze_uuid, source_run_id or "unknown", args.input_step)
            skipped += 1
            continue

        if has_completed_step(container, args.output_step) and not args.overwrite:
            logger.info("分析任務 %s 已存在步驟 %s，使用 --overwrite 可重新寫入", analyze_uuid, args.output_step)
            skipped += 1
            continue

        try:
            features_list = parse_features(input_step_data)
            converted_features = convert_features(model, device, features_list, normalization_params)
        except Exception as exc:
            logger.exception("分析任務 %s 轉換失敗：%s", analyze_uuid, exc)
            failures += 1
            continue

        metadata = {
            "source_step": args.input_step,
            "direction": "B→A",
            "checkpoint": str(args.checkpoint),
            "device": str(device),
            "converted_at": datetime.utcnow(),
            "num_samples": len(converted_features),
            "source_run_id": source_run_id,
        }

        if args.dry_run:
            logger.info(
                "[DRY RUN] 分析任務 %s 將寫入步驟 %s，共 %s 筆樣本",
                analyze_uuid,
                args.output_step,
                len(converted_features),
            )
            converted += 1
            continue

        run_context = {
            "source": "batch_domain_conversion",
            "input_step": args.input_step,
            "output_step": args.output_step,
            "checkpoint": str(args.checkpoint),
            "device": str(device),
            "source_run_id": source_run_id,
        }

        append_conversion_run(
            collection=collection,
            analyze_uuid=analyze_uuid,
            step_id=args.output_step,
            converted=converted_features,
            metadata=metadata,
            context=run_context,
            overwrite=args.overwrite,
        )
        logger.info(
            "分析任務 %s 已寫入步驟 %s，共 %s 筆樣本",
            analyze_uuid,
            args.output_step,
            len(converted_features),
        )
        converted += 1

    logger.info(
        "批次轉換完成：處理 %s 筆，成功 %s，跳過 %s，失敗 %s。最後處理 UUID：%s",
        total or 0,
        converted or 0,
        skipped or 0,
        failures or 0,
        last_uuid or "N/A",
    )


if __name__ == "__main__":
    main()
