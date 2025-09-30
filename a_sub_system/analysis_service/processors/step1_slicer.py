# processors/step1_slicer.py - 音訊切割處理器

import librosa
import numpy as np
from typing import List, Tuple, Dict, Any
from config import AUDIO_CONFIG, UPLOAD_FOLDER
from utils.logger import logger
import os


class AudioSlicer:
    """音訊切割處理器"""
    
    def __init__(self):
        """初始化切割器"""
        self.config = AUDIO_CONFIG
        logger.info(f"AudioSlicer 初始化: duration={self.config['slice_duration']}s, "
                   f"interval={self.config['slice_interval']}s")
    
    def slice_audio(self, filepath: str) -> List[Dict[str, Any]]:
        """
        切割音訊檔案
        
        Args:
            filepath: 音訊檔案路徑
            
        Returns:
            切片資料列表，格式：
            [
                {
                    'selec': 切片編號,
                    'channel': 通道編號,
                    'start': 開始時間(秒),
                    'end': 結束時間(秒),
                    'bottom_freq': 最低頻率(kHz),
                    'top_freq': 最高頻率(kHz)
                },
                ...
            ]
        """
        try:
            # 檢查檔案是否存在
            if not os.path.exists(filepath):
                logger.error(f"檔案不存在: {filepath}")
                return []
            
            logger.info(f"開始切割音訊: {filepath}")
            
            # 載入音訊
            audio, sr = librosa.load(
                filepath,
                sr=self.config['sample_rate'],
                mono=False
            )
            
            # 確保是多通道格式
            if audio.ndim == 1:
                audio = audio.reshape(1, -1)
            
            logger.debug(f"音訊載入成功: shape={audio.shape}, sr={sr}")
            
            # 執行切割
            segments = self._perform_slicing(audio, sr)
            
            logger.info(f"切割完成: 共 {len(segments)} 個切片")
            return segments
            
        except Exception as e:
            logger.error(f"音訊切割失敗 {filepath}: {e}")
            return []
    
    def _perform_slicing(self, audio: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """
        執行實際的切割操作
        
        Args:
            audio: 音訊資料 (channels, samples)
            sr: 採樣率
            
        Returns:
            切片資料列表
        """
        segments = []
        duration = self.config['slice_duration']
        interval = self.config['slice_interval']
        channels = self.config['channels']
        
        # 計算樣本數
        slice_samples = int(duration * sr)
        interval_samples = int(interval * sr)
        
        # 如果沒有指定通道，使用所有通道
        if not channels:
            channels = list(range(audio.shape[0]))
        
        # 對每個通道進行切割
        for channel in channels:
            if channel >= audio.shape[0]:
                logger.warning(f"通道 {channel} 超出範圍，跳過")
                continue
            
            channel_audio = audio[channel]
            
            # 滑動視窗切割
            start_sample = 0
            selec_count = 1
            
            while start_sample + slice_samples <= len(channel_audio):
                end_sample = start_sample + slice_samples
                
                start_time = start_sample / sr
                end_time = end_sample / sr
                
                # 檢查最小長度
                if end_time - start_time >= self.config['min_segment_duration']:
                    segment_info = {
                        'selec': selec_count,
                        'channel': channel,
                        'start': round(start_time, 6),
                        'end': round(end_time, 6),
                        'bottom_freq': 0.002,  # kHz
                        'top_freq': round(sr / 2 / 1000, 3)  # kHz (Nyquist)
                    }
                    segments.append(segment_info)
                    selec_count += 1
                
                start_sample += interval_samples
        
        return segments
    
    def validate_filepath(self, filepath: str) -> bool:
        """
        驗證檔案路徑
        
        Args:
            filepath: 檔案路徑
            
        Returns:
            是否有效
        """
        # 檢查是否為絕對路徑
        if not os.path.isabs(filepath):
            # 嘗試從 UPLOAD_FOLDER 組合路徑
            filepath = os.path.join(UPLOAD_FOLDER, filepath)
        
        return os.path.exists(filepath) and os.path.isfile(filepath)
    
    def get_audio_info(self, filepath: str) -> Dict[str, Any]:
        """
        獲取音訊資訊
        
        Args:
            filepath: 音訊檔案路徑
            
        Returns:
            音訊資訊字典
        """
        try:
            audio, sr = librosa.load(filepath, sr=None, mono=False)
            
            if audio.ndim == 1:
                channels = 1
                duration = len(audio) / sr
            else:
                channels = audio.shape[0]
                duration = audio.shape[1] / sr
            
            return {
                'sample_rate': sr,
                'channels': channels,
                'duration': round(duration, 3),
                'samples': audio.shape[-1] if audio.ndim > 1 else len(audio)
            }
        except Exception as e:
            logger.error(f"獲取音訊資訊失敗 {filepath}: {e}")
            return {}