"""
Data Preprocessing Utilities for LEAF Features

包含数据预处理和增强功能
"""

import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def normalize_features(
    features: np.ndarray,
    mean: Optional[np.ndarray] = None,
    std: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    标准化特征

    Args:
        features: 输入特征 (seq_len, feat_dim)
        mean: 均值（如果为 None 则计算）
        std: 标准差（如果为 None 则计算）

    Returns:
        (normalized_features, mean, std)
    """
    if mean is None:
        mean = np.mean(features, axis=0)

    if std is None:
        std = np.std(features, axis=0) + 1e-8

    normalized = (features - mean) / std

    return normalized, mean, std


def denormalize_features(
    features: np.ndarray, mean: np.ndarray, std: np.ndarray
) -> np.ndarray:
    """反标准化特征"""
    return features * std + mean


def augment_features(
    features: np.ndarray,
    noise_std: float = 0.01,
    dropout_prob: float = 0.1,
    time_warp: bool = False,
) -> np.ndarray:
    """
    数据增强

    Args:
        features: 输入特征 (seq_len, feat_dim)
        noise_std: 高斯噪声标准差
        dropout_prob: 特征 dropout 概率
        time_warp: 是否应用时间扭曲

    Returns:
        增强后的特征
    """
    augmented = features.copy()

    # 1. 添加高斯噪声
    if noise_std > 0:
        noise = np.random.normal(0, noise_std, features.shape)
        augmented += noise

    # 2. 特征 dropout
    if dropout_prob > 0:
        mask = np.random.random(features.shape) > dropout_prob
        augmented *= mask

    # 3. 时间扭曲（简单实现：随机采样）
    if time_warp and len(features) > 10:
        warp_factor = np.random.uniform(0.8, 1.2)
        new_len = int(len(features) * warp_factor)
        indices = np.linspace(0, len(features) - 1, new_len).astype(int)
        augmented = augmented[indices]

    return augmented


def pad_sequence(
    features: np.ndarray, target_length: int, pad_value: float = 0.0
) -> np.ndarray:
    """
    填充序列到目标长度

    Args:
        features: 输入特征 (seq_len, feat_dim)
        target_length: 目标长度
        pad_value: 填充值

    Returns:
        填充后的特征 (target_length, feat_dim)
    """
    seq_len, feat_dim = features.shape

    if seq_len >= target_length:
        return features[:target_length]

    # 创建填充
    pad_len = target_length - seq_len
    pad = np.full((pad_len, feat_dim), pad_value, dtype=features.dtype)

    return np.vstack([features, pad])


def truncate_sequence(features: np.ndarray, target_length: int) -> np.ndarray:
    """截断序列到目标长度"""
    return features[:target_length]


class LEAFPreprocessor:
    """
    LEAF 特征预处理器

    封装所有预处理操作
    """

    def __init__(
        self,
        normalize: bool = True,
        augment: bool = False,
        max_length: Optional[int] = None,
        noise_std: float = 0.01,
        dropout_prob: float = 0.1,
    ):
        """
        初始化预处理器

        Args:
            normalize: 是否标准化
            augment: 是否数据增强
            max_length: 最大序列长度
            noise_std: 噪声标准差
            dropout_prob: Dropout 概率
        """
        self.normalize = normalize
        self.augment = augment
        self.max_length = max_length
        self.noise_std = noise_std
        self.dropout_prob = dropout_prob

        self.mean = None
        self.std = None

    def fit(self, features_list: list):
        """拟合归一化参数"""
        if not self.normalize:
            return

        all_features = np.vstack(features_list)
        self.mean = np.mean(all_features, axis=0)
        self.std = np.std(all_features, axis=0) + 1e-8

        logger.info(
            f"Preprocessor fitted: mean={self.mean.mean():.4f}, "
            f"std={self.std.mean():.4f}"
        )

    def transform(self, features: np.ndarray) -> np.ndarray:
        """应用预处理"""
        # 序列长度处理
        if self.max_length is not None:
            features = pad_sequence(features, self.max_length)

        # 标准化
        if self.normalize and self.mean is not None:
            features = (features - self.mean) / self.std

        # 数据增强
        if self.augment:
            features = augment_features(
                features,
                noise_std=self.noise_std,
                dropout_prob=self.dropout_prob,
            )

        return features

    def fit_transform(self, features_list: list) -> list:
        """拟合并转换"""
        self.fit(features_list)
        return [self.transform(f) for f in features_list]

    def inverse_transform(self, features: np.ndarray) -> np.ndarray:
        """反标准化"""
        if self.normalize and self.mean is not None:
            features = features * self.std + self.mean
        return features


if __name__ == "__main__":
    # 测试预处理功能
    np.random.seed(42)

    # 创建测试数据
    test_features = np.random.randn(50, 40)

    print("=== Testing Normalization ===")
    normalized, mean, std = normalize_features(test_features)
    print(f"Original - Mean: {test_features.mean():.4f}, Std: {test_features.std():.4f}")
    print(f"Normalized - Mean: {normalized.mean():.4f}, Std: {normalized.std():.4f}")

    denormalized = denormalize_features(normalized, mean, std)
    print(f"Denormalized matches original: {np.allclose(test_features, denormalized)}")

    print("\n=== Testing Augmentation ===")
    augmented = augment_features(test_features, noise_std=0.01, dropout_prob=0.1)
    print(f"Original shape: {test_features.shape}")
    print(f"Augmented shape: {augmented.shape}")

    print("\n=== Testing Padding ===")
    padded = pad_sequence(test_features, 100)
    print(f"Padded shape: {padded.shape}")

    print("\n=== Testing Preprocessor ===")
    preprocessor = LEAFPreprocessor(
        normalize=True, augment=True, max_length=60
    )

    # 拟合
    features_list = [np.random.randn(50, 40) for _ in range(10)]
    preprocessor.fit(features_list)

    # 转换
    transformed = preprocessor.transform(test_features)
    print(f"Transformed shape: {transformed.shape}")

    # 反转换
    inverse = preprocessor.inverse_transform(transformed)
    print(f"Inverse shape: {inverse.shape}")
