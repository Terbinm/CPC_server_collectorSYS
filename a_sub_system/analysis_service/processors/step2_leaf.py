# processors/step2_leaf.py - LEAF 特徵提取器（簡化版）

import torch
import torch.nn as nn
import numpy as np
import librosa
from typing import List, Dict, Any, Optional
from speechbrain.lobes.features import Leaf
from config import LEAF_CONFIG, AUDIO_CONFIG, UPLOAD_FOLDER
from utils.logger import logger
import os


class LEAFFeatureExtractor:
    """LEAF 特徵提取器"""

    def __init__(self):
        """初始化 LEAF 提取器"""
        self.config = LEAF_CONFIG
        self.device = torch.device(self.config['device'])
        self.model = self._initialize_leaf_model()

        logger.info(f"LEAF 提取器初始化成功 (device={self.device})")

    def _initialize_leaf_model(self) -> nn.Module:
        """初始化 LEAF 模型"""
        try:
            leaf_model = Leaf(
                out_channels=self.config['n_filters'],
                window_len=self.config['window_len'],
                window_stride=self.config['window_stride'],
                sample_rate=self.config['sample_rate'],
                min_freq=self.config['init_min_freq'],
                max_freq=self.config['init_max_freq'],
                use_pcen=self.config['pcen_compression'],
                learnable_pcen=True,
                in_channels=1
            )

            leaf_model = leaf_model.to(self.device)
            leaf_model.eval()

            logger.debug(f"LEAF 模型參數數量: {self._count_parameters(leaf_model)}")
            return leaf_model

        except Exception as e:
            logger.error(f"LEAF 模型初始化失敗: {e}")
            raise

    def _count_parameters(self, model: nn.Module) -> int:
        """計算模型參數數量"""
        return sum(p.numel() for p in model.parameters() if p.requires_grad)

    def extract_features(self, filepath: str, segments: List[Dict]) -> List[List[float]]:
        """
        提取所有切片的 LEAF 特徵

        Args:
            filepath: 音訊檔案路徑
            segments: 切片資訊列表

        Returns:
            純特徵向量列表 [[feat1], [feat2], ...]
        """
        try:
            if not segments:
                logger.warning(f"沒有切片資料: {filepath}")
                return []

            logger.info(f"開始提取 LEAF 特徵: {len(segments)} 個切片")

            features_data = []

            # 批次處理切片
            for i in range(0, len(segments), self.config['batch_size']):
                batch_segments = segments[i:i + self.config['batch_size']]
                batch_features = self._extract_batch(filepath, batch_segments)
                features_data.extend(batch_features)

            logger.info(f"LEAF 特徵提取完成: {len(features_data)} 個特徵")
            return features_data

        except Exception as e:
            logger.error(f"LEAF 特徵提取失敗 {filepath}: {e}")
            return []

    def _extract_batch(self, filepath: str, segments: List[Dict]) -> List[List[float]]:
        """
        批次提取特徵

        Args:
            filepath: 音訊檔案路徑
            segments: 切片資訊列表

        Returns:
            特徵向量列表
        """
        batch_features = []

        for segment_info in segments:
            try:
                # 載入音訊切片
                audio_segment = self._load_audio_segment(
                    filepath,
                    segment_info['start'],
                    segment_info['end'],
                    segment_info['channel']
                )

                if audio_segment is None:
                    logger.warning(f"無法載入切片: selec={segment_info['selec']}, 使用空特徵")
                    # 使用零向量代替
                    feature_vector = [0.0] * self.config['n_filters']
                else:
                    # 提取特徵
                    features = self._extract_single_segment(audio_segment)

                    if features is not None:
                        feature_vector = features.tolist()
                    else:
                        logger.warning(f"特徵提取失敗: selec={segment_info['selec']}, 使用空特徵")
                        feature_vector = [0.0] * self.config['n_filters']

                batch_features.append(feature_vector)

            except Exception as e:
                logger.error(f"提取特徵失敗 (selec={segment_info['selec']}): {e}")
                # 異常時使用零向量
                batch_features.append([0.0] * self.config['n_filters'])

        return batch_features

    def _load_audio_segment(self, filepath: str, start_time: float,
                            end_time: float, channel: int) -> Optional[np.ndarray]:
        """
        載入音訊切片

        Args:
            filepath: 音訊檔案路徑
            start_time: 開始時間（秒）
            end_time: 結束時間（秒）
            channel: 通道編號

        Returns:
            音訊切片或 None
        """
        try:
            # 載入音訊檔案
            audio, sr = librosa.load(
                filepath,
                sr=AUDIO_CONFIG['sample_rate'],
                mono=False,
                offset=start_time,
                duration=end_time - start_time
            )

            # 處理多通道
            if audio.ndim == 1:
                if channel != 0:
                    logger.warning(f"請求通道 {channel} 但音訊是單聲道")
                    return None
                return audio
            else:
                if channel >= audio.shape[0]:
                    logger.warning(f"請求通道 {channel} 超出範圍 {audio.shape[0]}")
                    return None
                return audio[channel]

        except Exception as e:
            logger.error(f"音訊載入失敗 {filepath}: {e}")
            return None

    def _extract_single_segment(self, audio_segment: np.ndarray) -> Optional[np.ndarray]:
        """
        提取單個音訊切片的 LEAF 特徵

        Args:
            audio_segment: 音訊切片 (1D numpy array)

        Returns:
            LEAF 特徵向量或 None
        """
        try:
            # 檢查音訊長度
            min_samples = int(self.config['sample_rate'] * 0.025)
            if len(audio_segment) < min_samples:
                logger.warning(f"音訊切片太短: {len(audio_segment)} < {min_samples}")
                return None

            # 轉換為 PyTorch 張量 [batch, samples]
            audio_tensor = torch.FloatTensor(audio_segment).unsqueeze(0).to(self.device)

            # 提取 LEAF 特徵
            with torch.no_grad():
                features = self.model(audio_tensor)
                features_np = features.cpu().numpy().squeeze()

                # 處理維度
                if features_np.ndim == 2:
                    # 如果是時間x特徵的格式，取平均值
                    features_np = np.mean(features_np, axis=0)
                elif features_np.ndim == 0:
                    # 如果是純量，轉換為1維陣列
                    features_np = np.array([features_np])

                return features_np

        except Exception as e:
            logger.error(f"LEAF 特徵提取失敗: {e}")
            return None

    def get_feature_info(self) -> Dict[str, Any]:
        """獲取特徵提取器資訊"""
        return {
            'extractor_type': 'LEAF',
            'feature_dtype': 'float32',
            'n_filters': self.config['n_filters'],
            'sample_rate': self.config['sample_rate'],
            'window_len': self.config['window_len'],
            'window_stride': self.config['window_stride'],
            'pcen_compression': self.config['pcen_compression'],
            'device': str(self.device),
            'feature_dim': self.config['n_filters']
        }

    def cleanup(self):
        """清理資源"""
        if hasattr(self, 'model'):
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("LEAF 提取器資源已清理")