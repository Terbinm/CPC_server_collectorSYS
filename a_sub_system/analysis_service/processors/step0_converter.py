# processors/step0_converter.py - 音訊轉檔處理器

import numpy as np
import pandas as pd
import soundfile as sf
import os
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path
from utils.logger import logger
from config import AUDIO_CONFIG


class AudioConverter:
    """音訊轉檔處理器（支援 CSV 轉 WAV）"""

    def __init__(self):
        """初始化轉檔器"""
        self.sample_rate = AUDIO_CONFIG['sample_rate']
        logger.info(f"AudioConverter 初始化: sample_rate={self.sample_rate}Hz")

    def needs_conversion(self, filepath: str) -> bool:
        """
        判斷檔案是否需要轉檔

        Args:
            filepath: 檔案路徑

        Returns:
            是否需要轉檔
        """
        try:
            file_ext = Path(filepath).suffix.lower()

            # 如果是 WAV 檔案，不需要轉檔
            if file_ext == '.wav':
                return False

            # 如果是 CSV 檔案，需要轉檔
            if file_ext == '.csv':
                return True

            # 其他格式暫不支援
            logger.warning(f"不支援的檔案格式: {file_ext}")
            return False

        except Exception as e:
            logger.error(f"檢查檔案格式失敗 {filepath}: {e}")
            return False

    def convert_to_wav(self, filepath: str) -> Optional[str]:
        """
        將檔案轉換為 WAV 格式

        Args:
            filepath: 原始檔案路徑

        Returns:
            轉換後的 WAV 檔案路徑，或 None（如果失敗或不需轉換）
        """
        try:
            file_ext = Path(filepath).suffix.lower()

            # 如果已經是 WAV，直接返回
            if file_ext == '.wav':
                logger.info(f"檔案已是 WAV 格式，無需轉換: {filepath}")
                return filepath

            # CSV 轉 WAV
            if file_ext == '.csv':
                return self._convert_csv_to_wav(filepath)

            # 其他格式暫不支援
            logger.error(f"不支援的檔案格式: {file_ext}")
            return None

        except Exception as e:
            logger.error(f"轉檔失敗 {filepath}: {e}")
            return None

    def _convert_csv_to_wav(self, csv_path: str) -> Optional[str]:
        """
        將 CSV 檔案轉換為 WAV 格式

        CSV 格式要求：
        - 每一列代表一個時間點的採樣
        - 每一欄代表一個音軌（channel）
        - 數值應為浮點數或整數，範圍在 -1.0 到 1.0 之間（如果超出會自動正規化）

        Args:
            csv_path: CSV 檔案路徑

        Returns:
            轉換後的 WAV 檔案路徑或 None
        """
        try:
            logger.info(f"開始轉換 CSV 到 WAV: {csv_path}")

            # 讀取 CSV 檔案
            df = pd.read_csv(csv_path, header=None)
            logger.debug(f"CSV 資料形狀: {df.shape}")

            # 轉換為 numpy 陣列
            audio_data = df.values.astype(np.float32)

            # 檢查資料形狀
            if audio_data.ndim == 1:
                # 單聲道：轉換為 (n_samples,) 格式
                audio_data = audio_data.flatten()
                n_channels = 1
                n_samples = len(audio_data)
            else:
                # 多聲道：轉換為 (n_samples, n_channels) 格式
                n_samples, n_channels = audio_data.shape

            logger.info(f"音訊資料: {n_samples} 採樣點, {n_channels} 聲道")

            # 檢查並正規化數值範圍
            max_val = np.abs(audio_data).max()
            if max_val > 1.0:
                logger.warning(f"音訊數值超出範圍 (max={max_val:.3f})，進行正規化")
                audio_data = audio_data / max_val

            # 建立臨時 WAV 檔案
            temp_wav = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.wav',
                dir=tempfile.gettempdir()
            )
            temp_wav_path = temp_wav.name
            temp_wav.close()

            # 寫入 WAV 檔案
            sf.write(temp_wav_path, audio_data, self.sample_rate)

            logger.info(f"✓ CSV 轉 WAV 成功: {temp_wav_path}")

            # 返回轉換後的資訊
            return temp_wav_path

        except Exception as e:
            logger.error(f"CSV 轉 WAV 失敗 {csv_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_conversion_info(self, original_path: str, converted_path: str) -> Dict[str, Any]:
        """
        獲取轉檔資訊

        Args:
            original_path: 原始檔案路徑
            converted_path: 轉換後檔案路徑

        Returns:
            轉檔資訊字典
        """
        try:
            original_size = os.path.getsize(original_path) if os.path.exists(original_path) else 0
            converted_size = os.path.getsize(converted_path) if os.path.exists(converted_path) else 0

            # 讀取轉換後的音訊資訊
            audio_info, sr = sf.read(converted_path, frames=0)

            return {
                'original_format': Path(original_path).suffix.lower(),
                'converted_format': '.wav',
                'original_size_bytes': original_size,
                'converted_size_bytes': converted_size,
                'sample_rate': self.sample_rate,
                'converted_path': converted_path
            }

        except Exception as e:
            logger.error(f"獲取轉檔資訊失敗: {e}")
            return {}

    def cleanup_temp_file(self, filepath: str):
        """
        清理臨時檔案

        Args:
            filepath: 要清理的檔案路徑
        """
        try:
            if filepath and os.path.exists(filepath):
                # 只清理臨時目錄中的檔案
                if tempfile.gettempdir() in filepath:
                    os.remove(filepath)
                    logger.debug(f"已清理臨時檔案: {filepath}")
        except Exception as e:
            logger.warning(f"清理臨時檔案失敗 {filepath}: {e}")