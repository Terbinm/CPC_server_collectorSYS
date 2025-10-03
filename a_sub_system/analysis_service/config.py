# a_sub_system/analysis_service/config.py - 分析服務統一配置

import os

# ==================== MongoDB 配置 ====================
MONGODB_CONFIG = {
    'host': 'localhost',
    'port': 27020,
    'username': 'web_ui',
    'password': 'hod2iddfsgsrl',
    'database': 'web_db',
    'collection': 'recordings'
}

# ==================== 音訊處理配置 ====================
AUDIO_CONFIG = {
    # 切割參數（參考 V3_multi_dataset）
    'slice_duration': 0.16,  # 切割時長（秒）
    'slice_interval': 0.20,  # 切割間隔（秒）
    'channels': [6],  # 處理的通道列表
    'sample_rate': 16000,  # 採樣率（Hz）
    'min_segment_duration': 0.05  # 最小切片長度（秒）
}

# ==================== LEAF 特徵提取配置 ====================
LEAF_CONFIG = {
    # LEAF 前端參數
    'n_filters': 40,
    'sample_rate': 16000,
    'window_len': 25.0,  # 毫秒
    'window_stride': 10.0,  # 毫秒
    'pcen_compression': True,
    'init_min_freq': 60.0,
    'init_max_freq': 8000.0,

    # 處理參數
    'batch_size': 32,
    'device': 'cpu',  # 強制使用 CPU
    'num_workers': 4,

    # 特徵配置
    'feature_dim_expected': 40,
    'normalize_features': False,
    'feature_dtype': 'float32'
}

# ==================== 分類配置 ====================
CLASSIFICATION_CONFIG = {
    'method': 'rf_model',  # 目前使用隨機分類
    'classes': ['normal', 'abnormal'],
    'normal_probability': 0.7,  # 隨機分類時正常的機率

    # 未來模型配置（預留）
    'model_path': 'models',
    'threshold': 0.5
}

# ==================== 服務配置 ====================
SERVICE_CONFIG = {
    # Change Stream 配置
    'use_change_stream': False,
    'polling_interval': 5,  # 輪詢間隔（秒），當 Change Stream 不可用時

    # 處理配置
    'max_concurrent_tasks': 3,  # 最大並行處理任務數
    'retry_attempts': 3,  # 失敗重試次數
    'retry_delay': 2,  # 重試延遲（秒）

    # 超時配置
    'slice_timeout': 60,  # 切割超時（秒）
    'leaf_timeout': 120,  # LEAF 提取超時（秒）
    'classify_timeout': 30  # 分類超時（秒）
}

# ==================== 日誌配置 ====================
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_file': 'analysis_service.log',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# ==================== 處理步驟定義 ====================
PROCESSING_STEPS = {
    0: {'name': 'Pending', 'description': '等待處理'},
    1: {'name': 'Audio Slicing', 'description': '音訊切割'},
    2: {'name': 'LEAF Features', 'description': 'LEAF 特徵提取'},
    3: {'name': 'Classification', 'description': '分類預測'},
    4: {'name': 'Completed', 'description': '處理完成'}
}

# ==================== GridFS 配置 ====================
# 分析服務使用 GridFS 讀取音頻文件
USE_GRIDFS = True  # 啟用 GridFS 模式

# ==================== 檔案路徑配置（已棄用，保留用於向後相容） ====================
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')

# ==================== 資料庫索引 ====================
DATABASE_INDEXES = [
    'AnalyzeUUID',
    'info_features.device_id',
    'current_step',
    'analysis_status'
]