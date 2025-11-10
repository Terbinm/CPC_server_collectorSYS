"""
MongoDB 處理器
提供 MongoDB 連接和操作功能
"""
import logging
from typing import Dict, Any, List, Optional
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, ConnectionFailure
from config import get_config

logger = logging.getLogger(__name__)


class MongoDBHandler:
    """MongoDB 處理器類"""

    _instance = None
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    def __new__(cls):
        """單例模式"""
        if cls._instance is None:
            cls._instance = super(MongoDBHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化"""
        if self._client is None:
            self._connect()

    def _connect(self):
        """建立 MongoDB 連接"""
        try:
            config = get_config()
            uri = config.get_mongodb_uri()

            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=config.MONGODB_CONFIG['server_selection_timeout_ms']
            )

            # 測試連接
            self._client.admin.command('ping')

            # 獲取資料庫
            self._db = self._client[config.MONGODB_CONFIG['database']]

            logger.info(f"MongoDB 連接成功: {config.MONGODB_CONFIG['database']}")

            # 創建索引
            self._create_indexes()

        except ConnectionFailure as e:
            logger.error(f"MongoDB 連接失敗: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB 初始化錯誤: {e}")
            raise

    def _create_indexes(self):
        """創建必要的索引"""
        try:
            config = get_config()

            # recordings 集合索引
            recordings = self._db[config.COLLECTIONS['recordings']]
            recordings.create_index([('AnalyzeUUID', ASCENDING)], unique=True)
            recordings.create_index([('info_features.dataset_UUID', ASCENDING)])
            recordings.create_index([('info_features.device_id', ASCENDING)])
            recordings.create_index([('info_features.upload_time', DESCENDING)])
            recordings.create_index([('analyze_features.active_analysis_id', ASCENDING)])

            # analysis_configs 集合索引
            configs = self._db[config.COLLECTIONS['analysis_configs']]
            configs.create_index([('analysis_method_id', ASCENDING)])
            configs.create_index([('config_id', ASCENDING)], unique=True)

            # routing_rules 集合索引
            rules = self._db[config.COLLECTIONS['routing_rules']]
            rules.create_index([('rule_id', ASCENDING)], unique=True)
            rules.create_index([('enabled', ASCENDING)])
            rules.create_index([('priority', DESCENDING)])

            # mongodb_instances 集合索引
            instances = self._db[config.COLLECTIONS['mongodb_instances']]
            instances.create_index([('instance_id', ASCENDING)], unique=True)
            instances.create_index([('enabled', ASCENDING)])

            # nodes_status 集合索引（取代 Redis）
            nodes_status = self._db['nodes_status']
            # TTL Index: 自動清理超過 60 秒無心跳的節點
            nodes_status.create_index(
                [('last_heartbeat', ASCENDING)],
                expireAfterSeconds=60
            )
            nodes_status.create_index([('created_at', DESCENDING)])

            # system_metadata 集合索引
            system_metadata = self._db['system_metadata']
            system_metadata.create_index([('_id', ASCENDING)], unique=True)

            logger.info("MongoDB 索引創建完成")

        except Exception as e:
            logger.warning(f"創建索引時發生錯誤: {e}")

    def get_database(self) -> Database:
        """獲取資料庫對象"""
        if self._db is None:
            self._connect()
        return self._db

    def get_collection(self, collection_name: str) -> Collection:
        """獲取集合對象"""
        return self.get_database()[collection_name]

    def close(self):
        """關閉連接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB 連接已關閉")


class MultiMongoDBHandler:
    """多 MongoDB 實例處理器"""

    def __init__(self):
        self._connections: Dict[str, MongoClient] = {}
        self.logger = logging.getLogger(__name__)

    def connect(self, instance_id: str, instance_config: Dict[str, Any]) -> Database:
        """連接到指定的 MongoDB 實例"""
        try:
            # 如果已經存在連接，直接返回
            if instance_id in self._connections:
                client = self._connections[instance_id]
                return client[instance_config['database']]

            # 建立新連接
            uri = f"mongodb://{instance_config['username']}:{instance_config['password']}@" \
                  f"{instance_config['host']}:{instance_config['port']}/admin"

            client = MongoClient(uri, serverSelectionTimeoutMS=5000)

            # 測試連接
            client.admin.command('ping')

            # 保存連接
            self._connections[instance_id] = client

            self.logger.info(f"連接到 MongoDB 實例: {instance_id}")

            return client[instance_config['database']]

        except Exception as e:
            self.logger.error(f"連接 MongoDB 實例 {instance_id} 失敗: {e}")
            raise

    def get_connection(self, instance_id: str) -> Optional[MongoClient]:
        """獲取指定實例的連接"""
        return self._connections.get(instance_id)

    def disconnect(self, instance_id: str):
        """斷開指定實例的連接"""
        if instance_id in self._connections:
            self._connections[instance_id].close()
            del self._connections[instance_id]
            self.logger.info(f"斷開 MongoDB 實例連接: {instance_id}")

    def disconnect_all(self):
        """斷開所有連接"""
        for instance_id in list(self._connections.keys()):
            self.disconnect(instance_id)

    def __del__(self):
        """析構函數，清理連接"""
        self.disconnect_all()


# 全局單例實例
_handler = None


def get_db() -> Database:
    """獲取默認 MongoDB 資料庫"""
    global _handler
    if _handler is None:
        _handler = MongoDBHandler()
    return _handler.get_database()


def get_handler() -> MongoDBHandler:
    """獲取 MongoDB 處理器實例"""
    global _handler
    if _handler is None:
        _handler = MongoDBHandler()
    return _handler
