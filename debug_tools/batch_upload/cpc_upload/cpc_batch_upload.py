"""CPC 工廠音訊批次上傳工具。

自設定的資料夾讀取 WAV 音檔並上傳到 MongoDB／GridFS。
流程沿用其他資料集的批次上傳邏輯，但不需要分類子資料夾，
所有檔案都會套用同一個標籤與裝置代碼。
"""

from __future__ import annotations

import json
import logging
import hashlib
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import soundfile as sf
from bson.objectid import ObjectId
from gridfs import GridFS
from pymongo import MongoClient
from tqdm import tqdm

from config import UploadConfig


class BatchUploadLogger:
    """負責建立共用記錄器。"""

    @staticmethod
    def setup_logger(name: str = "cpc_batch_upload") -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, UploadConfig.LOGGING_CONFIG['level']))

        if logger.handlers:
            return logger

        formatter = logging.Formatter(UploadConfig.LOGGING_CONFIG['format'])

        log_path = Path(UploadConfig.LOGGING_CONFIG['log_file'])
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=UploadConfig.LOGGING_CONFIG['max_bytes'],
            backupCount=UploadConfig.LOGGING_CONFIG['backup_count'],
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger


logger = BatchUploadLogger.setup_logger()


class MongoDBUploader:
    """封裝 MongoDB 與 GridFS 操作的類別。"""

    def __init__(self) -> None:
        self.config = UploadConfig.MONGODB_CONFIG
        self.mongo_client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        self.fs: Optional[GridFS] = None
        self._connect()

    def _connect(self) -> None:
        try:
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
            self.db = self.mongo_client[self.config['database']]
            self.collection = self.db[self.config['collection']]

            if UploadConfig.USE_GRIDFS:
                self.fs = GridFS(self.db)

            self.mongo_client.admin.command("ping")
            logger.info("成功連線至 MongoDB。")
        except Exception as exc:  # pragma: no cover - 實際連線錯誤不易測試
            logger.error("無法連線至 MongoDB：%s", exc)
            raise

    def file_exists(self, file_hash: str) -> bool:
        if not UploadConfig.UPLOAD_BEHAVIOR['check_duplicates']:
            return False
        existing = self.collection.find_one({'info_features.file_hash': file_hash})
        return existing is not None

    def upload_file(
        self,
        file_path: Path,
        label: str,
        file_hash: str,
        cpc_metadata: Dict[str, Any],
    ) -> Optional[str]:
        analyze_uuid = str(uuid.uuid4())

        try:
            with open(file_path, 'rb') as handle:
                file_data = handle.read()

            file_id = None
            if self.fs:
                file_id = self.fs.put(
                    file_data,
                    filename=file_path.name,
                    metadata={
                        'device_id': UploadConfig.DEVICE_ID,
                        'file_hash': file_hash,
                        'label': label,
                    },
                )
                logger.debug("檔案已寫入 GridFS：%s", file_id)

            document = self._create_document(
                analyze_uuid=analyze_uuid,
                filename=file_path.name,
                file_hash=file_hash,
                file_id=file_id,
                label=label,
                cpc_metadata=cpc_metadata,
            )

            self.collection.insert_one(document)
            logger.debug("已新增 MongoDB 文件：%s", analyze_uuid)
            return analyze_uuid

        except Exception as exc:
            logger.error("上傳檔案 %s 時發生錯誤：%s", file_path.name, exc)
            return None

    def _create_document(
        self,
        analyze_uuid: str,
        filename: str,
        file_hash: str,
        file_id: Optional[ObjectId],
        label: str,
        cpc_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_time = datetime.now(UTC)
        file_type = Path(filename).suffix.lstrip('.').lower()

        info_features: Dict[str, Any] = {
            "dataset_UUID": UploadConfig.DATASET_CONFIG['dataset_UUID'],
            "device_id": UploadConfig.DEVICE_ID,
            "testing": False,
            "obj_ID": UploadConfig.DATASET_CONFIG['obj_ID'],
            "upload_complete": True,
            "file_hash": file_hash,
            "file_size": cpc_metadata.get('file_size'),
            "duration": cpc_metadata.get('duration'),
            "label": label,
            "sample_rate": cpc_metadata.get('sample_rate'),
            "channels": cpc_metadata.get('channels'),
            "raw_format": cpc_metadata.get('format'),
            "cpc_metadata": {
                "subtype": cpc_metadata.get('subtype'),
            },
        }

        # 添加 target_channel
        target_channel = getattr(UploadConfig, 'TARGET_CHANNEL', None)
        if target_channel is not None:
            info_features['target_channel'] = target_channel

        document = {
            "AnalyzeUUID": analyze_uuid,
            "current_step": 0,
            "created_at": current_time,
            "updated_at": current_time,
            "files": {
                "raw": {
                    "fileId": file_id,
                    "filename": filename,
                    "type": file_type,
                }
            },
            "analyze_features": [],
            "info_features": info_features,
        }

        return document

    def close(self) -> None:
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("已關閉 MongoDB 連線。")


class BatchUploader:
    """負責管理 CPC 音檔的掃描、上傳與報告輸出。"""

    def __init__(self) -> None:
        self.uploader = MongoDBUploader()
        self.supported_formats = UploadConfig.SUPPORTED_FORMATS
        self.default_label = UploadConfig.DEFAULT_LABEL or "未分類"

        self.stats: Dict[str, Any] = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'labels': {},
            'failed_files': [],
        }

        self.progress = self._load_progress()
        logger.info("批次上傳器已完成初始化。")

    def _load_progress(self) -> Dict[str, Any]:
        progress_path = Path(UploadConfig.PROGRESS_FILE)
        progress_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_path.exists():
            try:
                with progress_path.open('r', encoding='utf-8') as handle:
                    return json.load(handle)
            except Exception as exc:
                logger.warning("無法載入進度檔案：%s", exc)
        return {'uploaded_files': []}

    def _save_progress(self) -> None:
        try:
            progress_path = Path(UploadConfig.PROGRESS_FILE)
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            with progress_path.open('w', encoding='utf-8') as handle:
                json.dump(self.progress, handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("無法寫入進度檔案：%s", exc)

    @staticmethod
    def _to_json_serializable(data: Any) -> Any:
        if isinstance(data, dict):
            return {k: BatchUploader._to_json_serializable(v) for k, v in data.items()}
        if isinstance(data, list):
            return [BatchUploader._to_json_serializable(item) for item in data]
        if isinstance(data, datetime):
            return data.isoformat()
        if isinstance(data, ObjectId):
            return str(data)
        return data

    def _generate_dry_run_samples(self, audio_files: List[Tuple[Path, str]]) -> None:
        preview_config = getattr(UploadConfig, 'DRY_RUN_PREVIEW', {})
        if not preview_config.get('enable_preview', True):
            logger.info("[模擬上傳] 已停用預覽輸出。")
            return

        label_entries: Dict[str, List[Path]] = {}
        for file_path, label in audio_files:
            label_entries.setdefault(label, []).append(file_path)

        if not label_entries:
            logger.info("[模擬上傳] 沒有找到可預覽的檔案。")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        preview_root = Path(preview_config.get('output_directory', 'reports/dry_run_previews'))
        if not preview_root.is_absolute():
            preview_root = Path(__file__).parent / preview_root

        preview_directory = preview_root / f"dry_run_{timestamp}"
        preview_directory.mkdir(parents=True, exist_ok=True)

        base_path = Path(UploadConfig.UPLOAD_DIRECTORY)

        for label, candidates in sorted(label_entries.items()):
            try:
                sample_path = random.choice(candidates)
                cpc_metadata = self.get_cpc_metadata(sample_path)

                try:
                    relative_path = sample_path.relative_to(base_path)
                    relative_path_str = str(relative_path).replace("\\", "/")
                except ValueError:
                    relative_path_str = str(sample_path)

                file_hash = self.calculate_file_hash(sample_path)
                analyze_uuid = str(uuid.uuid4())

                document = self.uploader._create_document(
                    analyze_uuid=analyze_uuid,
                    filename=sample_path.name,
                    file_hash=file_hash,
                    file_id=None,
                    label=label,
                    cpc_metadata=cpc_metadata,
                )

                preview_payload = {
                    'label': label,
                    'source_file': str(sample_path),
                    'relative_path': relative_path_str,
                    'file_hash': file_hash,
                    'cpc_metadata': cpc_metadata,
                    'document': self._to_json_serializable(document),
                }

                output_filename = f"{label}_{sample_path.stem}_{analyze_uuid[:8]}.json"
                output_path = preview_directory / output_filename

                with output_path.open('w', encoding='utf-8') as handle:
                    json.dump(preview_payload, handle, indent=2, ensure_ascii=False)

                logger.info("[模擬上傳] 已輸出預覽檔案：%s", output_path)

            except Exception as exc:
                logger.error("[模擬上傳] 產生標籤 %s 的預覽失敗：%s", label, exc)

        logger.info("[模擬上傳] 預覽檔案儲存於：%s", preview_directory)

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as handle:
            for block in iter(lambda: handle.read(4096), b""):
                sha256_hash.update(block)
        return sha256_hash.hexdigest()

    def get_cpc_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            'file_size': file_path.stat().st_size,
            'duration': None,
            'sample_rate': None,
            'channels': None,
            'subtype': None,
            'format': None,
        }

        try:
            info = sf.info(str(file_path))
            metadata.update({
                'duration': float(info.duration),
                'sample_rate': info.samplerate,
                'channels': info.channels,
                'subtype': info.subtype,
                'format': info.format,
            })
        except Exception as exc:
            logger.warning("無法讀取音訊中繼資料 %s：%s", file_path.name, exc)

        expected_rate = UploadConfig.AUDIO_CONFIG.get('expected_sample_rate_hz')
        if expected_rate and metadata['sample_rate'] and metadata['sample_rate'] != expected_rate:
            logger.warning(
                "取樣率不符 %s：預期 %s Hz，實際 %s Hz",
                file_path.name,
                expected_rate,
                metadata['sample_rate'],
            )

        if UploadConfig.AUDIO_CONFIG.get('allow_mono_only', False) and metadata['channels']:
            if metadata['channels'] != 1:
                logger.warning("偵測到非單聲道檔案：%s（%s 聲道）", file_path.name, metadata['channels'])

        return metadata

    def determine_label(self, file_path: Path) -> str:
        path_parts = [part.lower() for part in file_path.parts]
        for label, folder_name in UploadConfig.LABEL_FOLDERS.items():
            if folder_name.lower() in path_parts:
                return label
        return self.default_label

    def scan_directory(self) -> List[Tuple[Path, str]]:
        directory_path = Path(UploadConfig.UPLOAD_DIRECTORY)
        logger.info("正在掃描資料夾：%s", directory_path)

        if not directory_path.is_dir():
            logger.error("找不到上傳資料夾：%s", directory_path)
            return []

        audio_files: List[Tuple[Path, str]] = []
        for ext in self.supported_formats:
            for file_path in directory_path.rglob(f"*{ext}"):
                if file_path.is_file():
                    label = self.determine_label(file_path)
                    audio_files.append((file_path, label))

        logger.info("共找到 %s 個音訊檔案。", len(audio_files))
        return audio_files

    def _apply_label_limit(self, audio_files: List[Tuple[Path, str]]) -> List[Tuple[Path, str]]:
        limit = UploadConfig.UPLOAD_BEHAVIOR.get('per_label_limit', 0)
        if not isinstance(limit, int) or limit <= 0:
            return audio_files

        label_counts: Dict[str, int] = {}
        filtered: List[Tuple[Path, str]] = []

        for file_path, label in audio_files:
            count = label_counts.get(label, 0)
            if count >= limit:
                continue

            label_counts[label] = count + 1
            filtered.append((file_path, label))

        if filtered != audio_files:
            logger.info("已套用每個標籤上限（%s），保留 %s 個檔案。", limit, len(filtered))

        return filtered

    def upload_single_file(self, file_path: Path, label: str) -> bool:
        try:
            file_hash = self.calculate_file_hash(file_path)

            if UploadConfig.UPLOAD_BEHAVIOR['skip_existing']:
                if file_hash in self.progress['uploaded_files']:
                    logger.debug("進度檔案顯示已上傳，略過：%s", file_path.name)
                    self.stats['skipped'] += 1
                    return True

                if self.uploader.file_exists(file_hash):
                    logger.debug("資料庫中已存在相同檔案，略過：%s", file_path.name)
                    self.progress['uploaded_files'].append(file_hash)
                    self._save_progress()
                    self.stats['skipped'] += 1
                    return True

            cpc_metadata = self.get_cpc_metadata(file_path)

            for attempt in range(UploadConfig.UPLOAD_BEHAVIOR['retry_attempts']):
                analyze_uuid = self.uploader.upload_file(
                    file_path=file_path,
                    label=label,
                    file_hash=file_hash,
                    cpc_metadata=cpc_metadata,
                )

                if analyze_uuid:
                    logger.info("已上傳 %s（標籤：%s）", file_path.name, label)
                    self.stats['success'] += 1
                    self.stats['labels'][label] = self.stats['labels'].get(label, 0) + 1
                    self.progress['uploaded_files'].append(file_hash)
                    self._save_progress()
                    return True

                if attempt < UploadConfig.UPLOAD_BEHAVIOR['retry_attempts'] - 1:
                    time.sleep(UploadConfig.UPLOAD_BEHAVIOR['retry_delay'])

            logger.error("多次重試後仍無法上傳：%s", file_path.name)
            self.stats['failed'] += 1
            self.stats['failed_files'].append(str(file_path))
            return False

        except Exception as exc:
            logger.error("上傳 %s 時發生未預期的錯誤：%s", file_path.name, exc)
            self.stats['failed'] += 1
            self.stats['failed_files'].append(str(file_path))
            return False

    def batch_upload(self, dry_run: bool = False) -> None:
        logger.info("=" * 60)
        logger.info("開始執行 CPC 批次上傳")
        logger.info("=" * 60)

        audio_files = self.scan_directory()
        if not audio_files:
            logger.warning("沒有找到任何音訊檔案。")
            return

        audio_files = self._apply_label_limit(audio_files)
        if not audio_files:
            logger.warning("每個標籤的上限設定讓所有檔案都被排除，沒有可上傳的項目。")
            return

        self.stats['total'] = len(audio_files)

        label_counts: Dict[str, int] = {}
        for _, label in audio_files:
            label_counts[label] = label_counts.get(label, 0) + 1

        logger.info("檔案分佈：")
        for label, count in sorted(label_counts.items()):
            logger.info("  - %s：%s 個檔案", label, count)

        if dry_run:
            logger.info("[模擬上傳] 不會實際上傳任何檔案。")
            self._generate_dry_run_samples(audio_files)
            return

        print("\n是否開始上傳檔案？(y/n)：", end='')
        confirm = input().strip().lower()
        if confirm != 'y':
            logger.info("使用者取消上傳。")
            return

        logger.info("正在上傳檔案……")

        concurrent = UploadConfig.UPLOAD_BEHAVIOR['concurrent_uploads']
        if concurrent > 1:
            with ThreadPoolExecutor(max_workers=concurrent) as executor:
                futures = {
                    executor.submit(self.upload_single_file, file_path, label): (file_path, label)
                    for file_path, label in audio_files
                }

                with tqdm(total=len(audio_files), desc="上傳進度") as progress_bar:
                    for future in as_completed(futures):
                        future.result()
                        progress_bar.update(1)
        else:
            with tqdm(audio_files, desc="上傳進度") as progress_bar:
                for file_path, label in progress_bar:
                    self.upload_single_file(file_path, label)
                    progress_bar.set_postfix({
                        '成功': self.stats['success'],
                        '失敗': self.stats['failed'],
                        '跳過': self.stats['skipped'],
                    })

        self._print_summary()
        self._save_report()

    def _print_summary(self) -> None:
        logger.info("\n" + "=" * 60)
        logger.info("批次上傳完成")
        logger.info("=" * 60)
        logger.info("總計：%s 筆檔案", self.stats['total'])
        logger.info("成功：%s 筆檔案", self.stats['success'])
        logger.info("失敗：%s 筆檔案", self.stats['failed'])
        logger.info("跳過：%s 筆檔案", self.stats['skipped'])

        if self.stats['labels']:
            logger.info("\n各標籤統計：")
            for label, count in sorted(self.stats['labels'].items()):
                logger.info("  %s：%s 筆", label, count)
        else:
            logger.info("\n各標籤統計：尚無資料")

        if self.stats['failed_files']:
            logger.info("\n失敗檔案列表：")
            for file_path in self.stats['failed_files'][:10]:
                logger.info("  - %s", file_path)
            remaining = len(self.stats['failed_files']) - 10
            if remaining > 0:
                logger.info("  … 還有 %s 筆", remaining)

    def _save_report(self) -> None:
        if not UploadConfig.REPORT_OUTPUT['save_report']:
            return

        try:
            report_dir = UploadConfig.REPORT_OUTPUT['report_directory']
            Path(report_dir).mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = Path(report_dir) / f"upload_report_{timestamp}.json"

            report_payload = {
                'timestamp': timestamp,
                'upload_directory': str(UploadConfig.UPLOAD_DIRECTORY),
                'statistics': {
                    'total': self.stats['total'],
                    'success': self.stats['success'],
                    'failed': self.stats['failed'],
                    'skipped': self.stats['skipped'],
                    'labels': dict(sorted(self.stats['labels'].items())),
                    'failed_files': self.stats['failed_files'],
                },
                'config_snapshot': {
                    'dataset_UUID': UploadConfig.DATASET_CONFIG['dataset_UUID'],
                    'use_gridfs': UploadConfig.USE_GRIDFS,
                    'skip_existing': UploadConfig.UPLOAD_BEHAVIOR['skip_existing'],
                    'device_id': UploadConfig.DEVICE_ID,
                    'default_label': self.default_label,
                },
            }

            with report_file.open('w', encoding='utf-8') as handle:
                json.dump(report_payload, handle, indent=2, ensure_ascii=False)

            logger.info("已儲存報告檔案：%s", report_file)

        except Exception as exc:
            logger.error("寫入報告失敗：%s", exc)

    def cleanup(self) -> None:
        self.uploader.close()


def main() -> None:
    print("""
============================================================
   CPC 工廠音訊批次上傳工具 v1.0
============================================================
功能特色：
  - 直接寫入 MongoDB + GridFS（不依賴 Flask）
  - 所有 WAV 檔案統一使用「factory_ambient」標籤
  - 支援檔案重複檢查與續傳
  - 可執行模擬上傳並輸出預覽

設定檔案：config.py
============================================================
""")

    from config import validate_config
    issues = validate_config()

    if issues:
        logger.error("偵測到設定錯誤：")
        for issue in issues:
            logger.error("  - %s", issue)
        sys.exit(1)

    print("請選擇模式：")
    print("  1. 模擬上傳（僅輸出預覽）")
    print("  2. 直接上傳")
    print("\n請輸入選項 (1 或 2)：", end='')

    mode = input().strip()
    dry_run = (mode == '1')

    uploader = BatchUploader()
    try:
        uploader.batch_upload(dry_run=dry_run)
    except KeyboardInterrupt:
        logger.info("使用者中斷上傳程序。")
    except Exception as exc:
        logger.error("上傳過程發生未預期的錯誤：%s", exc)
    finally:
        uploader.cleanup()
        logger.info("流程結束。")


if __name__ == '__main__':
    main()
