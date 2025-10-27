# analysis_pipeline.py - 分析流程管理器（加入 Step 0 轉檔）

from typing import Dict, Any, Optional
from datetime import datetime
import os
import traceback
from bson.objectid import ObjectId

from config import SERVICE_CONFIG, USE_GRIDFS
from utils.logger import logger
from utils.mongodb_handler import MongoDBHandler
from processors.step0_converter import AudioConverter
from processors.step1_slicer import AudioSlicer
from processors.step2_leaf import LEAFFeatureExtractor
from processors.step3_classifier import AudioClassifier
from gridfs_handler import AnalysisGridFSHandler


class AnalysisPipeline:
    """分析流程管理器（支援 GridFS + 簡化格式 + Step 0 轉檔）"""

    def __init__(self, mongodb_handler: MongoDBHandler):
        """
        初始化分析流程

        Args:
            mongodb_handler: MongoDB 處理器
        """
        self.mongodb = mongodb_handler
        self.config = SERVICE_CONFIG
        self.use_gridfs = USE_GRIDFS

        # 初始化 GridFS Handler（如果啟用）
        if self.use_gridfs:
            self.gridfs_handler = AnalysisGridFSHandler(mongodb_handler.mongo_client)
            logger.info("✓ GridFS 模式已啟用")
        else:
            self.gridfs_handler = None
            logger.info("✓ 本地檔案模式")

        # 初始化處理器
        try:
            self.converter = AudioConverter()
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
        converted_file_path = None  # 轉檔後的檔案路徑（用於最後清理）

        try:
            logger.info(f"=" * 60)
            logger.info(f"開始處理記錄: {analyze_uuid}")
            logger.info(f"=" * 60)

            # ✅ 先嘗試認領記錄
            if not self.mongodb.try_claim_record(analyze_uuid):
                logger.info(f"記錄已被其他 Worker 處理,跳過: {analyze_uuid}")
                return True  # 不算失敗

            # 檢查記錄是否已處理
            if self._is_already_processed(record):
                logger.info(f"記錄已處理，跳過: {analyze_uuid}")
                return True

            # Step 0: 獲取檔案並判斷是否需要轉檔
            audio_data, temp_file_path = self._get_audio_file(record)
            if audio_data is None and temp_file_path is None:
                self._mark_error(analyze_uuid, "無法獲取音頻檔案")
                return False

            # 判斷是否需要轉檔
            needs_conversion = self.converter.needs_conversion(temp_file_path)

            if needs_conversion:
                if not self._execute_step0(analyze_uuid, temp_file_path):
                    return False

                # 取得轉檔後的檔案路徑
                record_updated = self.mongodb.get_record_by_uuid(analyze_uuid)
                conversion_info = record_updated.get('analyze_features', [{}])[0].get('processor_metadata', {})
                converted_file_path = conversion_info.get('converted_path')

                if not converted_file_path or not os.path.exists(converted_file_path):
                    self._mark_error(analyze_uuid, "轉檔後的檔案不存在")
                    return False

                # 使用轉檔後的檔案繼續處理
                working_file_path = converted_file_path
            else:
                # 不需轉檔，直接使用原始檔案
                working_file_path = temp_file_path

            try:
                # 從 info_features 獲取 target_channel
                info_features = record.get('info_features', {})
                target_channels = info_features.get('target_channel', [])

                # Step 1: 音訊切割（傳入 target_channels）
                if not self._execute_step1(analyze_uuid, working_file_path, target_channels):
                    return False

                # Step 2: LEAF 特徵提取
                if not self._execute_step2(analyze_uuid, working_file_path):
                    return False

                # Step 3: 分類
                if not self._execute_step3(analyze_uuid):
                    return False

                logger.info(f"✓ 記錄處理完成: {analyze_uuid}")
                return True

            finally:
                # 清理原始臨時檔案
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        logger.debug(f"已清理原始臨時檔案: {temp_file_path}")
                    except Exception as e:
                        logger.warning(f"清理原始臨時檔案失敗: {e}")

                # 清理轉檔後的臨時檔案
                if converted_file_path and converted_file_path != temp_file_path:
                    self.converter.cleanup_temp_file(converted_file_path)

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

        if current_step >= 4 or analysis_status == 'completed':
            return True

        return False

    def _get_audio_file(self, record: Dict) -> tuple[Optional[bytes], Optional[str]]:
        """
        獲取音頻檔案（從 GridFS 或本地）

        Args:
            record: MongoDB 記錄

        Returns:
            (音頻數據, 臨時檔案路徑) 元組
        """
        try:
            files = record.get('files', {}).get('raw', {})

            if self.use_gridfs:
                # 從 GridFS 讀取
                file_id = files.get('fileId')
                if not file_id:
                    logger.error("記錄中沒有 GridFS fileId")
                    return None, None

                # 處理不同格式的 ObjectId
                if isinstance(file_id, dict) and '$oid' in file_id:
                    file_id = ObjectId(file_id['$oid'])
                elif isinstance(file_id, str):
                    file_id = ObjectId(file_id)

                logger.info(f"從 GridFS 讀取檔案 (ID: {file_id})")

                # 檢查檔案是否存在
                if not self.gridfs_handler.file_exists(file_id):
                    logger.error(f"GridFS 檔案不存在 (ID: {file_id})")
                    return None, None

                # 下載檔案
                audio_data = self.gridfs_handler.download_file(file_id)
                if not audio_data:
                    logger.error(f"從 GridFS 下載檔案失敗 (ID: {file_id})")
                    return None, None

                # 獲取原始檔案名稱和副檔名
                file_info = self.gridfs_handler.get_file_info(file_id)
                original_filename = file_info.get('filename', 'audio.wav')
                file_extension = os.path.splitext(original_filename)[1] or '.wav'

                # 創建臨時檔案（保留原始副檔名）
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
                temp_file.write(audio_data)
                temp_file.close()

                logger.info(f"✓ 從 GridFS 讀取檔案成功，創建臨時檔案: {temp_file.name}")
                return audio_data, temp_file.name

            else:
                # 從本地檔案系統讀取（向後相容）
                from config import UPLOAD_FOLDER

                info_features = record.get('info_features', {})
                filepath = info_features.get('filepath')

                if not filepath:
                    filename = files.get('filename')
                    if filename:
                        filepath = os.path.join(UPLOAD_FOLDER, filename)

                if filepath and os.path.exists(filepath):
                    logger.info(f"從本地讀取檔案: {filepath}")
                    with open(filepath, 'rb') as f:
                        audio_data = f.read()
                    return audio_data, filepath
                else:
                    logger.error(f"本地檔案不存在: {filepath}")
                    return None, None

        except Exception as e:
            logger.error(f"獲取音頻檔案失敗: {e}")
            logger.error(traceback.format_exc())
            return None, None

    def _execute_step0(self, analyze_uuid: str, filepath: str) -> bool:
        """
        執行 Step 0: 音訊轉檔（CSV -> WAV）

        Args:
            analyze_uuid: 記錄 UUID
            filepath: 原始檔案路徑

        Returns:
            是否成功
        """
        try:
            logger.info(f"[Step 0] 開始音訊轉檔...")
            self.mongodb.update_record_step(analyze_uuid, 0, 'processing')

            # 執行轉檔
            converted_path = self.converter.convert_to_wav(filepath)

            if not converted_path:
                error_msg = "音訊轉檔失敗"
                logger.error(f"[Step 0] {error_msg}")
                self._mark_error(analyze_uuid, error_msg, step=0)
                return False

            # 獲取轉檔資訊
            conversion_info = self.converter.get_conversion_info(filepath, converted_path)

            # 儲存轉檔結果
            success = self.mongodb.save_conversion_results(analyze_uuid, conversion_info)

            if success:
                logger.info(f"[Step 0] ✓ 音訊轉檔完成: {conversion_info.get('original_format')} -> WAV")
                return True
            else:
                logger.error(f"[Step 0] ✗ 儲存轉檔結果失敗")
                return False

        except Exception as e:
            logger.error(f"[Step 0] 執行失敗: {e}")
            self._mark_error(analyze_uuid, f"Step 0 異常: {str(e)}", step=0)
            return False

    def _execute_step1(self, analyze_uuid: str, filepath: str, target_channels: list) -> bool:
        """
        執行 Step 1: 音訊切割

        Args:
            analyze_uuid: 記錄 UUID
            filepath: 音頻檔案路徑（可能是原始檔案或轉檔後檔案）
            target_channels: 目標音軌列表

        Returns:
            是否成功
        """
        try:
            logger.info(f"[Step 1] 開始音訊切割...")
            logger.info(f"[Step 1] 目標音軌: {target_channels if target_channels else '預設'}")
            self.mongodb.update_record_step(analyze_uuid, 1, 'processing')

            # 執行切割（傳入 target_channels）
            segments = self.slicer.slice_audio(filepath, target_channels)

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
        執行 Step 2: LEAF 特徵提取（簡化格式）

        Args:
            analyze_uuid: 記錄 UUID
            filepath: 音頻檔案路徑（可能是轉檔後的臨時檔案）

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

            analyze_features = record.get('analyze_features', [])

            # 找到 Step 1 的結果（features_step == 1）
            slice_step = None
            for feature in analyze_features:
                if feature.get('features_step') == 1:
                    slice_step = feature
                    break

            if not slice_step:
                logger.error(f"[Step 2] 無切割資料")
                return False

            slice_data = slice_step.get('features_data', [])
            if not slice_data:
                logger.error(f"[Step 2] 切割資料為空")
                return False

            # 提取特徵（使用檔案路徑）- 返回簡化格式 [[feat1], [feat2], ...]
            features_data = self.leaf_extractor.extract_features(filepath, slice_data)

            if not features_data:
                error_msg = "LEAF 特徵提取失敗"
                logger.error(f"[Step 2] {error_msg}")
                self._mark_error(analyze_uuid, error_msg, step=2)
                return False

            # 儲存特徵（簡化格式）
            processor_metadata = self.leaf_extractor.get_feature_info()
            success = self.mongodb.save_leaf_features(
                analyze_uuid, features_data, processor_metadata
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
        執行 Step 3: 分類（適配簡化格式）

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

            # 找到 Step 2 的結果（features_step == 2）
            leaf_step = None
            for feature in analyze_features:
                if feature.get('features_step') == 2:
                    leaf_step = feature
                    break

            if not leaf_step:
                logger.error(f"[Step 3] 無 LEAF 特徵資料")
                return False

            # 簡化格式: features_data 直接是 [[feat1], [feat2], ...]
            leaf_data = leaf_step.get('features_data', [])
            if not leaf_data:
                logger.error(f"[Step 3] LEAF 特徵資料為空")
                return False

            # 執行分類（傳入簡化格式）
            classification_results = self.classifier.classify(leaf_data)

            # 儲存分類結果（統一格式）
            success = self.mongodb.save_classification_results(
                analyze_uuid, classification_results
            )

            if success:
                processor_metadata = classification_results.get('processor_metadata', {})
                logger.info(
                    f"[Step 3] ✓ 分類完成: {processor_metadata.get('final_prediction', 'unknown')} "
                    f"(正常: {processor_metadata.get('normal_count', 0)}, "
                    f"異常: {processor_metadata.get('abnormal_count', 0)})"
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
            if hasattr(self, 'gridfs_handler') and self.gridfs_handler:
                self.gridfs_handler.close()
            logger.info("分析流程資源已清理")
        except Exception as e:
            logger.error(f"清理資源失敗: {e}")