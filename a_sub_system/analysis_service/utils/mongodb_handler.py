# utils/mongodb_handler.py - MongoDB 操作工具（加入 Step 0 支援）

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from uuid import uuid4
from copy import deepcopy
from config import MONGODB_CONFIG, DATABASE_INDEXES
from utils.logger import logger


def build_analysis_container() -> Dict[str, Any]:
    """建立 analyze_features 預設結構"""
    return {
        'active_analysis_id': None,
        'latest_analysis_id': None,
        'latest_summary_index': None,  # 1-based index 指向 runs
        'total_runs': 0,
        'last_requested_at': None,
        'last_started_at': None,
        'last_completed_at': None,
        'runs': []
    }


class MongoDBHandler:
    """MongoDB 操作處理器"""

    def __init__(self):
        """初始化 MongoDB 連接"""
        self.config = MONGODB_CONFIG
        self.mongo_client = None
        self.db = None
        self.collection = None
        self._connect()

    def _connect(self):
        """建立 MongoDB 連接"""
        try:
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
            self.db = self.mongo_client[self.config['database']]
            self.collection = self.db[self.config['collection']]

            # 測試連接
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB 連接成功")

            # 建立索引
            self._create_indexes()

        except Exception as e:
            logger.error(f"✗ MongoDB 連接失敗: {e}")
            raise

    def _create_indexes(self):
        """建立資料庫索引"""
        for index_field in DATABASE_INDEXES:
            try:
                self.collection.create_index([(index_field, ASCENDING)])
                logger.debug(f"索引建立成功: {index_field}")
            except Exception as e:
                logger.warning(f"索引建立失敗 {index_field}: {e}")

    def _merge_container_defaults(self, container: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
        """
        將既有 analyze_features 容器補齊必要欄位

        Returns:
            (補齊後容器, 是否需要回寫資料庫)
        """
        merged = build_analysis_container()
        needs_update = False

        if not isinstance(container, dict):
            return merged, True

        for key in ['active_analysis_id', 'latest_analysis_id', 'latest_summary_index']:
            if key in container:
                merged[key] = container.get(key)
            else:
                needs_update = True

        legacy_metadata = container.get('metadata')
        if isinstance(legacy_metadata, dict):
            merged['total_runs'] = legacy_metadata.get('total_runs', merged['total_runs'])
            merged['last_requested_at'] = legacy_metadata.get('last_requested_at')
            merged['last_started_at'] = legacy_metadata.get('last_started_at')
            merged['last_completed_at'] = legacy_metadata.get('last_completed_at')
            needs_update = True
        else:
            for key in ['total_runs', 'last_requested_at', 'last_started_at', 'last_completed_at']:
                if key in container:
                    merged[key] = container.get(key)
                else:
                    needs_update = True

        runs = container.get('runs')
        if isinstance(runs, list):
            normalized_runs = []
            for idx, run in enumerate(runs, start=1):
                if isinstance(run, dict) and 'run_index' not in run:
                    run = dict(run)
                    run['run_index'] = idx
                    needs_update = True
                normalized_runs.append(run)
            merged['runs'] = normalized_runs
        else:
            merged['runs'] = []
            needs_update = True

        if merged['total_runs'] == 0 and merged['runs']:
            merged['total_runs'] = len(merged['runs'])
            needs_update = True

        if merged['latest_summary_index'] is None and merged['runs']:
            for run in reversed(merged['runs']):
                if run.get('analysis_summary'):
                    merged['latest_summary_index'] = run.get('run_index')
                    needs_update = True
                    break

        return merged, needs_update

    def _wrap_legacy_analyze_features(self, record: Dict[str, Any], legacy_value: Any) -> Dict[str, Any]:
        """
        將舊版 list 結構包裝成多 run 容器
        """
        container = build_analysis_container()
        if isinstance(legacy_value, list) and legacy_value:
            legacy_id = f"legacy-{record.get('AnalyzeUUID', uuid4().hex)}"
            summary = record.get('analysis_summary', {}) or {}
            run_index = 1
            legacy_run = {
                'analysis_id': legacy_id,
                'run_index': run_index,
                'analysis_summary': summary,
                'analysis_context': {'imported_from': 'legacy'},
                'steps': legacy_value,
                'requested_at': record.get('created_at'),
                'started_at': record.get('processing_started_at') or record.get('created_at'),
                'completed_at': record.get('updated_at'),
                'error_message': record.get('error_message')
            }
            container['runs'] = [legacy_run]
            container['active_analysis_id'] = None
            container['latest_analysis_id'] = legacy_id
            container['latest_summary_index'] = run_index
            container['total_runs'] = 1
            container['last_requested_at'] = legacy_run.get('requested_at')
            container['last_started_at'] = legacy_run.get('started_at')
            container['last_completed_at'] = legacy_run.get('completed_at')

        return container

    def ensure_analysis_container(self, analyze_uuid: str,
                                  record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        確保 analyze_features 採用最新結構

        Returns:
            正常化後的容器
        """
        if record is None:
            record = self.get_record_by_uuid(analyze_uuid)

        if not record:
            raise ValueError(f"找不到記錄: {analyze_uuid}")

        raw_value = record.get('analyze_features')
        needs_update = False

        if isinstance(raw_value, dict) and 'runs' in raw_value:
            container, needs_update = self._merge_container_defaults(raw_value)
        else:
            container = self._wrap_legacy_analyze_features(record, raw_value)
            needs_update = True

        if needs_update:
            update_doc: Dict[str, Any] = {'$set': {'analyze_features': container}}
            if record.get('analysis_summary') is not None:
                update_doc.setdefault('$unset', {})['analysis_summary'] = ""
            self.collection.update_one({'AnalyzeUUID': analyze_uuid}, update_doc)
            record['analyze_features'] = container

        return container

    def start_analysis_run(self, analyze_uuid: str,
                           request_context: Optional[Dict[str, Any]] = None,
                           record: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        建立新的分析 run, 以支援多次完整分析
        """
        request_context = deepcopy(request_context or {})
        if record is None:
            record = self.get_record_by_uuid(analyze_uuid)

        if not record:
            logger.error(f"建立分析 run 失敗，找不到記錄: {analyze_uuid}")
            return None

        container = self.ensure_analysis_container(analyze_uuid, record)
        existing_runs = container.get('runs', [])

        analysis_id = request_context.get('analysis_id') or f"run_{uuid4().hex}"
        current_time = datetime.utcnow()
        requested_at = request_context.get('requested_at', current_time)
        run_index = len(existing_runs) + 1

        request_context.setdefault('run_index', run_index)

        run_doc = {
            'analysis_id': analysis_id,
            'run_index': run_index,
            'analysis_summary': {},
            'analysis_context': request_context,
            'steps': [],
            'requested_at': requested_at,
            'started_at': current_time,
            'completed_at': None,
            'error_message': None
        }

        update_doc = {
            '$push': {'analyze_features.runs': run_doc},
            '$set': {
                'analysis_status': 'processing',
                'current_step': 0,
                'updated_at': current_time,
                'analyze_features.active_analysis_id': analysis_id,
                'analyze_features.latest_analysis_id': analysis_id,
                'analyze_features.last_requested_at': requested_at,
                'analyze_features.last_started_at': current_time,
                'analyze_features.total_runs': run_index,
                'analyze_features.latest_summary_index': None
            }
        }

        result = self.collection.update_one({'AnalyzeUUID': analyze_uuid}, update_doc)

        if result.modified_count == 0:
            logger.error(f"建立分析 run 失敗: {analyze_uuid}")
            return None

        return {'analysis_id': analysis_id, 'run_index': run_index}

    def try_claim_record(self, analyze_uuid: str) -> bool:
        """
        嘗試認領記錄進行處理(原子操作)

        Returns:
            True: 認領成功,可以處理
            False: 已被其他 Worker 認領
        """
        try:
            result = self.collection.update_one(
                {
                    'AnalyzeUUID': analyze_uuid,
                    'current_step': 0,  # 只更新尚未處理的
                    'analysis_status': {'$in': ['pending', None]}
                },
                {
                    '$set': {
                        'current_step': 1,
                        'analysis_status': 'processing',
                        'processing_started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            # modified_count > 0 表示成功認領
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"認領記錄失敗 {analyze_uuid}: {e}")
            return False

    def find_pending_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        查找待處理的記錄

        Args:
            limit: 最大返回數量

        Returns:
            待處理記錄列表
        """
        try:
            query = {
                '$or': [
                    {'current_step': {'$exists': False}},
                    {'current_step': 0}
                ],
                'analysis_status': {'$nin': ['processing', 'completed', 'error']}
            }
            records = list(self.collection.find(query).limit(limit))
            logger.debug(f"找到 {len(records)} 筆待處理記錄")
            return records
        except Exception as e:
            logger.error(f"查詢待處理記錄失敗: {e}")
            return []

    def update_record_step(self, analyze_uuid: str, step: int,
                           status: str = 'processing',
                           error_message: Optional[str] = None,
                           analysis_id: Optional[str] = None) -> bool:
        """
        更新記錄的處理步驟

        Args:
            analyze_uuid: 記錄 UUID
            step: 當前步驟
            status: 處理狀態
            error_message: 錯誤訊息（如果有）
            analysis_id: 目標分析 run

        Returns:
            是否更新成功
        """
        try:
            current_time = datetime.utcnow()
            update_data = {
                'current_step': step,
                'analysis_status': status,
                'updated_at': current_time
            }

            if error_message:
                update_data['error_message'] = error_message

            update_doc = {'$set': update_data}
            run_updates = {}

            if analysis_id:
                if status == 'error':
                    run_updates['analyze_features.runs.$[run].completed_at'] = current_time
                if error_message:
                    run_updates['analyze_features.runs.$[run].error_message'] = error_message

            if run_updates:
                update_doc['$set'].update(run_updates)
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    update_doc,
                    array_filters=[{'run.analysis_id': analysis_id}]
                )
            else:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    update_doc
                )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"更新記錄步驟失敗 {analyze_uuid}: {e}")
            return False

    def save_conversion_results(self, analyze_uuid: str, conversion_info: Dict,
                                analysis_id: Optional[str] = None,
                                conversion_state: str = 'completed') -> bool:
        """
        儲存轉檔結果（Step 0）

        Args:
            analyze_uuid: 記錄 UUID
            conversion_info: 轉檔資訊

        Returns:
            是否儲存成功
        """
        try:
            current_time = datetime.utcnow()

            conversion_step = {
                'features_step': 0,
                'features_state': conversion_state,
                'features_name': 'Audio Conversion',
                'features_data': [],  # 轉檔步驟無特徵資料
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time,
                'processor_metadata': conversion_info
            }

            if analysis_id:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features.runs.$[run].steps': conversion_step},
                        '$set': {
                            'current_step': 0,
                            'analysis_status': 'converted',
                            'updated_at': current_time,
                            'analyze_features.last_started_at': conversion_info.get('started_at', current_time)
                        }
                    },
                    array_filters=[{'run.analysis_id': analysis_id}]
                )
            else:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features': conversion_step},
                        '$set': {
                            'current_step': 0,
                            'analysis_status': 'converted',
                            'updated_at': current_time
                        }
                    }
                )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"儲存轉檔結果失敗 {analyze_uuid}: {e}")
            return False

    def save_slice_results(self, analyze_uuid: str, features_data: List[Dict],
                           analysis_id: Optional[str] = None) -> bool:
        """
        儲存切割結果

        Args:
            analyze_uuid: 記錄 UUID
            features_data: 切割特徵資料

        Returns:
            是否儲存成功
        """
        try:
            current_time = datetime.utcnow()

            slice_step = {
                'features_step': 1,
                'features_state': 'completed',
                'features_name': 'Audio Slicing',
                'features_data': features_data,
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time,
                'processor_metadata': {
                    'segments_count': len(features_data),
                    'total_duration': round(sum(fd['end'] - fd['start'] for fd in features_data), 3)
                }
            }

            if analysis_id:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features.runs.$[run].steps': slice_step},
                        '$set': {
                            'current_step': 1,
                            'analysis_status': 'sliced',
                            'updated_at': current_time
                        }
                    },
                    array_filters=[{'run.analysis_id': analysis_id}]
                )
            else:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features': slice_step},
                        '$set': {
                            'current_step': 1,
                            'analysis_status': 'sliced',
                            'updated_at': current_time
                        }
                    }
                )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"儲存切割結果失敗 {analyze_uuid}: {e}")
            return False

    def save_leaf_features(self, analyze_uuid: str, features_data: List[Dict],
                           processor_metadata: Dict,
                           analysis_id: Optional[str] = None) -> bool:
        """
        儲存 LEAF 特徵

        Args:
            analyze_uuid: 記錄 UUID
            features_data: LEAF 特徵資料
            processor_metadata: 提取資訊

        Returns:
            是否儲存成功
        """
        try:
            current_time = datetime.utcnow()

            leaf_step = {
                'features_step': 2,
                'features_state': 'completed',
                'features_name': 'LEAF Features',
                'features_data': features_data,
                'processor_metadata': processor_metadata,
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time
            }

            if analysis_id:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features.runs.$[run].steps': leaf_step},
                        '$set': {
                            'current_step': 2,
                            'analysis_status': 'features_extracted',
                            'updated_at': current_time
                        }
                    },
                    array_filters=[{'run.analysis_id': analysis_id}]
                )
            else:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features': leaf_step},
                        '$set': {
                            'current_step': 2,
                            'analysis_status': 'features_extracted',
                            'updated_at': current_time
                        }
                    }
                )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"儲存 LEAF 特徵失敗 {analyze_uuid}: {e}")
            return False

    def save_classification_results(self, analyze_uuid: str,
                                    classification_results: Dict,
                                    analysis_id: Optional[str] = None,
                                    run_index: Optional[int] = None) -> bool:
        """
        儲存分類結果（統一格式）

        Args:
            analyze_uuid: 記錄 UUID
            classification_results: 分類結果 (包含 features_data 和 processor_metadata)

        Returns:
            是否儲存成功
        """
        try:
            current_time = datetime.utcnow()

            # 統一格式：與 Step 0, Step 1, Step 2 一致
            classify_step = {
                'features_step': 3,
                'features_state': 'completed',
                'features_name': 'Classification',
                'features_data': classification_results.get('features_data', []),
                'processor_metadata': classification_results.get('processor_metadata', {}),
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time
            }

            # 從 processor_metadata 提取摘要資訊
            processor_metadata = classification_results.get('processor_metadata', {})

            summary = {
                'final_prediction': processor_metadata.get('final_prediction', 'unknown'),
                'total_segments': processor_metadata.get('total_segments', 0),
                'normal_count': processor_metadata.get('normal_count', 0),
                'abnormal_count': processor_metadata.get('abnormal_count', 0),
                'unknown_count': processor_metadata.get('unknown_count', 0),
                'average_confidence': processor_metadata.get('average_confidence', 0.0),
                'method': processor_metadata.get('method', 'unknown')
            }

            if analysis_id:
                set_fields = {
                    'current_step': 4,
                    'analysis_status': 'completed',
                    'updated_at': current_time,
                    'analyze_features.runs.$[run].analysis_summary': summary,
                    'analyze_features.runs.$[run].completed_at': current_time,
                    'analyze_features.runs.$[run].error_message': None,
                    'analyze_features.last_completed_at': current_time,
                    'analyze_features.active_analysis_id': None,
                    'analysis_summary': summary
                }
                if run_index is not None:
                    set_fields['analyze_features.latest_summary_index'] = run_index

                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features.runs.$[run].steps': classify_step},
                        '$set': set_fields
                    },
                    array_filters=[{'run.analysis_id': analysis_id}]
                )
            else:
                result = self.collection.update_one(
                    {'AnalyzeUUID': analyze_uuid},
                    {
                        '$push': {'analyze_features': classify_step},
                        '$set': {
                            'current_step': 4,
                            'analysis_status': 'completed',
                            'updated_at': current_time,
                            'analysis_summary': summary,
                            'analyze_features.latest_summary_index': 1,
                            'analyze_features.last_completed_at': current_time
                        }
                    }
                )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"儲存分類結果失敗 {analyze_uuid}: {e}")
            return False

    def get_record_by_uuid(self, analyze_uuid: str) -> Optional[Dict]:
        """
        根據 UUID 獲取記錄

        Args:
            analyze_uuid: 記錄 UUID

        Returns:
            記錄資料或 None
        """
        try:
            return self.collection.find_one({'AnalyzeUUID': analyze_uuid})
        except Exception as e:
            logger.error(f"獲取記錄失敗 {analyze_uuid}: {e}")
            return None

    def watch_changes(self):
        """
        監聽 MongoDB Change Stream

        Yields:
            變更事件
        """
        try:
            logger.info("開始監聽 MongoDB Change Stream...")

            # 只監聽插入事件
            pipeline = [
                {'$match': {'operationType': 'insert'}}
            ]

            with self.collection.watch(pipeline) as stream:
                for change in stream:
                    yield change

        except Exception as e:
            logger.error(f"Change Stream 監聽失敗: {e}")
            raise

    def close(self):
        """關閉連接"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB 連接已關閉")
