# main.py - 分析服務主程式 (V2 - RabbitMQ 版本)

import signal
import sys
import uuid
import os
from typing import Dict, Any
from threading import Lock

from config import SERVICE_CONFIG, RABBITMQ_CONFIG, STATE_MANAGEMENT_CONFIG
from utils.logger import logger, analyze_uuid_context
from utils.mongodb_handler import MongoDBHandler
from analysis_pipeline import AnalysisPipeline
from rabbitmq_consumer import RetryableConsumer
from heartbeat_sender import HeartbeatSender
from state_client import StateManagementClient


class AnalysisServiceV2:
    """分析服務主類別 (V2 - RabbitMQ 版本)"""

    def __init__(self):
        """初始化服務"""
        self.is_running = False
        self.node_id = f"analysis_node_{uuid.uuid4().hex[:8]}"

        # 核心組件
        self.mongodb_handler = None
        self.mongodb_connections = {}  # 多實例連接緩存
        self.pipeline = None
        self.rabbitmq_consumer = None
        self.heartbeat_sender = None
        self.state_client = None

        # 任務追蹤
        self.processing_tasks = set()
        self.processing_lock = Lock()
        self.current_task_count = 0

        # 註冊信號處理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("=" * 60)
        logger.info(f"音訊分析服務 V2 初始化 (節點 ID: {self.node_id})")
        logger.info("=" * 60)

    def _signal_handler(self, signum, frame):
        """處理終止信號"""
        logger.info(f"\n收到終止信號 ({signum})，正在關閉服務...")
        self.stop()
        sys.exit(0)

    def initialize(self):
        """初始化所有組件"""
        try:
            # 初始化狀態管理系統客戶端
            logger.info("初始化狀態管理系統客戶端...")
            self.state_client = StateManagementClient(
                STATE_MANAGEMENT_CONFIG['url']
            )

            # 等待狀態管理系統就緒
            if not self.state_client.wait_for_ready():
                logger.error("狀態管理系統未就緒")
                return False

            # 初始化默認 MongoDB 連接
            logger.info("初始化默認 MongoDB 連接...")
            self.mongodb_handler = MongoDBHandler()

            # 初始化分析流程
            logger.info("初始化分析流程...")
            self.pipeline = AnalysisPipeline(self.mongodb_handler)

            # 註冊節點
            logger.info("註冊分析節點...")
            node_info = {
                'node_id': self.node_id,
                'capabilities': [SERVICE_CONFIG['analysis_Method_ID']],
                'version': 'v2.0',
                'max_concurrent_tasks': SERVICE_CONFIG['max_concurrent_tasks'],
                'tags': ['python', 'audio', 'leaf', 'rf']
            }

            success, error = self.state_client.register_node(node_info)
            if not success:
                logger.error(f"節點註冊失敗: {error}")
                return False

            # 初始化心跳發送器
            logger.info("初始化心跳發送器...")
            self.heartbeat_sender = HeartbeatSender(
                STATE_MANAGEMENT_CONFIG['url'],
                self.node_id,
                interval=30
            )

            # 初始化 RabbitMQ 消費者
            logger.info("初始化 RabbitMQ 消費者...")
            self.rabbitmq_consumer = RetryableConsumer(
                RABBITMQ_CONFIG,
                self._process_task
            )

            logger.info("✓ 所有組件初始化完成")
            return True

        except Exception as e:
            logger.error(f"✗ 初始化失敗: {e}", exc_info=True)
            return False

    def start(self):
        """啟動服務"""
        if not self.initialize():
            logger.error("初始化失敗，服務無法啟動")
            return

        self.is_running = True

        try:
            # 啟動心跳發送
            logger.info("啟動心跳發送...")
            self.heartbeat_sender.start_in_thread()

            # 開始監聽
            logger.info("=" * 60)
            logger.info("服務啟動成功，開始監聽任務隊列...")
            logger.info(f"節點 ID: {self.node_id}")
            logger.info("按 Ctrl+C 停止服務")
            logger.info("=" * 60)

            # 啟動 RabbitMQ 消費者（阻塞）
            self.rabbitmq_consumer.start()

        except KeyboardInterrupt:
            logger.info("\n收到中斷信號")
            self.stop()
        except Exception as e:
            logger.error(f"服務運行異常: {e}", exc_info=True)
            self.stop()

    def stop(self):
        """停止服務"""
        if not self.is_running:
            return

        logger.info("正在停止服務...")
        self.is_running = False

        # 停止心跳發送
        if self.heartbeat_sender:
            self.heartbeat_sender.stop()

        # 停止 RabbitMQ 消費者
        if self.rabbitmq_consumer:
            self.rabbitmq_consumer.stop()

        # 清理資源
        if self.pipeline:
            self.pipeline.cleanup()

        if self.mongodb_handler:
            self.mongodb_handler.close()

        # 清理多實例連接
        for instance_id, handler in self.mongodb_connections.items():
            try:
                handler.close()
            except:
                pass

        logger.info("服務已停止")

    def _process_task(self, task_data: Dict[str, Any]) -> bool:
        """
        處理任務

        Args:
            task_data: 任務數據

        Returns:
            是否成功
        """
        task_id = task_data.get('task_id', 'unknown')
        analyze_uuid = task_data.get('analyze_uuid')
        mongodb_instance = task_data.get('mongodb_instance')
        config_id = task_data.get('config_id')

        with analyze_uuid_context(analyze_uuid):
            try:
                logger.info(f"開始處理任務: {task_id}")
                logger.info(f"分析 UUID: {analyze_uuid}")
                logger.info(f"MongoDB 實例: {mongodb_instance}")
                logger.info(f"配置 ID: {config_id}")

                # 更新任務計數
                self._update_task_count(1)

                # 獲取 MongoDB 連接
                mongo_handler = self._get_mongodb_connection(mongodb_instance)
                if not mongo_handler:
                    logger.error(f"無法連接到 MongoDB 實例: {mongodb_instance}")
                    return False

                # 獲取記錄
                record = mongo_handler.get_collection('recordings').find_one({
                    'AnalyzeUUID': analyze_uuid
                })

                if not record:
                    logger.error(f"找不到記錄: {analyze_uuid}")
                    return False

                # 執行分析
                success = self.pipeline.process_record(record)

                if success:
                    logger.info(f"任務處理成功: {task_id}")
                else:
                    logger.error(f"任務處理失敗: {task_id}")

                return success

            except Exception as e:
                logger.error(f"處理任務異常: {e}", exc_info=True)
                return False

            finally:
                # 更新任務計數
                self._update_task_count(-1)

    def _get_mongodb_connection(self, instance_id: str) -> MongoDBHandler:
        """獲取 MongoDB 連接"""
        # 如果是默認實例，使用默認連接
        if instance_id == 'default' or not instance_id:
            return self.mongodb_handler

        # 檢查緩存
        if instance_id in self.mongodb_connections:
            return self.mongodb_connections[instance_id]

        # 從狀態管理系統獲取實例配置
        try:
            instance_config = self.state_client.get_mongodb_instance(instance_id)
            if not instance_config:
                logger.error(f"無法獲取實例配置: {instance_id}")
                return None

            # 創建新連接
            # TODO: 實現多實例 MongoDB 連接
            # 暫時使用默認連接
            logger.warning(f"暫時使用默認 MongoDB 連接: {instance_id}")
            return self.mongodb_handler

        except Exception as e:
            logger.error(f"獲取 MongoDB 連接失敗: {e}")
            return None

    def _update_task_count(self, delta: int):
        """更新當前任務計數"""
        with self.processing_lock:
            self.current_task_count += delta

            # 更新心跳發送器
            if self.heartbeat_sender:
                self.heartbeat_sender.update_task_count(self.current_task_count)


def main():
    """主程式入口"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         音訊分析服務 - Analysis Service V2.0 (RabbitMQ)     ║
    ║                                                          ║
    ║  功能:                                                    ║
    ║  1. 從 RabbitMQ 消費分析任務                              ║
    ║  2. 支援多 MongoDB 實例                                   ║
    ║  3. 向狀態管理系統發送心跳                                 ║
    ║  4. 動態配置管理                                          ║
    ║                                                          ║
    ║  流程:                                                    ║
    ║  - 音訊轉檔 (Step 0)                                      ║
    ║  - 音訊切割 (Step 1)                                      ║
    ║  - LEAF 特徵提取 (Step 2)                                 ║
    ║  - 分類預測 (Step 3)                                      ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # 建立並啟動服務
    service = AnalysisServiceV2()
    service.start()


if __name__ == '__main__':
    main()
