# config.py - CPC 工廠音訊批次上傳設定
import os
from pathlib import Path


class UploadConfig:
    """CPC 批次上傳工具的集中設定。"""

    # ==================== MongoDB 連線設定 ====================
    MONGODB_CONFIG = {
        'host': 'localhost',
        'port': 27021,
        'username': 'web_ui',
        'password': 'hod2iddfsgsrl',
        'database': 'web_db',
        'collection': 'recordings'
    }

    # ==================== 資料來源 ====================
    UPLOAD_DIRECTORY = (
        r"C:\Users\sixsn\PycharmProjects\CPC_server_collectorSYS"
        r"\debug_tools\batch_upload\cpc_upload\cpc_data"
    )

    # CPC 錄音沒有分類子資料夾，全部檔案使用同一標籤與裝置代碼。
    LABEL_FOLDERS: dict[str, str] = {}
    DEFAULT_LABEL = "factory_ambient"
    DEVICE_ID = "cpc006"

    # ==================== 支援檔案格式 ====================
    SUPPORTED_FORMATS = ['.wav']

    # ==================== 資料集固定欄位 ====================
    DATASET_CONFIG = {
        'dataset_UUID': 'cpc_batch_upload',
    }

    ANALYSIS_CONFIG = {
        # CPC 音訊為單聲道，如有變更請調整此設定。
        'target_channel': [0],
    }

    AUDIO_CONFIG = {
        'expected_sample_rate_hz': 16000,  # CPC 錄音為 16 kHz
        'allow_mono_only': True,
    }

    # ==================== 上傳行為設定 ====================
    UPLOAD_BEHAVIOR = {
        'skip_existing': True,
        'check_duplicates': True,
        'concurrent_uploads': 3,
        'retry_attempts': 3,
        'retry_delay': 2,
        'per_label_limit': 2,  # 0 代表不限制每個標籤的檔案數量
    }

    # ==================== 記錄與輸出設定 ====================
    LOGGING_CONFIG = {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'log_file': os.path.join('reports', 'batch_upload.log'),
        'max_bytes': 10 * 1024 * 1024,
        'backup_count': 5,
    }

    PROGRESS_FILE = os.path.join('reports', 'upload_progress.json')

    REPORT_OUTPUT = {
        'save_report': True,
        'report_directory': 'reports',
        'report_format': 'json',
    }

    USE_GRIDFS = True

    DRY_RUN_PREVIEW = {
        'enable_preview': True,
        'output_directory': os.path.join('reports', 'dry_run_previews'),
    }


def validate_config() -> list[str]:
    """檢查設定是否有效並回傳錯誤訊息清單。"""
    errors: list[str] = []

    upload_path = Path(UploadConfig.UPLOAD_DIRECTORY)
    if not upload_path.exists():
        errors.append(f"找不到上傳資料夾：{upload_path}")
    elif not any(upload_path.glob('**/*')):
        errors.append(f"上傳資料夾沒有檔案：{upload_path}")

    required_mongo_keys = ['host', 'port', 'username', 'password', 'database', 'collection']
    for key in required_mongo_keys:
        if key not in UploadConfig.MONGODB_CONFIG:
            errors.append(f"MongoDB 設定缺少欄位：{key}")

    # 如果設定了 LABEL_FOLDERS，就確認對應資料夾是否存在。
    for label, folder_name in UploadConfig.LABEL_FOLDERS.items():
        folder_path = upload_path / folder_name
        if not folder_path.is_dir():
            errors.append(f"找不到標籤「{label}」對應的資料夾：{folder_path}")

    return errors


if __name__ == '__main__':
    print("=" * 60)
    print("CPC 批次上傳工具 - 設定檢查")
    print("=" * 60)

    problems = validate_config()
    if problems:
        print("\n偵測到下列設定問題：")
        for issue in problems:
            print(f"  - {issue}")
    else:
        print("\n設定檢查通過。")
        print(f"上傳資料夾：{UploadConfig.UPLOAD_DIRECTORY}")
        print(f"資料集 UUID：{UploadConfig.DATASET_CONFIG['dataset_UUID']}")
        print(f"MongoDB 集合：{UploadConfig.MONGODB_CONFIG['collection']}")
        print(f"是否使用 GridFS：{UploadConfig.USE_GRIDFS}")
