# config.py - 批量上傳工具配置

import os


class UploadConfig:
    """批量上傳配置類"""

    # ==================== MongoDB 配置 ====================
    MONGODB_CONFIG = {
        'host': 'localhost',
        'port': 27021,
        'username': 'web_ui',
        'password': 'hod2iddfsgsrl',
        'database': 'web_db',
        'collection': 'recordings'
    }

    # ==================== 上傳資料夾配置 ====================
    # 要上傳的資料夾路徑(請修改為您的實際路徑)
    UPLOAD_DIRECTORY = r"C:\Users\sixsn\PycharmProjects\CPC_server_collectorSYS\debug_tools\batch_upload\mafaulda_upload\mafaulda_data"
    # UPLOAD_DIRECTORY = "/path/to/mafaulda/dataset"  # Linux 範例

    # ==================== 資料夾結構 ====================
    # 資料夾結構範例:
    # UPLOAD_DIRECTORY/
    # ├── normal/
    # │   ├── 12.288.csv
    # │   └── ...
    # ├── imbalance/
    # │   ├── 6g/
    # │   │   ├── 13.9264.csv
    # │   │   └── ...
    # │   └── ...
    # ├── horizontal-misalignment/
    # │   ├── 0.5mm/
    # │   └── ...
    # ├── vertical-misalignment/
    # ├── underhang/
    # └── overhang/

    # 標籤對應資料夾名稱(小寫)
    LABEL_FOLDERS = {
        'normal': 'normal',
        'imbalance': 'imbalance',
        'horizontal_misalignment': 'horizontal-misalignment',
        'vertical_misalignment': 'vertical-misalignment',
        'underhang': 'underhang',
        'overhang': 'overhang',
    }

    # ==================== 支援的檔案格式 ====================
    SUPPORTED_FORMATS = ['.csv']

    # ==================== 資料集配置 ====================
    DATASET_CONFIG = {
        'dataset_UUID': 'mafaulda_batch_upload',
        'obj_ID': '-1',  # 依需求調整成對應的 obj_ID
    }

    # ==================== 分析服務配置 ====================
    ANALYSIS_CONFIG = {
        'target_channel': [7]
    }

    # ==================== CSV 解析配置 ====================
    CSV_CONFIG = {
        'sample_rate_hz': 51200,  # 依據 MAFAULDA 數據手冊
        'expected_channels': 8,  # 預期感測器數量(資料列欄位數)
    }

    # ==================== 上傳行為配置 ====================
    UPLOAD_BEHAVIOR = {
        'skip_existing': True,  # 是否跳過已存在的檔案(根據檔案雜湊值判斷)
        'check_duplicates': True,  # 是否檢查重複檔案
        'concurrent_uploads': 3,  # 並行上傳數量(1 表示單線程)
        'retry_attempts': 3,  # 失敗重試次數
        'retry_delay': 2,  # 重試延遲(秒)
        'per_label_limit': 10,  # 限制每個 label 上傳數量, 0 為不限制
    }

    # ==================== 看不懂別動 ====================
    # ===================================================
    # ==================== 看不懂別動 ====================

    # ==================== 日誌配置 ====================
    LOGGING_CONFIG = {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'log_file': os.path.join('reports', 'batch_upload.log'),
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5
    }

    # ==================== 進度追蹤 ====================
    PROGRESS_FILE = os.path.join('reports', 'upload_progress.json')  # 進度記錄檔案

    # ==================== 報告輸出 ====================
    REPORT_OUTPUT = {
        'save_report': True,
        'report_directory': 'reports',
        'report_format': 'json',  # json, csv, txt
    }

    # ==================== GridFS 配置 ====================
    USE_GRIDFS = True  # 使用 GridFS 儲存檔案

    # ==================== Dry Run 預覽輸出 ====================
    DRY_RUN_PREVIEW = {
        'enable_preview': True,
        'output_directory': os.path.join('reports', 'dry_run_previews')
    }


# 驗證配置
def validate_config():
    """驗證配置是否正確"""
    errors = []

    # 檢查上傳資料夾
    if not os.path.exists(UploadConfig.UPLOAD_DIRECTORY):
        errors.append(f"上傳資料夾不存在: {UploadConfig.UPLOAD_DIRECTORY}")

    # 檢查 MongoDB 配置
    required_mongo_keys = ['host', 'port', 'username', 'password', 'database', 'collection']
    for key in required_mongo_keys:
        if key not in UploadConfig.MONGODB_CONFIG:
            errors.append(f"MongoDB 配置缺少 {key}")

    # 檢查標籤資料夾
    if UploadConfig.LABEL_FOLDERS:
        for label, folder_name in UploadConfig.LABEL_FOLDERS.items():
            folder_path = os.path.join(UploadConfig.UPLOAD_DIRECTORY, folder_name)
            if not os.path.isdir(folder_path):
                errors.append(f"標籤資料夾不存在: {folder_path}")

    return errors


if __name__ == '__main__':
    """測試配置"""
    print("=" * 60)
    print("批量上傳工具 - 配置檢查")
    print("=" * 60)

    errors = validate_config()

    if errors:
        print("\n❌ 配置錯誤:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ 配置檢查通過")
        print(f"\n上傳資料夾: {UploadConfig.UPLOAD_DIRECTORY}")
        print(f"MongoDB 資料庫: {UploadConfig.MONGODB_CONFIG['database']}")
        print(f"MongoDB 集合: {UploadConfig.MONGODB_CONFIG['collection']}")
        print(f"使用 GridFS: {'是' if UploadConfig.USE_GRIDFS else '否'}")
