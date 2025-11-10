"""
狀態管理系統配置文件
"""
import os
from typing import Dict, Any

class Config:
    """基礎配置"""

    # Flask 配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'

    # 服務配置
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8000))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # MongoDB 配置
    MONGODB_CONFIG: Dict[str, Any] = {
        'host': os.environ.get('MONGODB_HOST', 'localhost'),
        'port': int(os.environ.get('MONGODB_PORT', 27021)),
        'username': os.environ.get('MONGODB_USERNAME', 'web_ui'),
        'password': os.environ.get('MONGODB_PASSWORD', 'hod2iddfsgsrl'),
        'database': os.environ.get('MONGODB_DATABASE', 'web_db'),
        'auth_source': 'admin',
        'server_selection_timeout_ms': 5000,
    }

    # MongoDB Collections
    COLLECTIONS = {
        'recordings': 'recordings',
        'analysis_configs': 'analysis_configs',
        'routing_rules': 'routing_rules',
        'mongodb_instances': 'mongodb_instances',
    }

    # RabbitMQ 配置
    RABBITMQ_CONFIG: Dict[str, Any] = {
        'host': os.environ.get('RABBITMQ_HOST', 'localhost'),
        'port': int(os.environ.get('RABBITMQ_PORT', 5672)),
        'username': os.environ.get('RABBITMQ_USERNAME', 'admin'),
        'password': os.environ.get('RABBITMQ_PASSWORD', 'rabbitmq_admin_pass'),
        'virtual_host': os.environ.get('RABBITMQ_VHOST', '/'),
    }

    # RabbitMQ 隊列配置
    RABBITMQ_EXCHANGE = 'analysis_tasks_exchange'
    RABBITMQ_QUEUE = 'analysis_tasks_queue'
    RABBITMQ_ROUTING_KEY_PREFIX = 'analysis'
    RABBITMQ_MESSAGE_TTL = 24 * 60 * 60 * 1000  # 24 小時（毫秒）

    # 節點配置
    NODE_HEARTBEAT_INTERVAL = 30  # 秒
    NODE_HEARTBEAT_TIMEOUT = 60   # 秒
    NODE_OFFLINE_THRESHOLD = 120  # 秒

    # 任務配置
    TASK_MONITOR_INTERVAL = 5     # 任務監控間隔（秒）
    TASK_TIMEOUT = 24 * 60 * 60   # 任務超時時間（秒）

    # 日誌配置
    LOG_DIR = 'logs'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 文件上傳配置
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    UPLOAD_EXTENSIONS = {'.pkl', '.pth', '.h5', '.onnx', '.pb'}

    @staticmethod
    def get_mongodb_uri() -> str:
        """獲取 MongoDB 連接 URI"""
        cfg = Config.MONGODB_CONFIG
        return f"mongodb://{cfg['username']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['auth_source']}"

    @staticmethod
    def get_rabbitmq_uri() -> str:
        """獲取 RabbitMQ 連接 URI"""
        cfg = Config.RABBITMQ_CONFIG
        return f"amqp://{cfg['username']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['virtual_host']}"


class DevelopmentConfig(Config):
    """開發環境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """生產環境配置"""
    DEBUG = False
    LOG_LEVEL = 'INFO'


class TestingConfig(Config):
    """測試環境配置"""
    TESTING = True
    DEBUG = True


# 配置字典
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}


def get_config() -> Config:
    """獲取當前配置"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_dict.get(env, DevelopmentConfig)
