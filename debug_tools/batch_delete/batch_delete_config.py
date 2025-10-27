# batch_delete_config.py - 批量刪除工具配置

import os


class DeleteConfig:
    """批量刪除配置類"""

    # ==================== MongoDB 配置 ====================
    MONGODB_CONFIG = {
        'host': 'localhost',
        'port': 27020,
        'username': 'web_ui',
        'password': 'hod2iddfsgsrl',
        'database': 'web_db',
        'collection': 'recordings'
    }

    # ==================== 刪除條件配置 ====================
    # 可以組合多個條件，全部符合才會刪除

    DELETE_CONDITIONS = {
        # 按標籤刪除（留空則不限制）
        # 可選值: 'normal', 'abnormal', 'unknown' 或 None
        'label': None,  # 例如: 'abnormal' 只刪除異常音檔

        # 按 dataset_UUID 刪除（留空則不限制）
        'dataset_UUID': None,  # 例如: 'BATCH_UPLOAD_Dataset'

        # 按上傳來源刪除（留空則不限制）
        # True = 只刪除批量上傳的檔案
        'batch_upload_only': False,

        # 按時間範圍刪除（留空則不限制）
        # 格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'
        'uploaded_before': None,  # 例如: '2025-01-01' 刪除此日期之前的
        'uploaded_after': None,  # 例如: '2024-01-01' 刪除此日期之後的

        # 按設備 ID 刪除（留空則不限制）
        'device_id': None,  # 例如: 'BATCH_UPLOAD_NORMAL'

        # 按 obj_ID 刪除（留空則不限制）
        'obj_ID': None,  # 例如: '88'
    }

    # ==================== 刪除行為配置 ====================
    DELETE_BEHAVIOR = {
        # 是否同時刪除 GridFS 中的檔案
        'delete_gridfs_files': True,

        # 是否使用軟刪除（僅標記為已刪除，不實際移除）
        'soft_delete': False,

        # 軟刪除時的標記欄位
        'soft_delete_field': 'deleted',

        # 是否在刪除前備份記錄到 JSON 檔案
        'backup_before_delete': True,

        # 備份檔案目錄
        'backup_directory': 'delete_backups',

        # 批次大小（一次刪除多少筆記錄）
        'batch_size': 100,

        # 是否顯示刪除進度
        'show_progress': True,
    }

    # ==================== 安全配置 ====================
    SAFETY_CONFIG = {
        # 是否需要二次確認
        'require_confirmation': True,

        # 單次刪除數量上限（0 表示無限制）
        # 防止誤刪大量資料
        'max_delete_count': 0,  # 例如: 1000 最多刪除 1000 筆

        # 是否在預覽模式下顯示前 N 筆記錄詳情
        'preview_sample_size': 10,
    }

    # ==================== 日誌配置 ====================
    LOGGING_CONFIG = {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'log_file': 'batch_delete.log',
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5
    }

    # ==================== 報告輸出 ====================
    REPORT_OUTPUT = {
        'save_report': True,
        'report_directory': 'delete_reports',
    }


# 驗證配置
def validate_delete_config():
    """驗證刪除配置是否正確"""
    errors = []
    warnings = []

    # 檢查 MongoDB 配置
    required_mongo_keys = ['host', 'port', 'username', 'password', 'database', 'collection']
    for key in required_mongo_keys:
        if key not in DeleteConfig.MONGODB_CONFIG:
            errors.append(f"MongoDB 配置缺少 {key}")

    # 檢查是否至少有一個刪除條件
    conditions = DeleteConfig.DELETE_CONDITIONS
    has_condition = any([
        conditions['label'],
        conditions['dataset_UUID'],
        conditions['batch_upload_only'],
        conditions['uploaded_before'],
        conditions['uploaded_after'],
        conditions['device_id'],
        conditions['obj_ID'],
    ])

    if not has_condition:
        warnings.append("⚠️  警告: 沒有設定任何刪除條件，將會刪除所有記錄！")

    # 檢查日期格式
    if conditions['uploaded_before']:
        try:
            from datetime import datetime
            datetime.fromisoformat(conditions['uploaded_before'].replace(' ', 'T'))
        except:
            errors.append(f"日期格式錯誤: uploaded_before = {conditions['uploaded_before']}")

    if conditions['uploaded_after']:
        try:
            from datetime import datetime
            datetime.fromisoformat(conditions['uploaded_after'].replace(' ', 'T'))
        except:
            errors.append(f"日期格式錯誤: uploaded_after = {conditions['uploaded_after']}")

    # 檢查標籤值
    if conditions['label'] and conditions['label'] not in ['normal', 'abnormal', 'unknown']:
        errors.append(f"標籤值錯誤: {conditions['label']}，應為 'normal', 'abnormal' 或 'unknown'")

    return errors, warnings


if __name__ == '__main__':
    """測試配置"""
    print("=" * 60)
    print("批量刪除工具 - 配置檢查")
    print("=" * 60)

    errors, warnings = validate_delete_config()

    if errors:
        print("\n❌ 配置錯誤:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ 配置檢查通過")

    if warnings:
        print("\n⚠️  警告:")
        for warning in warnings:
            print(f"  - {warning}")

    print(f"\nMongoDB 資料庫: {DeleteConfig.MONGODB_CONFIG['database']}")
    print(f"MongoDB 集合: {DeleteConfig.MONGODB_CONFIG['collection']}")
    print(f"\n刪除條件:")
    for key, value in DeleteConfig.DELETE_CONDITIONS.items():
        if value:
            print(f"  - {key}: {value}")

    print(f"\n軟刪除: {'是' if DeleteConfig.DELETE_BEHAVIOR['soft_delete'] else '否'}")
    print(f"刪除 GridFS 檔案: {'是' if DeleteConfig.DELETE_BEHAVIOR['delete_gridfs_files'] else '否'}")
    print(f"刪除前備份: {'是' if DeleteConfig.DELETE_BEHAVIOR['backup_before_delete'] else '否'}")