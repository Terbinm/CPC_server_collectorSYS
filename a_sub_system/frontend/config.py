import os

import pytz


class Config:
    """
    Application配置類
    """
    SECRET_KEY = 'your_secret_key'  # 設定密鑰
    SQLALCHEMY_DATABASE_URI = 'sqlite:///schedules.db'  # 僅用於排程資料
    UPLOAD_FOLDER = 'uploads'  # 設定上傳文件的存儲目錄
    TAIPEI_TZ = pytz.timezone('Asia/Taipei')  # 設定時區為台北時區

    # MongoDB 配置（用於錄音數據）

    MONGODB_CONFIG = {
        'host': os.getenv('MONGODB_HOST', 'localhost'),
        'port': int(os.getenv('MONGODB_PORT', '27021')),
        'username': os.getenv('MONGODB_USERNAME', 'web_ui'),
        'password': os.getenv('MONGODB_PASSWORD', 'hod2iddfsgsrl'),
        'database': 'web_db',
        'collection': 'recordings'
    }

    # 資料集配置（參考 V3_multi_dataset）
    DATASET_CONFIG = {
        'dataset_UUID': 'WEB_UI_Dataset',
        'obj_ID': '99',  # Web UI 專用代碼
    }

    # 音頻配置
    AUDIO_CONFIG = {
        'sample_rate': 44100,  # 預設採樣率
        'channels': 1,  # 預設聲道數
        'default_format': 'wav'
    }

    # 資料庫索引設定
    DATABASE_INDEXES = [
        'AnalyzeUUID',
        'info_features.device_id',
        'info_features.upload_time',
        'info_features.file_hash',
        'files.raw.filename'
    ]