"""
Evaluation Metrics for Domain Adaptation
"""

import numpy as np
import torch
from typing import Union


def compute_mmd(
    features_a: Union[np.ndarray, torch.Tensor],
    features_b: Union[np.ndarray, torch.Tensor],
    kernel: str = "rbf",
    gamma: float = 1.0,
) -> float:
    """
    计算 Maximum Mean Discrepancy (MMD)

    Args:
        features_a: Domain A 特征
        features_b: Domain B 特征
        kernel: 核函数类型
        gamma: RBF 核参数

    Returns:
        MMD 距离
    """
    if isinstance(features_a, np.ndarray):
        features_a = torch.FloatTensor(features_a)
    if isinstance(features_b, np.ndarray):
        features_b = torch.FloatTensor(features_b)

    # 展平为 2D
    if features_a.dim() == 3:
        features_a = features_a.reshape(-1, features_a.shape[-1])
    if features_b.dim() == 3:
        features_b = features_b.reshape(-1, features_b.shape[-1])

    def rbf_kernel(x, y, gamma):
        x_size = x.size(0)
        y_size = y.size(0)
        dim = x.size(1)

        x = x.unsqueeze(1)  # (x_size, 1, dim)
        y = y.unsqueeze(0)  # (1, y_size, dim)

        tiled_x = x.expand(x_size, y_size, dim)
        tiled_y = y.expand(x_size, y_size, dim)

        kernel_input = (tiled_x - tiled_y).pow(2).mean(2) / float(dim)
        return torch.exp(-gamma * kernel_input)

    xx = rbf_kernel(features_a, features_a, gamma).mean()
    yy = rbf_kernel(features_b, features_b, gamma).mean()
    xy = rbf_kernel(features_a, features_b, gamma).mean()

    mmd = xx + yy - 2 * xy
    return mmd.item()


def compute_frechet_distance(
    features_a: np.ndarray, features_b: np.ndarray
) -> float:
    """
    计算 Fréchet Distance

    Args:
        features_a: Domain A 特征
        features_b: Domain B 特征

    Returns:
        Fréchet 距离
    """
    # 展平
    if features_a.ndim == 3:
        features_a = features_a.reshape(-1, features_a.shape[-1])
    if features_b.ndim == 3:
        features_b = features_b.reshape(-1, features_b.shape[-1])

    # 计算均值和协方差
    mu_a = np.mean(features_a, axis=0)
    mu_b = np.mean(features_b, axis=0)

    sigma_a = np.cov(features_a, rowvar=False)
    sigma_b = np.cov(features_b, rowvar=False)

    # 计算距离
    diff = mu_a - mu_b
    covmean = np.sqrt(sigma_a @ sigma_b)

    if np.iscomplexobj(covmean):
        covmean = covmean.real

    fd = diff.dot(diff) + np.trace(sigma_a + sigma_b - 2 * covmean)

    return fd
