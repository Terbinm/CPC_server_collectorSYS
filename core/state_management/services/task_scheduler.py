"""
任務調度器
監聽 MongoDB 實例的新資料，根據路由規則創建並發送任務到 RabbitMQ
"""
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any
from threading import Thread
import pymongo

from models.routing_rule import RoutingRule
from models.mongodb_instance import MongoDBInstance
from models.analysis_config import AnalysisConfig
from utils.mongodb_handler import MultiMongoDBHandler
from utils.rabbitmq_handler import publish_task
from config import get_config

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任務調度器類"""

    def __init__(self):
        """初始化"""
        self.config = get_config()
        self.mongo_handler = MultiMongoDBHandler()
        self.running = False
        self.watchers: Dict[str, Thread] = {}

    def start(self):
        """啟動調度器"""
        try:
            logger.info("啟動任務調度器...")
            self.running = True

            # 獲取所有啟用的 MongoDB 實例
            instances = MongoDBInstance.get_all(enabled_only=True)

            if not instances:
                logger.warning("沒有啟用的 MongoDB 實例")
                return

            # 為每個實例啟動一個監聽線程
            for instance in instances:
                self._start_watcher(instance)

            logger.info(f"任務調度器已啟動，監聽 {len(instances)} 個實例")

            # 保持運行
            while self.running:
                time.sleep(10)

                # 檢查並重啟失敗的監聽器
                self._check_watchers(instances)

        except KeyboardInterrupt:
            logger.info("任務調度器收到停止信號")
            self.stop()
        except Exception as e:
            logger.error(f"任務調度器錯誤: {e}", exc_info=True)
            self.stop()

    def stop(self):
        """停止調度器"""
        logger.info("停止任務調度器...")
        self.running = False

        # 等待所有監聽線程結束
        for instance_id, thread in self.watchers.items():
            if thread.is_alive():
                logger.info(f"等待監聽器停止: {instance_id}")
                thread.join(timeout=5)

        # 斷開所有 MongoDB 連接
        self.mongo_handler.disconnect_all()

        logger.info("任務調度器已停止")

    def _start_watcher(self, instance: MongoDBInstance):
        """啟動單個實例的監聽器"""
        try:
            thread = Thread(
                target=self._watch_instance,
                args=(instance,),
                daemon=True,
                name=f"Watcher-{instance.instance_id}"
            )
            thread.start()
            self.watchers[instance.instance_id] = thread

            logger.info(f"已啟動監聽器: {instance.instance_id}")

        except Exception as e:
            logger.error(f"啟動監聽器失敗 ({instance.instance_id}): {e}")

    def _watch_instance(self, instance: MongoDBInstance):
        """監聽單個 MongoDB 實例"""
        instance_id = instance.instance_id
        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                logger.info(f"開始監聽實例: {instance_id}")

                # 連接到 MongoDB
                db = self.mongo_handler.connect(
                    instance_id,
                    instance.get_connection_config()
                )
                collection = db[instance.collection]

                # 嘗試使用 Change Stream
                try:
                    self._watch_with_change_stream(instance_id, collection)
                except pymongo.errors.OperationFailure as e:
                    logger.warning(f"Change Stream 不可用 ({instance_id}): {e}")
                    # 降級為輪詢模式
                    self._watch_with_polling(instance_id, collection)

            except Exception as e:
                retry_count += 1
                logger.error(
                    f"監聽實例失敗 ({instance_id}), "
                    f"重試 {retry_count}/{max_retries}: {e}"
                )
                time.sleep(5 * retry_count)  # 指數退避

        if retry_count >= max_retries:
            logger.error(f"監聽器達到最大重試次數，停止監聽: {instance_id}")

    def _watch_with_change_stream(self, instance_id: str, collection):
        """使用 Change Stream 監聽"""
        logger.info(f"使用 Change Stream 監聽: {instance_id}")

        # 只監聽插入操作
        pipeline = [{'$match': {'operationType': 'insert'}}]

        with collection.watch(pipeline, full_document='updateLookup') as stream:
            for change in stream:
                if not self.running:
                    break

                try:
                    # 獲取新插入的文檔
                    document = change.get('fullDocument')
                    if document:
                        self._process_new_record(instance_id, document)

                except Exception as e:
                    logger.error(f"處理變更事件失敗 ({instance_id}): {e}")

    def _watch_with_polling(self, instance_id: str, collection):
        """使用輪詢模式監聽"""
        logger.info(f"使用輪詢模式監聽: {instance_id}")

        last_check_time = datetime.utcnow()
        poll_interval = self.config.TASK_MONITOR_INTERVAL

        while self.running:
            try:
                # 查找自上次檢查以來的新記錄
                new_records = collection.find({
                    'info_features.upload_time': {'$gt': last_check_time}
                }).sort('info_features.upload_time', 1)

                for record in new_records:
                    self._process_new_record(instance_id, record)

                # 更新檢查時間
                last_check_time = datetime.utcnow()

                # 等待下一次輪詢
                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"輪詢失敗 ({instance_id}): {e}")
                time.sleep(poll_interval)

    def _process_new_record(self, instance_id: str, record: Dict[str, Any]):
        """處理新記錄"""
        try:
            analyze_uuid = record.get('AnalyzeUUID')
            info_features = record.get('info_features', {})

            if not analyze_uuid or not info_features:
                logger.warning(f"記錄缺少必要字段: {record.get('_id')}")
                return

            logger.info(f"發現新記錄: {analyze_uuid} (實例: {instance_id})")

            # 匹配路由規則
            matching_rules = RoutingRule.find_matching_rules(info_features)

            if not matching_rules:
                logger.info(f"沒有匹配的路由規則: {analyze_uuid}")
                return

            logger.info(
                f"找到 {len(matching_rules)} 個匹配規則: {analyze_uuid}"
            )

            # 為每個匹配的規則創建任務
            for rule in matching_rules:
                self._create_tasks_for_rule(
                    instance_id,
                    analyze_uuid,
                    rule,
                    info_features
                )

        except Exception as e:
            logger.error(f"處理新記錄失敗: {e}", exc_info=True)

    def _create_tasks_for_rule(
        self,
        instance_id: str,
        analyze_uuid: str,
        rule: RoutingRule,
        info_features: Dict[str, Any]
    ):
        """為規則創建任務"""
        try:
            # 遍歷規則的所有 actions
            for action in rule.actions:
                analysis_method_id = action['analysis_method_id']
                config_id = action['config_id']
                target_instance = action.get('mongodb_instance', instance_id)

                # 獲取配置
                config = AnalysisConfig.get_by_id(config_id)
                if not config:
                    logger.warning(f"配置不存在: {config_id}")
                    continue

                if not config.enabled:
                    logger.info(f"配置已禁用: {config_id}")
                    continue

                # 創建任務
                task_data = {
                    'task_id': str(uuid.uuid4()),
                    'mongodb_instance': target_instance,
                    'analyze_uuid': analyze_uuid,
                    'analysis_method_id': analysis_method_id,
                    'config_id': config_id,
                    'priority': rule.priority,
                    'created_at': datetime.utcnow().isoformat(),
                    'retry_count': 0,
                    'metadata': {
                        'rule_id': rule.rule_id,
                        'rule_name': rule.rule_name,
                        'source_instance': instance_id
                    }
                }

                # 發送到 RabbitMQ
                success = publish_task(task_data, priority=rule.priority)

                if success:
                    logger.info(
                        f"任務已發送: {task_data['task_id']} "
                        f"(方法: {analysis_method_id}, 配置: {config_id})"
                    )
                else:
                    logger.error(f"任務發送失敗: {task_data['task_id']}")

        except Exception as e:
            logger.error(f"創建任務失敗: {e}", exc_info=True)

    def _check_watchers(self, instances: List[MongoDBInstance]):
        """檢查並重啟失敗的監聽器"""
        try:
            for instance in instances:
                instance_id = instance.instance_id

                # 檢查監聽器是否存在且運行中
                if instance_id not in self.watchers or \
                   not self.watchers[instance_id].is_alive():

                    logger.warning(f"監聽器已停止，嘗試重啟: {instance_id}")
                    self._start_watcher(instance)

        except Exception as e:
            logger.error(f"檢查監聽器失敗: {e}")
