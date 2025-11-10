"""
節點狀態模型
使用 MongoDB 存儲節點狀態，取代 Redis
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.mongodb_handler import get_db
from config import get_config

logger = logging.getLogger(__name__)


class NodeStatus:
    """節點狀態類 - 使用 MongoDB 存儲"""

    COLLECTION_NAME = 'nodes_status'

    @staticmethod
    def register_node(node_id: str, node_info: Dict[str, Any]) -> bool:
        """
        註冊節點

        Args:
            node_id: 節點 ID
            node_info: 節點信息

        Returns:
            是否成功
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            now = datetime.utcnow()

            # 使用 upsert 插入或更新
            result = collection.update_one(
                {'_id': node_id},
                {
                    '$set': {
                        'info': node_info,
                        'current_tasks': 0,
                        'last_heartbeat': now,
                        'updated_at': now
                    },
                    '$setOnInsert': {
                        'created_at': now
                    }
                },
                upsert=True
            )

            logger.info(f"節點已註冊: {node_id}")
            return True

        except Exception as e:
            logger.error(f"註冊節點失敗: {e}")
            return False

    @staticmethod
    def update_heartbeat(node_id: str, current_tasks: int = None) -> bool:
        """
        更新節點心跳

        Args:
            node_id: 節點 ID
            current_tasks: 當前任務數（可選）

        Returns:
            是否成功
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            update_data = {
                'last_heartbeat': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }

            if current_tasks is not None:
                update_data['current_tasks'] = current_tasks

            result = collection.update_one(
                {'_id': node_id},
                {'$set': update_data}
            )

            if result.modified_count > 0:
                logger.debug(f"心跳已更新: {node_id}")
                return True
            else:
                logger.warning(f"節點不存在或心跳未更新: {node_id}")
                return False

        except Exception as e:
            logger.error(f"更新心跳失敗 ({node_id}): {e}")
            return False

    @staticmethod
    def is_alive(node_id: str, timeout_seconds: int = 60) -> bool:
        """
        檢查節點是否存活

        Args:
            node_id: 節點 ID
            timeout_seconds: 超時時間（秒）

        Returns:
            是否存活
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            node = collection.find_one({'_id': node_id})

            if not node:
                return False

            last_heartbeat = node.get('last_heartbeat')
            if not last_heartbeat:
                return False

            # 計算心跳時間差
            elapsed = (datetime.utcnow() - last_heartbeat).total_seconds()

            return elapsed <= timeout_seconds

        except Exception as e:
            logger.error(f"檢查節點狀態失敗 ({node_id}): {e}")
            return False

    @staticmethod
    def get_node_info(node_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取節點信息

        Args:
            node_id: 節點 ID

        Returns:
            節點信息，失敗返回 None
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            node = collection.find_one({'_id': node_id})

            if not node:
                return None

            # 判斷狀態
            is_online = NodeStatus.is_alive(node_id)

            # 構建返回數據
            info = node.get('info', {})
            info['node_id'] = node_id
            info['status'] = 'online' if is_online else 'offline'
            info['current_tasks'] = node.get('current_tasks', 0)
            info['last_heartbeat'] = node.get('last_heartbeat')
            info['created_at'] = node.get('created_at')

            return info

        except Exception as e:
            logger.error(f"獲取節點信息失敗 ({node_id}): {e}")
            return None

    @staticmethod
    def get_all_nodes() -> List[Dict[str, Any]]:
        """
        獲取所有節點

        Returns:
            節點列表
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            nodes = []

            for node in collection.find():
                node_id = node.get('_id')

                # 判斷狀態
                is_online = NodeStatus.is_alive(node_id)

                # 構建節點數據
                info = node.get('info', {})
                info['node_id'] = node_id
                info['status'] = 'online' if is_online else 'offline'
                info['current_tasks'] = node.get('current_tasks', 0)
                info['last_heartbeat'] = node.get('last_heartbeat')
                info['created_at'] = node.get('created_at')

                nodes.append(info)

            return nodes

        except Exception as e:
            logger.error(f"獲取所有節點失敗: {e}")
            return []

    @staticmethod
    def unregister_node(node_id: str) -> bool:
        """
        註銷節點

        Args:
            node_id: 節點 ID

        Returns:
            是否成功
        """
        try:
            db = get_db()
            collection = db[NodeStatus.COLLECTION_NAME]

            result = collection.delete_one({'_id': node_id})

            if result.deleted_count > 0:
                logger.info(f"節點已註銷: {node_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"註銷節點失敗 ({node_id}): {e}")
            return False

    @staticmethod
    def get_node_statistics() -> Dict[str, Any]:
        """
        獲取節點統計信息

        Returns:
            統計數據
        """
        try:
            nodes = NodeStatus.get_all_nodes()

            online_count = sum(1 for n in nodes if n.get('status') == 'online')
            offline_count = sum(1 for n in nodes if n.get('status') == 'offline')

            return {
                'total_nodes': len(nodes),
                'online_nodes': online_count,
                'offline_nodes': offline_count,
                'nodes': nodes
            }

        except Exception as e:
            logger.error(f"獲取節點統計失敗: {e}")
            return {
                'total_nodes': 0,
                'online_nodes': 0,
                'offline_nodes': 0,
                'nodes': []
            }
