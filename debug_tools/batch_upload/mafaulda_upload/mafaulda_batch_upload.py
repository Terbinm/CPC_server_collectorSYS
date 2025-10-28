# batch_upload.py - 獨立批量上傳工具(直接寫入 MongoDB + GridFS)

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import hashlib
import uuid
import random
from pymongo import MongoClient
from gridfs import GridFS
from bson.objectid import ObjectId
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time

from config import UploadConfig


class BatchUploadLogger:
    """日誌管理器"""

    @staticmethod
    def setup_logger(name: str = 'batch_upload') -> logging.Logger:
        """設置日誌記錄器"""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, UploadConfig.LOGGING_CONFIG['level']))

        if logger.handlers:
            return logger

        formatter = logging.Formatter(UploadConfig.LOGGING_CONFIG['format'])

        log_path = Path(UploadConfig.LOGGING_CONFIG['log_file'])
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 檔案處理器
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=UploadConfig.LOGGING_CONFIG['max_bytes'],
            backupCount=UploadConfig.LOGGING_CONFIG['backup_count'],
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # 控制台處理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger


logger = BatchUploadLogger.setup_logger()


class MongoDBUploader:
    """MongoDB + GridFS 上傳器"""

    def __init__(self):
        """初始化 MongoDB 連接"""
        self.config = UploadConfig.MONGODB_CONFIG
        self.mongo_client = None
        self.db = None
        self.collection = None
        self.fs = None
        self._connect()

    def _connect(self):
        """建立 MongoDB 連接"""
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

            # 測試連接
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB 連接成功")

        except Exception as e:
            logger.error(f"✗ MongoDB 連接失敗: {e}")
            raise

    def file_exists(self, file_hash: str) -> bool:
        """檢查檔案是否已存在(根據雜湊值)"""
        if not UploadConfig.UPLOAD_BEHAVIOR['check_duplicates']:
            return False

        existing = self.collection.find_one({
            'info_features.file_hash': file_hash
        })
        return existing is not None

    def upload_file(self, file_path: Path, label: str, file_hash: str,
                    file_metadata: Dict[str, Any]) -> Optional[str]:
        """
        上傳檔案到 MongoDB + GridFS

        Returns:
            記錄的 AnalyzeUUID,失敗返回 None
        """
        try:
            analyze_uuid = str(uuid.uuid4())

            # 讀取檔案數據
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # 上傳到 GridFS
            file_id = None
            if UploadConfig.USE_GRIDFS:
                file_id = self.fs.put(
                    file_data,
                    filename=file_path.name,
                    metadata={
                        'device_id': f'BATCH_UPLOAD_{label.upper()}',
                        'upload_time': datetime.utcnow().isoformat(),
                        'file_hash': file_hash,
                        'label': label
                    }
                )
                logger.debug(f"檔案上傳至 GridFS: {file_id}")

            # 創建 MongoDB 文檔
            document = self._create_document(
                analyze_uuid=analyze_uuid,
                filename=file_path.name,
                file_hash=file_hash,
                file_id=file_id,
                label=label,
                file_metadata=file_metadata
            )

            # 插入 MongoDB
            self.collection.insert_one(document)
            logger.debug(f"記錄插入 MongoDB: {analyze_uuid}")

            return analyze_uuid

        except Exception as e:
            logger.error(f"上傳失敗 {file_path.name}: {e}")
            return None

    def _create_document(self, analyze_uuid: str, filename: str,
                         file_hash: str, file_id: ObjectId, label: str,
                         file_metadata: Dict[str, Any]) -> Dict:
        """創建 MongoDB 文檔(符合 V3 格式)"""
        current_time = datetime.utcnow()

        # 獲取檔案元數據
        file_type = Path(filename).suffix[1:].lower()
        duration = file_metadata.get('duration')
        file_size = file_metadata.get('file_size')

        mafaulda_metadata = {
            'fault_type': file_metadata.get('fault_type'),
            'fault_variant': file_metadata.get('fault_variant'),
            'fault_condition': file_metadata.get('fault_condition'),
            'fault_hierarchy': file_metadata.get('fault_hierarchy'),
            'relative_path': file_metadata.get('relative_path'),
            'rotational_frequency_hz': file_metadata.get('rotational_frequency_hz'),
            'rotational_speed_rpm': file_metadata.get('rotational_speed_rpm'),
            'num_samples': file_metadata.get('num_samples'),
            'num_channels': file_metadata.get('num_channels'),
            'sample_rate_hz': file_metadata.get('sample_rate_hz'),
        }
        mafaulda_metadata = {k: v for k, v in mafaulda_metadata.items() if v is not None}

        batch_metadata = {
            "upload_method": "BATCH_UPLOAD",
            "upload_timestamp": current_time.isoformat(),
            "label": label,
            "source": "mafaulda_batch_uploader_v1.0"
        }
        if file_metadata.get('fault_condition'):
            batch_metadata['fault_condition'] = file_metadata['fault_condition']

        analysis_config = getattr(UploadConfig, 'ANALYSIS_CONFIG', {})
        target_channel = analysis_config.get('target_channel') if isinstance(analysis_config, dict) else None
        document = {
            "AnalyzeUUID": analyze_uuid,
            "current_step": 0,
            "created_at": current_time,
            "updated_at": current_time,
            "files": {
                "raw": {
                    "fileId": file_id,
                    "filename": filename,
                    "type": file_type
                }
            },
            "analyze_features": [],
            "info_features": {
                "dataset_UUID": UploadConfig.DATASET_CONFIG['dataset_UUID'],
                "device_id": f"BATCH_UPLOAD_{label.upper()}",
                "testing": False,
                "obj_ID": UploadConfig.DATASET_CONFIG['obj_ID'],
                "upload_time": current_time.isoformat(),
                "upload_complete": True,
                "file_hash": file_hash,
                "file_size": file_size,
                "duration": duration,
                "label": label,  # 標籤資訊
                "batch_upload_metadata": batch_metadata,
                "mafaulda_metadata": mafaulda_metadata
            }
        }
        if target_channel is not None:
            document['info_features']['target_channel'] = target_channel

        return document

    def close(self):
        """關閉連接"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB 連接已關閉")


class BatchUploader:
    """批量上傳管理器"""

    def __init__(self):
        """初始化批量上傳器"""
        self.uploader = MongoDBUploader()
        self.supported_formats = UploadConfig.SUPPORTED_FORMATS

        # 統計資訊
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'labels': {},
            'failed_files': [],
            'filtered_invalid_label': 0
        }

        # 進度追蹤
        self.progress = self._load_progress()

        logger.info("批量上傳器初始化完成")

    def _load_progress(self) -> Dict:
        """載入上傳進度"""
        progress_path = Path(UploadConfig.PROGRESS_FILE)
        progress_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_path.exists():
            try:
                with progress_path.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"無法載入進度檔案: {e}")
        return {'uploaded_files': []}

    def _save_progress(self):
        """儲存上傳進度"""
        try:
            progress_path = Path(UploadConfig.PROGRESS_FILE)
            progress_path.parent.mkdir(parents=True, exist_ok=True)
            with progress_path.open('w', encoding='utf-8') as f:
                json.dump(self.progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"無法儲存進度檔案: {e}")

    @staticmethod
    def _to_json_serializable(data: Any) -> Any:
        """遞迴轉換資料為可序列化的 JSON 格式"""
        if isinstance(data, dict):
            return {k: BatchUploader._to_json_serializable(v) for k, v in data.items()}
        if isinstance(data, list):
            return [BatchUploader._to_json_serializable(item) for item in data]
        if isinstance(data, datetime):
            return data.isoformat()
        if isinstance(data, ObjectId):
            return str(data)
        return data

    def _generate_dry_run_samples(self, dataset_files: List[Dict[str, Any]]) -> None:
        """為 Dry Run 模式輸出各標籤的樣本 JSON"""
        preview_config = getattr(UploadConfig, 'DRY_RUN_PREVIEW', {})
        if not preview_config.get('enable_preview', True):
            logger.info("[DRY RUN] 預覽輸出已停用")
            return

        label_entries: Dict[str, List[Dict[str, Any]]] = {}
        for entry in dataset_files:
            label_entries.setdefault(entry['label'], []).append(entry)

        if not label_entries:
            logger.info("[DRY RUN] 沒有可輸出的標籤樣本")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        preview_root = Path(preview_config.get('output_directory', 'dry_run_previews'))
        if not preview_root.is_absolute():
            preview_root = Path(__file__).parent / preview_root
        preview_directory = preview_root / f"dry_run_{timestamp}"
        preview_directory.mkdir(parents=True, exist_ok=True)

        for label, entries in sorted(label_entries.items()):
            try:
                sample_entry = random.choice(entries)
                file_path: Path = sample_entry['path']
                path_metadata = sample_entry['path_metadata']

                file_metadata = self.get_file_metadata(file_path, path_metadata)
                file_hash = self.calculate_file_hash(file_path)
                analyze_uuid = str(uuid.uuid4())
                document = self.uploader._create_document(
                    analyze_uuid=analyze_uuid,
                    filename=file_path.name,
                    file_hash=file_hash,
                    file_id=None,
                    label=label,
                    file_metadata=file_metadata
                )

                preview_payload = {
                    'label': label,
                    'source_file': str(file_path),
                    'relative_path': file_metadata.get('relative_path'),
                    'file_metadata': self._to_json_serializable(file_metadata),
                    'document': self._to_json_serializable(document),
                }

                output_filename = f"{label}_{file_path.stem}_{analyze_uuid[:8]}.json"
                output_path = preview_directory / output_filename

                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(preview_payload, f, indent=2, ensure_ascii=False)

                logger.info(f"[DRY RUN] 樣本已輸出: {output_path}")

            except Exception as e:
                logger.error(f"[DRY RUN] 產生標籤 {label} 的樣本失敗: {e}")

        logger.info(f"[DRY RUN] 預覽輸出目錄: {preview_directory}")

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """計算檔案 SHA-256 雜湊值"""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def _extract_rotational_speed(file_path: Path) -> Dict[str, Optional[float]]:
        """從檔案名稱推算轉速資訊 (e.g. 13.5168 -> 811 rpm)"""
        metadata: Dict[str, Optional[float]] = {}
        stem = file_path.stem
        try:
            frequency_hz = float(stem.replace('_', '.'))
            metadata['rotational_frequency_hz'] = frequency_hz
            metadata['rotational_speed_rpm'] = frequency_hz * 60.0
        except ValueError:
            # 檔名不是數值時忽略即可
            pass
        return metadata

    def _analyze_file_path(self, file_path: Path) -> Dict[str, Any]:
        """從路徑解析 MAFAULDA 資料的標籤與層級資訊"""
        base_path = Path(UploadConfig.UPLOAD_DIRECTORY)
        try:
            relative = file_path.relative_to(base_path)
        except ValueError:
            relative = file_path

        parts = relative.parts
        folder_map = {
            folder_name.lower(): label_key
            for label_key, folder_name in UploadConfig.LABEL_FOLDERS.items()
        }

        label = 'unknown'
        if parts:
            label = folder_map.get(parts[0].lower(), 'unknown')

        fault_hierarchy = list(parts[1:-1]) if len(parts) > 1 else []

        metadata: Dict[str, Any] = {
            'relative_path': str(relative).replace("\\", "/"),
        }
        if label != 'unknown':
            metadata['fault_type'] = label

        if fault_hierarchy:
            metadata['fault_hierarchy'] = fault_hierarchy
            metadata['fault_variant'] = fault_hierarchy[0]
            metadata['fault_condition'] = "/".join(fault_hierarchy)

        metadata.update(self._extract_rotational_speed(file_path))
        return label, metadata

    def _get_csv_metadata(self, file_path: Path) -> Dict[str, Any]:
        """解析 CSV 檔案的取樣點數與欄位數"""
        num_samples = 0
        num_channels: Optional[int] = None

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if num_channels is None:
                        num_channels = len(stripped.split(','))
                    num_samples += 1
        except Exception as e:
            logger.warning(f"無法解析 CSV 檔案 {file_path.name}: {e}")
            return {
                'num_samples': None,
                'num_channels': num_channels,
                'duration': None
            }

        metadata: Dict[str, Any] = {
            'num_samples': num_samples,
            'num_channels': num_channels,
        }

        sample_rate = UploadConfig.CSV_CONFIG.get('sample_rate_hz')
        if sample_rate and num_samples:
            metadata['duration'] = num_samples / sample_rate
        else:
            metadata['duration'] = None

        expected_channels = UploadConfig.CSV_CONFIG.get('expected_channels')
        if expected_channels and num_channels and num_channels != expected_channels:
            logger.warning(
                f"CSV 欄位數異常 {file_path.name}: 期望 {expected_channels}, 實際 {num_channels}"
            )

        return metadata

    def get_file_metadata(self, file_path: Path, path_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """整合檔案與路徑取得的所有中繼資訊"""
        metadata: Dict[str, Any] = {
            'file_size': file_path.stat().st_size,
            'sample_rate_hz': UploadConfig.CSV_CONFIG.get('sample_rate_hz'),
        }
        metadata.update(path_metadata)

        ext = file_path.suffix.lower()
        if ext == '.csv':
            metadata.update(self._get_csv_metadata(file_path))
        else:
            metadata['duration'] = None

        if metadata.get('duration') is None and metadata.get('num_samples') and metadata.get('sample_rate_hz'):
            metadata['duration'] = metadata['num_samples'] / metadata['sample_rate_hz']

        return metadata

    def scan_directory(self) -> List[Dict[str, Any]]:
        """掃描資料夾,找出所有待上傳的資料檔案"""
        logger.info(f"掃描資料夾: {UploadConfig.UPLOAD_DIRECTORY}")

        directory_path = Path(UploadConfig.UPLOAD_DIRECTORY)
        dataset_files: List[Dict[str, Any]] = []

        # 遞迴掃描
        for ext in self.supported_formats:
            for file_path in directory_path.rglob(f"*{ext}"):
                if file_path.is_file():
                    label, path_metadata = self._analyze_file_path(file_path)
                    if label == 'unknown':
                        try:
                            rel_path = file_path.relative_to(directory_path)
                        except ValueError:
                            rel_path = file_path
                        logger.warning(
                            f"忽略未在 LABEL_FOLDERS 設定中的子資料夾檔案: {rel_path}"
                        )
                        self.stats['filtered_invalid_label'] += 1
                        continue

                    dataset_files.append({
                        'path': file_path,
                        'label': label,
                        'path_metadata': path_metadata
                    })

        logger.info(f"找到 {len(dataset_files)} 個資料檔案")
        return dataset_files

    def _apply_label_limit(self, dataset_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """依設定限制每個標籤的檔案數量"""
        limit = UploadConfig.UPLOAD_BEHAVIOR.get('per_label_limit', 0)
        if not isinstance(limit, int) or limit <= 0:
            return dataset_files

        logger.info(f"套用標籤上限: 每個標籤最多 {limit} 個檔案")

        limited_files: List[Dict[str, Any]] = []
        label_counts: Dict[str, int] = {}
        skipped = 0

        for entry in dataset_files:
            label = entry['label']
            count = label_counts.get(label, 0)
            if count >= limit:
                skipped += 1
                continue

            label_counts[label] = count + 1
            limited_files.append(entry)

        if skipped:
            logger.info(f"依標籤上限排除 {skipped} 個資料檔案")

        return limited_files

    def upload_single_file(self, file_entry: Dict[str, Any]) -> bool:
        """上傳單個檔案"""
        try:
            file_path: Path = file_entry['path']
            label: str = file_entry['label']
            path_metadata: Dict[str, Any] = file_entry['path_metadata']

            # 檢查是否已上傳
            file_hash = self.calculate_file_hash(file_path)

            if UploadConfig.UPLOAD_BEHAVIOR['skip_existing']:
                if file_hash in self.progress['uploaded_files']:
                    logger.debug(f"跳過已上傳: {file_path.name}")
                    self.stats['skipped'] += 1
                    return True

                if self.uploader.file_exists(file_hash):
                    logger.debug(f"跳過已存在: {file_path.name}")
                    self.progress['uploaded_files'].append(file_hash)
                    self._save_progress()
                    self.stats['skipped'] += 1
                    return True

            # 獲取檔案資訊
            file_metadata = self.get_file_metadata(file_path, path_metadata)

            # 上傳檔案(帶重試)
            for attempt in range(UploadConfig.UPLOAD_BEHAVIOR['retry_attempts']):
                analyze_uuid = self.uploader.upload_file(
                    file_path, label, file_hash, file_metadata
                )

                if analyze_uuid:
                    logger.info(f"✓ {file_path.name} (標籤: {label})")
                    self.stats['success'] += 1
                    self.stats['labels'][label] = self.stats['labels'].get(label, 0) + 1

                    # 記錄進度
                    self.progress['uploaded_files'].append(file_hash)
                    self._save_progress()

                    return True

                if attempt < UploadConfig.UPLOAD_BEHAVIOR['retry_attempts'] - 1:
                    time.sleep(UploadConfig.UPLOAD_BEHAVIOR['retry_delay'])

            # 上傳失敗
            logger.error(f"✗ {file_path.name}")
            self.stats['failed'] += 1
            self.stats['failed_files'].append(str(file_path))
            return False

        except Exception as e:
            logger.error(f"✗ {file_path.name}: {e}")
            self.stats['failed'] += 1
            self.stats['failed_files'].append(str(file_path))
            return False

    def batch_upload(self, dry_run: bool = False):
        """執行批量上傳"""
        logger.info("=" * 60)
        logger.info("批量上傳開始")
        logger.info("=" * 60)

        # 掃描檔案
        dataset_files = self.scan_directory()
        if not dataset_files:
            logger.warning("沒有找到任何資料檔案")
            return

        dataset_files = self._apply_label_limit(dataset_files)
        if not dataset_files:
            logger.warning("套用標籤上限後沒有可上傳的資料檔案")
            return

        self.stats['total'] = len(dataset_files)

        # 統計標籤分布
        label_counts = {}
        for entry in dataset_files:
            label = entry['label']
            label_counts[label] = label_counts.get(label, 0) + 1

        logger.info(f"\n檔案統計:")
        logger.info(f"  總計: {len(dataset_files)} 個")
        for label, count in sorted(label_counts.items()):
            logger.info(f"  - {label}: {count} 個")

        if dry_run:
            logger.info("\n[DRY RUN 模式] 不會實際上傳")
            self._generate_dry_run_samples(dataset_files)
            return

        # 確認上傳
        print("\n是否開始上傳? (y/n): ", end='')
        confirm = input().strip().lower()
        if confirm != 'y':
            logger.info("取消上傳")
            return

        # 批量上傳
        logger.info("\n開始上傳檔案...\n")

        concurrent = UploadConfig.UPLOAD_BEHAVIOR['concurrent_uploads']

        if concurrent > 1:
            # 並行上傳
            with ThreadPoolExecutor(max_workers=concurrent) as executor:
                futures = {
                    executor.submit(self.upload_single_file, entry): entry
                    for entry in dataset_files
                }

                with tqdm(total=len(dataset_files), desc="上傳進度") as pbar:
                    for future in as_completed(futures):
                        future.result()
                        pbar.update(1)
        else:
            # 單線程上傳
            with tqdm(dataset_files, desc="上傳進度") as pbar:
                for entry in pbar:
                    self.upload_single_file(entry)
                    pbar.set_postfix({
                        '成功': self.stats['success'],
                        '失敗': self.stats['failed'],
                        '跳過': self.stats['skipped']
                    })

        # 顯示統計
        self._print_summary()

        # 儲存報告
        self._save_report()

    def _print_summary(self):
        """顯示統計摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("批量上傳完成")
        logger.info("=" * 60)
        logger.info(f"總計:   {self.stats['total']} 個檔案")
        logger.info(f"成功:   {self.stats['success']} 個")
        logger.info(f"失敗:   {self.stats['failed']} 個")
        logger.info(f"跳過:   {self.stats['skipped']} 個")
        if self.stats['filtered_invalid_label']:
            logger.info(f"忽略未設定標籤的檔案: {self.stats['filtered_invalid_label']} 個")

        if self.stats['labels']:
            logger.info(f"\n標籤統計:")
            for label, count in sorted(self.stats['labels'].items()):
                logger.info(f"  {label}: {count} 個")
        else:
            logger.info("\n標籤統計: 尚無成功上傳的檔案")

        if self.stats['failed_files']:
            logger.info(f"\n失敗檔案列表:")
            for file_path in self.stats['failed_files'][:10]:
                logger.info(f"  - {file_path}")
            if len(self.stats['failed_files']) > 10:
                logger.info(f"  ... 還有 {len(self.stats['failed_files']) - 10} 個")

    def _save_report(self):
        """儲存上傳報告"""
        if not UploadConfig.REPORT_OUTPUT['save_report']:
            return

        try:
            report_dir = UploadConfig.REPORT_OUTPUT['report_directory']
            os.makedirs(report_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = os.path.join(
                report_dir,
                f"upload_report_{timestamp}.json"
            )

            statistics = dict(self.stats)
            statistics['labels'] = dict(sorted(self.stats['labels'].items()))

            report = {
                'timestamp': timestamp,
                'upload_directory': str(UploadConfig.UPLOAD_DIRECTORY),
                'statistics': statistics,
                'config': {
                    'dataset_UUID': UploadConfig.DATASET_CONFIG['dataset_UUID'],
                    'use_gridfs': UploadConfig.USE_GRIDFS,
                    'skip_existing': UploadConfig.UPLOAD_BEHAVIOR['skip_existing'],
                    'sample_rate_hz': UploadConfig.CSV_CONFIG.get('sample_rate_hz'),
                }
            }

            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"\n報告已儲存: {report_file}")

        except Exception as e:
            logger.error(f"儲存報告失敗: {e}")

    def cleanup(self):
        """清理資源"""
        self.uploader.close()


def main():
    """主程式"""
    print("""
╔══════════════════════════════════════════════════════════╗
║      MAFAULDA 批量資料上傳工具 v1.0 (獨立版本)              ║
║                                                          ║
║  功能:                                                    ║
║  1. 直接寫入 MongoDB + GridFS (不需要 Flask)              ║
║  2. 自動偵測並標記 MAFAULDA 故障分類                       ║
║  3. 支援並行上傳與斷點續傳                                  ║
║  4. 完整的進度追蹤與錯誤處理                                ║
║                                                          ║
║  配置檔案: config.py                                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 驗證配置
    from config import validate_config
    errors = validate_config()

    if errors:
        logger.error("配置錯誤:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    # 詢問模式
    print("選擇執行模式:")
    print("  1. 預覽模式 (DRY RUN - 只顯示將要上傳的檔案)")
    print("  2. 正式上傳")
    print("\n請輸入選項 (1 或 2): ", end='')

    mode = input().strip()
    dry_run = (mode == '1')

    # 創建上傳器
    uploader = BatchUploader()

    try:
        uploader.batch_upload(dry_run=dry_run)
    except KeyboardInterrupt:
        logger.info("\n\n上傳被使用者中斷")
    except Exception as e:
        logger.error(f"上傳過程發生錯誤: {e}")
    finally:
        uploader.cleanup()
        logger.info("\n程式結束")


if __name__ == '__main__':
    main() #
