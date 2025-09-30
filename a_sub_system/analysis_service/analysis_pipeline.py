# analysis_pipeline.py - 分析流程管理器

from typing import Dict, Any, Optional
from datetime import datetime
import os
import traceback

from config import SERVICE_CONFIG, UPLOAD_FOLDER
from utils.logger import logger
from utils.mongodb_handler import MongoDBHandler
from processors.step1_slicer import AudioSlicer
from processors.step2_leaf import LEAFFeatureExtractor
from processors.step3_classifier import AudioClassifier


class AnalysisPipeline:
    """分析流程管理器"""
    
    def __init__(self, mongodb_handler: MongoDBHandler):
        """
        初始化分析流程
        
        Args:
            mongodb_handler: MongoDB 處理器
        """
        self.mongodb = mongodb_handler
        self.config = SERVICE_CONFIG
        
        # 初始化處理器
        try:
            self.slicer = AudioSlicer()
            self.leaf_extractor = LEAFFeatureExtractor()
            self.classifier = AudioClassifier()
            logger.info("✓ 所有處理器初始化成功")
        except Exception as e:
            logger.error(f"✗ 處理器初始化失敗: {e}")
            raise
    
    def process_record(self, record: Dict[str, Any]) -> bool:
        """
        處理單一記錄的完整流程
        
        Args:
            record: MongoDB 記錄
            
        Returns:
            是否處理成功
        """
        analyze_uuid = record.get('AnalyzeUUID', 'UNKNOWN')
        
        try:
            logger.info(f"=" * 60)
            logger.info(f"開始處理記錄: {analyze_uuid}")
            logger.info(f"=" * 60)
            
            # 檢查記錄是否已處理
            if self._is_already_processed(record):
                logger.info(f"記錄已處理，跳過: {analyze_uuid}")
                return True
            
            # Step 0: 獲取檔案路徑
            filepath = self._get_filepath(record)
            if not filepath:
                self._mark_error(analyze_uuid, "無法獲取檔案路徑")
                return False
            
            # Step 1: 音訊切割
            if not self._execute_step1(analyze_uuid, filepath):
                return False
            
            # Step 2: LEAF 特徵提取
            if not self._execute_step2(analyze_uuid, filepath):
                return False
            
            # Step 3: 分類
            if not self._execute_step3(analyze_uuid):
                return False
            
            logger.info(f"✓ 記錄處理完成: {analyze_uuid}")
            return True
            
        except Exception as e:
            logger.error(f"✗ 記錄處理失敗 {analyze_uuid}: {e}")
            logger.error(traceback.format_exc())
            self._mark_error(analyze_uuid, f"處理異常: {str(e)}")
            return False
    
    def _is_already_processed(self, record: Dict) -> bool:
        """
        檢查記錄是否已處理
        
        Args:
            record: MongoDB 記錄
            
        Returns:
            是否已處理
        """
        current_step = record.get('current_step', 0)
        analysis_status = record.get('analysis_status', '')
        
        # 如果 current_step >= 4 或 status 為 completed，視為已處理
        if current_step >= 4 or analysis_status == 'completed':
            return True
        
        return False
    
    def _get_filepath(self, record: Dict) -> Optional[str]:
        """
        獲取音訊檔案路徑
        
        Args:
            record: MongoDB 記錄
            
        Returns:
            檔案路徑或 None
        """
        try:
            # 嘗試從不同位置獲取檔案路徑
            info_features = record.get('info_features', {})
            files = record.get('files', {}).get('raw', {})
            
            # 優先使用 info_features.filepath
            filepath = info_features.get('filepath')
            
            # 如果沒有，嘗試從 filename 組合
            if not filepath:
                filename = files.get('filename')
                if filename:
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            # 驗證檔案存在
            if filepath and os.path.exists(filepath):
                logger.debug(f"檔案路徑: {filepath}")
                return filepath
            else:
                logger.error(f"檔案不存在: {filepath}")
                return None
                
        except Exception as e:
            logger.error(f"獲取檔案路徑失敗: {e}")
            return None
    
    def _execute_step1(self, analyze_uuid: str, filepath: str) -> bool:
        """
        執行 Step 1: 音訊切割
        
        Args:
            analyze_uuid: 記錄 UUID
            filepath: 音訊檔案路徑
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"[Step 1] 開始音訊切割...")
            self.mongodb.update_record_step(analyze_uuid, 1, 'processing')
            
            # 執行切割
            segments = self.slicer.slice_audio(filepath)
            
            if not segments:
                error_msg = "音訊切割失敗或無有效切片"
                logger.error(f"[Step 1] {error_msg}")
                self._mark_error(analyze_uuid, error_msg, step=1)
                return False
            
            # 儲存切割結果
            success = self.mongodb.save_slice_results(analyze_uuid, segments)
            
            if success:
                logger.info(f"[Step 1] ✓ 音訊切割完成: {len(segments)} 個切片")
                return True
            else:
                logger.error(f"[Step 1] ✗ 儲存切割結果失敗")
                return False
                
        except Exception as e:
            logger.error(f"[Step 1] 執行失敗: {e}")
            self._mark_error(analyze_uuid, f"Step 1 異常: {str(e)}", step=1)
            return False
    
    def _execute_step2(self, analyze_uuid: str, filepath: str) -> bool:
        """
        執行 Step 2: LEAF 特徵提取
        
        Args:
            analyze_uuid: 記錄 UUID
            filepath: 音訊檔案路徑
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"[Step 2] 開始 LEAF 特徵提取...")
            self.mongodb.update_record_step(analyze_uuid, 2, 'processing')
            
            # 獲取切割結果
            record = self.mongodb.get_record_by_uuid(analyze_uuid)
            if not record:
                logger.error(f"[Step 2] 無法獲取記錄")
                return False
            
            # 從 analyze_features 中獲取切割資料
            analyze_features = record.get('analyze_features', [])
            if not analyze_features:
                logger.error(f"[Step 2] 無切割資料")
                return False
            
            slice_data = analyze_features[0].get('features_data', [])
            if not slice_data:
                logger.error(f"[Step 2] 切割資料為空")
                return False
            
            # 提取特徵
            features_data = self.leaf_extractor.extract_features(filepath, slice_data)
            
            if not features_data:
                error_msg = "LEAF 特徵提取失敗"
                logger.error(f"[Step 2] {error_msg}")
                self._mark_error(analyze_uuid, error_msg, step=2)
                return False
            
            # 儲存特徵
            extraction_info = self.leaf_extractor.get_feature_info()
            success = self.mongodb.save_leaf_features(
                analyze_uuid, features_data, extraction_info
            )
            
            if success:
                logger.info(f"[Step 2] ✓ LEAF 特徵提取完成: {len(features_data)} 個特徵")
                return True
            else:
                logger.error(f"[Step 2] ✗ 儲存 LEAF 特徵失敗")
                return False
                
        except Exception as e:
            logger.error(f"[Step 2] 執行失敗: {e}")
            self._mark_error(analyze_uuid, f"Step 2 異常: {str(e)}", step=2)
            return False
    
    def _execute_step3(self, analyze_uuid: str) -> bool:
        """
        執行 Step 3: 分類
        
        Args:
            analyze_uuid: 記錄 UUID
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"[Step 3] 開始分類...")
            self.mongodb.update_record_step(analyze_uuid, 3, 'processing')
            
            # 獲取 LEAF 特徵
            record = self.mongodb.get_record_by_uuid(analyze_uuid)
            if not record:
                logger.error(f"[Step 3] 無法獲取記錄")
                return False
            
            analyze_features = record.get('analyze_features', [])
            if len(analyze_features) < 2:
                logger.error(f"[Step 3] 無 LEAF 特徵資料")
                return False
            
            leaf_data = analyze_features[1].get('features_data', [])
            if not leaf_data:
                logger.error(f"[Step 3] LEAF 特徵資料為空")
                return False
            
            # 執行分類
            classification_results = self.classifier.classify(leaf_data)
            
            # 儲存分類結果
            success = self.mongodb.save_classification_results(
                analyze_uuid, classification_results
            )
            
            if success:
                summary = classification_results.get('summary', {})
                logger.info(
                    f"[Step 3] ✓ 分類完成: {summary.get('final_prediction', 'unknown')} "
                    f"(正常: {summary.get('normal_count', 0)}, "
                    f"異常: {summary.get('abnormal_count', 0)})"
                )
                return True
            else:
                logger.error(f"[Step 3] ✗ 儲存分類結果失敗")
                return False
                
        except Exception as e:
            logger.error(f"[Step 3] 執行失敗: {e}")
            self._mark_error(analyze_uuid, f"Step 3 異常: {str(e)}", step=3)
            return False
    
    def _mark_error(self, analyze_uuid: str, error_message: str, step: int = 0):
        """
        標記記錄為錯誤狀態
        
        Args:
            analyze_uuid: 記錄 UUID
            error_message: 錯誤訊息
            step: 失敗的步驟
        """
        try:
            self.mongodb.update_record_step(
                analyze_uuid, step, 'error', error_message
            )
            logger.error(f"已標記錯誤: {analyze_uuid} - {error_message}")
        except Exception as e:
            logger.error(f"標記錯誤失敗: {e}")
    
    def cleanup(self):
        """清理資源"""
        try:
            if hasattr(self, 'leaf_extractor'):
                self.leaf_extractor.cleanup()
            logger.info("分析流程資源已清理")
        except Exception as e:
            logger.error(f"清理資源失敗: {e}")