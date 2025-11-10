"""
狀態管理系統客戶端
與狀態管理系統通信，獲取配置和註冊節點
"""
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class StateManagementClient:
    """狀態管理系統客戶端類"""

    def __init__(self, base_url: str, timeout: int = 10):
        """
        初始化

        Args:
            base_url: 狀態管理系統基礎 URL
            timeout: 請求超時時間（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def register_node(self, node_info: Dict[str, Any]) -> tuple[bool, str]:
        """
        註冊節點

        Args:
            node_info: 節點信息

        Returns:
            (是否成功, 錯誤信息)
        """
        try:
            url = f"{self.base_url}/api/nodes/register"

            response = requests.post(
                url,
                json=node_info,
                timeout=self.timeout
            )

            if response.status_code == 201:
                logger.info(f"節點註冊成功: {node_info.get('node_id')}")
                return True, ""
            else:
                error_msg = f"註冊失敗: {response.status_code}, {response.text}"
                logger.error(error_msg)
                return False, error_msg

        except requests.RequestException as e:
            error_msg = f"註冊節點網絡錯誤: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"註冊節點異常: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_analysis_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取分析配置

        Args:
            config_id: 配置 ID

        Returns:
            配置數據，失敗返回 None
        """
        try:
            url = f"{self.base_url}/api/configs/{config_id}"

            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result.get('data')

            logger.error(f"獲取配置失敗: {config_id}")
            return None

        except Exception as e:
            logger.error(f"獲取配置異常: {e}")
            return None

    def get_mongodb_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取 MongoDB 實例配置

        Args:
            instance_id: 實例 ID

        Returns:
            實例配置，失敗返回 None
        """
        try:
            url = f"{self.base_url}/api/instances/{instance_id}"

            # 需要包含密碼
            response = requests.get(
                url,
                params={'include_password': 'true'},
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result.get('data')

            logger.error(f"獲取實例配置失敗: {instance_id}")
            return None

        except Exception as e:
            logger.error(f"獲取實例配置異常: {e}")
            return None

    def health_check(self) -> bool:
        """
        健康檢查

        Returns:
            是否健康
        """
        try:
            url = f"{self.base_url}/health"

            response = requests.get(url, timeout=5)

            return response.status_code == 200

        except Exception as e:
            logger.error(f"健康檢查失敗: {e}")
            return False

    def wait_for_ready(self, max_retries: int = 30, retry_interval: int = 2) -> bool:
        """
        等待狀態管理系統就緒

        Args:
            max_retries: 最大重試次數
            retry_interval: 重試間隔（秒）

        Returns:
            是否就緒
        """
        import time

        logger.info(f"等待狀態管理系統就緒: {self.base_url}")

        for i in range(max_retries):
            if self.health_check():
                logger.info("狀態管理系統已就緒")
                return True

            logger.debug(f"等待中... ({i + 1}/{max_retries})")
            time.sleep(retry_interval)

        logger.error("狀態管理系統未就緒")
        return False
