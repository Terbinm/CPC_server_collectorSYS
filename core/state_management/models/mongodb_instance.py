"""
MongoDB 實例模型
管理多個 MongoDB 實例配置
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
from utils.mongodb_handler import get_db
from config import get_config

logger = logging.getLogger(__name__)


class MongoDBInstance:
    """MongoDB 實例類"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """初始化"""
        if data:
            self.from_dict(data)
        else:
            # 默認值
            self.instance_id = ""
            self.instance_name = ""
            self.description = ""
            self.host = ""
            self.port = 27017
            self.username = ""
            self.password = ""
            self.database = ""
            self.collection = "recordings"
            self.auth_source = "admin"
            self.enabled = True
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    def from_dict(self, data: Dict[str, Any]):
        """從字典加載"""
        self.instance_id = data.get('instance_id', '')
        self.instance_name = data.get('instance_name', '')
        self.description = data.get('description', '')
        self.host = data.get('host', '')
        self.port = data.get('port', 27017)
        self.username = data.get('username', '')
        self.password = data.get('password', '')
        self.database = data.get('database', '')
        self.collection = data.get('collection', 'recordings')
        self.auth_source = data.get('auth_source', 'admin')
        self.enabled = data.get('enabled', True)
        self.created_at = data.get('created_at', datetime.utcnow())
        self.updated_at = data.get('updated_at', datetime.utcnow())
        return self

    def to_dict(self, include_password: bool = True) -> Dict[str, Any]:
        """
        轉換為字典

        Args:
            include_password: 是否包含密碼（默認 True）
        """
        data = {
            'instance_id': self.instance_id,
            'instance_name': self.instance_name,
            'description': self.description,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'database': self.database,
            'collection': self.collection,
            'auth_source': self.auth_source,
            'enabled': self.enabled,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

        if include_password:
            data['password'] = self.password

        return data

    def get_connection_config(self) -> Dict[str, Any]:
        """獲取連接配置"""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'database': self.database,
            'collection': self.collection,
            'auth_source': self.auth_source
        }

    def get_uri(self) -> str:
        """獲取連接 URI"""
        return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.auth_source}"

    def validate(self) -> tuple[bool, str]:
        """驗證數據"""
        if not self.instance_id:
            return False, "缺少 instance_id"

        if not self.instance_name:
            return False, "缺少 instance_name"

        if not self.host:
            return False, "缺少 host"

        if not self.username:
            return False, "缺少 username"

        if not self.password:
            return False, "缺少 password"

        if not self.database:
            return False, "缺少 database"

        return True, ""

    @staticmethod
    def create(instance_data: Dict[str, Any]) -> Optional['MongoDBInstance']:
        """創建新實例配置"""
        try:
            config = get_config()
            db = get_db()
            collection = db[config.COLLECTIONS['mongodb_instances']]

            # 創建實例對象
            instance = MongoDBInstance()
            instance.instance_id = instance_data.get('instance_id', str(uuid.uuid4()))
            instance.instance_name = instance_data['instance_name']
            instance.description = instance_data.get('description', '')
            instance.host = instance_data['host']
            instance.port = instance_data.get('port', 27017)
            instance.username = instance_data['username']
            instance.password = instance_data['password']
            instance.database = instance_data['database']
            instance.collection = instance_data.get('collection', 'recordings')
            instance.auth_source = instance_data.get('auth_source', 'admin')
            instance.enabled = instance_data.get('enabled', True)
            instance.created_at = datetime.utcnow()
            instance.updated_at = datetime.utcnow()

            # 驗證
            valid, error = instance.validate()
            if not valid:
                logger.error(f"實例配置驗證失敗: {error}")
                return None

            # 插入資料庫
            result = collection.insert_one(instance.to_dict())

            if result.inserted_id:
                logger.info(f"實例配置已創建: {instance.instance_id}")
                return instance

            return None

        except Exception as e:
            logger.error(f"創建實例配置失敗: {e}", exc_info=True)
            return None

    @staticmethod
    def get_by_id(instance_id: str) -> Optional['MongoDBInstance']:
        """根據 ID 獲取實例配置"""
        try:
            config = get_config()
            db = get_db()
            collection = db[config.COLLECTIONS['mongodb_instances']]

            data = collection.find_one({'instance_id': instance_id})
            if data:
                return MongoDBInstance(data)

            return None

        except Exception as e:
            logger.error(f"獲取實例配置失敗: {e}")
            return None

    @staticmethod
    def get_all(enabled_only: bool = False) -> List['MongoDBInstance']:
        """獲取所有實例配置"""
        try:
            config = get_config()
            db = get_db()
            collection = db[config.COLLECTIONS['mongodb_instances']]

            query = {'enabled': True} if enabled_only else {}
            instances = []

            for data in collection.find(query).sort('created_at', -1):
                instances.append(MongoDBInstance(data))

            return instances

        except Exception as e:
            logger.error(f"獲取所有實例配置失敗: {e}")
            return []

    @staticmethod
    def update(instance_id: str, update_data: Dict[str, Any]) -> bool:
        """更新實例配置"""
        try:
            config = get_config()
            db = get_db()
            collection = db[config.COLLECTIONS['mongodb_instances']]

            # 更新時間
            update_data['updated_at'] = datetime.utcnow()

            result = collection.update_one(
                {'instance_id': instance_id},
                {'$set': update_data}
            )

            if result.modified_count > 0:
                logger.info(f"實例配置已更新: {instance_id}")

                # 更新配置版本
                from models.config_version import ConfigVersion
                ConfigVersion.increment()

                return True

            return False

        except Exception as e:
            logger.error(f"更新實例配置失敗: {e}")
            return False

    @staticmethod
    def delete(instance_id: str) -> bool:
        """刪除實例配置"""
        try:
            config = get_config()
            db = get_db()
            collection = db[config.COLLECTIONS['mongodb_instances']]

            result = collection.delete_one({'instance_id': instance_id})

            if result.deleted_count > 0:
                logger.info(f"實例配置已刪除: {instance_id}")

                # 更新配置版本
                from models.config_version import ConfigVersion
                ConfigVersion.increment()

                return True

            return False

        except Exception as e:
            logger.error(f"刪除實例配置失敗: {e}")
            return False

    @staticmethod
    def test_connection(instance_id: str) -> tuple[bool, str]:
        """
        測試連接

        Returns:
            (是否成功, 錯誤信息)
        """
        try:
            instance = MongoDBInstance.get_by_id(instance_id)
            if not instance:
                return False, "實例配置不存在"

            # 嘗試連接
            from utils.mongodb_handler import MultiMongoDBHandler
            handler = MultiMongoDBHandler()

            db = handler.connect(instance_id, instance.get_connection_config())

            # 測試 ping
            db.command('ping')

            # 測試查詢
            db[instance.collection].count_documents({}, limit=1)

            handler.disconnect(instance_id)

            logger.info(f"實例連接測試成功: {instance_id}")
            return True, "連接成功"

        except Exception as e:
            error_msg = f"連接失敗: {str(e)}"
            logger.error(f"實例連接測試失敗 ({instance_id}): {e}")
            return False, error_msg
