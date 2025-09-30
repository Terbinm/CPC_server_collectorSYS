# utils/mongodb_handler.py - MongoDB 操作工具

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from typing import Dict, Any, Optional, List
from datetime import datetime
from config import MONGODB_CONFIG, DATABASE_INDEXES
from utils.logger import logger


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
                    {'current_step': 0},
                    {'analysis_status': 'pending'}
                ]
            }
            records = list(self.collection.find(query).limit(limit))
            logger.debug(f"找到 {len(records)} 筆待處理記錄")
            return records
        except Exception as e:
            logger.error(f"查詢待處理記錄失敗: {e}")
            return []
    
    def update_record_step(self, analyze_uuid: str, step: int, 
                          status: str = 'processing', 
                          error_message: Optional[str] = None) -> bool:
        """
        更新記錄的處理步驟
        
        Args:
            analyze_uuid: 記錄 UUID
            step: 當前步驟
            status: 處理狀態
            error_message: 錯誤訊息（如果有）
            
        Returns:
            是否更新成功
        """
        try:
            update_data = {
                'current_step': step,
                'analysis_status': status,
                'updated_at': datetime.utcnow()
            }
            
            if error_message:
                update_data['error_message'] = error_message
            
            result = self.collection.update_one(
                {'AnalyzeUUID': analyze_uuid},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新記錄步驟失敗 {analyze_uuid}: {e}")
            return False
    
    def save_slice_results(self, analyze_uuid: str, features_data: List[Dict]) -> bool:
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
                'processing_stats': {
                    'segments_count': len(features_data),
                    'total_duration': round(sum(fd['end'] - fd['start'] for fd in features_data), 3)
                }
            }
            
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
                          extraction_info: Dict) -> bool:
        """
        儲存 LEAF 特徵
        
        Args:
            analyze_uuid: 記錄 UUID
            features_data: LEAF 特徵資料
            extraction_info: 提取資訊
            
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
                'extraction_info': extraction_info,
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time
            }
            
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
                                   classification_results: Dict) -> bool:
        """
        儲存分類結果
        
        Args:
            analyze_uuid: 記錄 UUID
            classification_results: 分類結果
            
        Returns:
            是否儲存成功
        """
        try:
            current_time = datetime.utcnow()
            
            classify_step = {
                'features_step': 3,
                'features_state': 'completed',
                'features_name': 'Classification',
                'classification_results': classification_results,
                'error_message': None,
                'started_at': current_time,
                'completed_at': current_time
            }
            
            result = self.collection.update_one(
                {'AnalyzeUUID': analyze_uuid},
                {
                    '$push': {'analyze_features': classify_step},
                    '$set': {
                        'current_step': 4,
                        'analysis_status': 'completed',
                        'updated_at': current_time,
                        'analysis_summary': classification_results['summary']
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