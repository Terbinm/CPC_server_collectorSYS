"""
RabbitMQ 處理器
提供 RabbitMQ 連接和操作功能
"""
import logging
import json
import pika
from typing import Dict, Any, Optional, Callable
from config import get_config

logger = logging.getLogger(__name__)


class RabbitMQHandler:
    """RabbitMQ 處理器類"""

    def __init__(self):
        """初始化"""
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._config = get_config()
        self._connect()

    def _connect(self):
        """建立 RabbitMQ 連接"""
        try:
            # 建立連接參數
            credentials = pika.PlainCredentials(
                self._config.RABBITMQ_CONFIG['username'],
                self._config.RABBITMQ_CONFIG['password']
            )

            parameters = pika.ConnectionParameters(
                host=self._config.RABBITMQ_CONFIG['host'],
                port=self._config.RABBITMQ_CONFIG['port'],
                virtual_host=self._config.RABBITMQ_CONFIG['virtual_host'],
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )

            # 建立連接
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()

            logger.info(f"RabbitMQ 連接成功: {self._config.RABBITMQ_CONFIG['host']}")

            # 聲明 Exchange 和 Queue
            self._setup_queues()

        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ 連接失敗: {e}")
            raise
        except Exception as e:
            logger.error(f"RabbitMQ 初始化錯誤: {e}")
            raise

    def _setup_queues(self):
        """設置 Exchange 和 Queue"""
        try:
            # 聲明 Topic Exchange
            self._channel.exchange_declare(
                exchange=self._config.RABBITMQ_EXCHANGE,
                exchange_type='topic',
                durable=True
            )

            # 聲明任務隊列
            self._channel.queue_declare(
                queue=self._config.RABBITMQ_QUEUE,
                durable=True,
                arguments={
                    'x-message-ttl': self._config.RABBITMQ_MESSAGE_TTL,  # 消息 TTL
                }
            )

            # 綁定隊列到 Exchange
            self._channel.queue_bind(
                queue=self._config.RABBITMQ_QUEUE,
                exchange=self._config.RABBITMQ_EXCHANGE,
                routing_key=f"{self._config.RABBITMQ_ROUTING_KEY_PREFIX}.#"
            )

            logger.info("RabbitMQ 隊列設置完成")

        except Exception as e:
            logger.error(f"設置 RabbitMQ 隊列失敗: {e}")
            raise

    def get_channel(self) -> pika.channel.Channel:
        """獲取 Channel"""
        if self._channel is None or self._channel.is_closed:
            self._connect()
        return self._channel

    def publish_task(self, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """
        發布任務到隊列

        Args:
            task_data: 任務數據
            priority: 優先級 (0-9)

        Returns:
            是否成功
        """
        try:
            # 確保連接正常
            if self._channel is None or self._channel.is_closed:
                self._connect()

            # 構建 routing key
            analysis_method_id = task_data.get('analysis_method_id', 'unknown')
            routing_key = f"{self._config.RABBITMQ_ROUTING_KEY_PREFIX}.{analysis_method_id}.{priority}"

            # 發布消息
            self._channel.basic_publish(
                exchange=self._config.RABBITMQ_EXCHANGE,
                routing_key=routing_key,
                body=json.dumps(task_data, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化消息
                    content_type='application/json',
                    priority=priority
                )
            )

            logger.debug(f"任務已發布: {task_data.get('task_id', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"發布任務失敗: {e}")
            return False

    def consume_tasks(self, callback: Callable, prefetch_count: int = 1):
        """
        消費任務

        Args:
            callback: 回調函數，接收 (channel, method, properties, body)
            prefetch_count: 預取數量
        """
        try:
            # 設置 QoS
            self._channel.basic_qos(prefetch_count=prefetch_count)

            # 開始消費
            self._channel.basic_consume(
                queue=self._config.RABBITMQ_QUEUE,
                on_message_callback=callback,
                auto_ack=False  # 手動確認
            )

            logger.info("開始消費任務...")
            self._channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("停止消費任務")
            self._channel.stop_consuming()
        except Exception as e:
            logger.error(f"消費任務失敗: {e}")
            raise

    def ack_message(self, delivery_tag: int):
        """確認消息"""
        try:
            self._channel.basic_ack(delivery_tag=delivery_tag)
            logger.debug(f"消息已確認: {delivery_tag}")

        except Exception as e:
            logger.error(f"確認消息失敗: {e}")

    def nack_message(self, delivery_tag: int, requeue: bool = True):
        """拒絕消息"""
        try:
            self._channel.basic_nack(
                delivery_tag=delivery_tag,
                requeue=requeue
            )
            logger.debug(f"消息已拒絕: {delivery_tag}, requeue={requeue}")

        except Exception as e:
            logger.error(f"拒絕消息失敗: {e}")

    def get_queue_size(self) -> int:
        """獲取隊列大小"""
        try:
            method_frame = self._channel.queue_declare(
                queue=self._config.RABBITMQ_QUEUE,
                passive=True
            )
            return method_frame.method.message_count

        except Exception as e:
            logger.error(f"獲取隊列大小失敗: {e}")
            return 0

    def purge_queue(self) -> bool:
        """清空隊列"""
        try:
            self._channel.queue_purge(queue=self._config.RABBITMQ_QUEUE)
            logger.info("隊列已清空")
            return True

        except Exception as e:
            logger.error(f"清空隊列失敗: {e}")
            return False

    def close(self):
        """關閉連接"""
        try:
            if self._channel and not self._channel.is_closed:
                self._channel.close()

            if self._connection and not self._connection.is_closed:
                self._connection.close()

            logger.info("RabbitMQ 連接已關閉")

        except Exception as e:
            logger.error(f"關閉 RabbitMQ 連接時發生錯誤: {e}")

    def __del__(self):
        """析構函數"""
        self.close()


class RabbitMQPublisher:
    """RabbitMQ 發布者（輕量級，適合快速發布）"""

    def __init__(self):
        """初始化"""
        self._config = get_config()

    def publish(self, task_data: Dict[str, Any], priority: int = 0) -> bool:
        """發布單個任務（自動管理連接）"""
        handler = None
        try:
            handler = RabbitMQHandler()
            result = handler.publish_task(task_data, priority)
            return result

        except Exception as e:
            logger.error(f"發布任務失敗: {e}")
            return False

        finally:
            if handler:
                handler.close()


# 便捷函數
def publish_task(task_data: Dict[str, Any], priority: int = 0) -> bool:
    """
    發布任務到 RabbitMQ

    Args:
        task_data: 任務數據
        priority: 優先級

    Returns:
        是否成功
    """
    publisher = RabbitMQPublisher()
    return publisher.publish(task_data, priority)
