"""
心跳發送器
定期向狀態管理系統發送心跳
"""
import logging
import time
import requests
from threading import Thread, Event
from typing import Optional

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """心跳發送器類"""

    def __init__(self, state_management_url: str, node_id: str, interval: int = 30):
        """
        初始化

        Args:
            state_management_url: 狀態管理系統 URL
            node_id: 節點 ID
            interval: 心跳間隔（秒）
        """
        self.state_management_url = state_management_url.rstrip('/')
        self.node_id = node_id
        self.interval = interval
        self.running = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self.current_tasks = 0

    def start(self):
        """啟動心跳發送"""
        if self.running:
            logger.warning("心跳發送器已在運行")
            return

        logger.info(f"啟動心跳發送器 (間隔: {self.interval}秒)")
        self.running = True
        self._stop_event.clear()

        while self.running and not self._stop_event.is_set():
            try:
                self._send_heartbeat()
            except Exception as e:
                logger.error(f"發送心跳失敗: {e}")

            # 等待下一次心跳
            self._stop_event.wait(self.interval)

        logger.info("心跳發送器已停止")

    def stop(self):
        """停止心跳發送"""
        logger.info("停止心跳發送器...")
        self.running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def start_in_thread(self) -> Thread:
        """在新線程中啟動"""
        self._thread = Thread(
            target=self.start,
            daemon=True,
            name='HeartbeatSender'
        )
        self._thread.start()
        return self._thread

    def _send_heartbeat(self):
        """發送心跳"""
        try:
            url = f"{self.state_management_url}/api/nodes/heartbeat"

            data = {
                'node_id': self.node_id,
                'current_tasks': self.current_tasks
            }

            response = requests.post(
                url,
                json=data,
                timeout=5
            )

            if response.status_code == 200:
                logger.debug(f"心跳發送成功: {self.node_id}")
            else:
                logger.warning(
                    f"心跳發送失敗: {response.status_code}, "
                    f"{response.text}"
                )

        except requests.RequestException as e:
            logger.error(f"心跳發送網絡錯誤: {e}")
        except Exception as e:
            logger.error(f"心跳發送異常: {e}")

    def update_task_count(self, count: int):
        """更新當前任務數"""
        self.current_tasks = count
