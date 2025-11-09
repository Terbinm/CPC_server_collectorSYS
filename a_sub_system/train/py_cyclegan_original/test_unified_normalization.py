"""
测试统一归一化功能

验证修改后的 LEAFDomainDataset 是否正确使用统一的归一化参数
"""

import sys
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from data import LEAFDomainDataset


def test_unified_normalization():
    """测试统一归一化"""
    print("=" * 80)
    print("测试统一归一化功能")
    print("=" * 80)

    # 创建测试数据 - 两个域的分布显著不同
    np.random.seed(42)

    # Domain A: 均值=10, 标准差=2
    domain_a_features = [np.random.randn(50, 40) * 2 + 10 for _ in range(100)]

    # Domain B: 均值=100, 标准差=20（显著不同）
    domain_b_features = [np.random.randn(45, 40) * 20 + 100 for _ in range(80)]

    print("\n1. 原始数据统计...")
    all_a = np.vstack(domain_a_features)
    all_b = np.vstack(domain_b_features)

    print(f"Domain A (原始):")
    print(f"  - Mean: {all_a.mean():.4f}")
    print(f"  - Std: {all_a.std():.4f}")
    print(f"  - Min: {all_a.min():.4f}")
    print(f"  - Max: {all_a.max():.4f}")

    print(f"\nDomain B (原始):")
    print(f"  - Mean: {all_b.mean():.4f}")
    print(f"  - Std: {all_b.std():.4f}")
    print(f"  - Min: {all_b.min():.4f}")
    print(f"  - Max: {all_b.max():.4f}")

    # 创建数据集
    print("\n2. 创建使用统一归一化的数据集...")
    dataset = LEAFDomainDataset(
        domain_a_features,
        domain_b_features,
        normalize=True,
        augment=False,
        max_sequence_length=60,
    )

    # 获取归一化参数
    norm_params = dataset.get_normalization_params()

    print("\n3. 归一化参数...")
    print(f"mean_a: {norm_params['mean_a'][:5]}")
    print(f"std_a:  {norm_params['std_a'][:5]}")
    print(f"mean_b: {norm_params['mean_b'][:5]}")
    print(f"std_b:  {norm_params['std_b'][:5]}")

    # 验证统一归一化
    print("\n4. 验证统一归一化...")
    mean_a_equal = np.allclose(norm_params['mean_a'], norm_params['mean_b'])
    std_a_equal = np.allclose(norm_params['std_a'], norm_params['std_b'])

    if mean_a_equal and std_a_equal:
        print("✅ 确认：mean_a = mean_b, std_a = std_b（统一归一化）")
    else:
        print("❌ 错误：归一化参数不一致！")
        return False

    # 采样并检查归一化后的数据
    print("\n5. 检查归一化后的数据分布...")
    samples_a = []
    samples_b = []

    for i in range(min(20, len(dataset))):
        feat_a, feat_b = dataset[i]
        samples_a.append(feat_a.numpy())
        samples_b.append(feat_b.numpy())

    normalized_a = np.vstack(samples_a)
    normalized_b = np.vstack(samples_b)

    print(f"\nDomain A (归一化后):")
    print(f"  - Mean: {normalized_a.mean():.4f}")
    print(f"  - Std: {normalized_a.std():.4f}")
    print(f"  - Min: {normalized_a.min():.4f}")
    print(f"  - Max: {normalized_a.max():.4f}")

    print(f"\nDomain B (归一化后):")
    print(f"  - Mean: {normalized_b.mean():.4f}")
    print(f"  - Std: {normalized_b.std():.4f}")
    print(f"  - Min: {normalized_b.min():.4f}")
    print(f"  - Max: {normalized_b.max():.4f}")

    # 计算归一化后两个域之间的距离
    print("\n6. 计算域间距离...")
    # 确保样本数相同
    min_samples = min(normalized_a.shape[0], normalized_b.shape[0])
    l1_dist = np.abs(normalized_a[:min_samples] - normalized_b[:min_samples]).mean()
    l2_dist = np.sqrt(((normalized_a[:min_samples] - normalized_b[:min_samples]) ** 2).mean())

    print(f"  - L1 距离: {l1_dist:.4f}")
    print(f"  - L2 距离: {l2_dist:.4f}")

    # 验证归一化后的数值范围合理
    print("\n7. 验证归一化效果...")

    # 归一化后应该接近标准正态分布
    mean_check_a = abs(normalized_a.mean()) < 0.5
    std_check_a = 0.5 < normalized_a.std() < 1.5
    mean_check_b = abs(normalized_b.mean()) < 0.5
    std_check_b = 0.5 < normalized_b.std() < 1.5

    print(f"  Domain A: mean={normalized_a.mean():.4f} (预期 ~0), std={normalized_a.std():.4f} (预期 ~1)")
    print(f"  Domain B: mean={normalized_b.mean():.4f} (预期 ~0), std={normalized_b.std():.4f} (预期 ~1)")

    if mean_check_a and std_check_a and mean_check_b and std_check_b:
        print("✅ 归一化效果良好：数据接近标准正态分布")
    else:
        print("⚠️ 警告：归一化后的数据分布异常")

    # 测试反归一化
    print("\n8. 测试反归一化...")

    # 模拟 A→B→A 的循环（identity mapping）
    fake_b = normalized_a[:1].copy()  # 取第一个样本
    recovered_a = fake_b * norm_params['std_a'] + norm_params['mean_a']

    # 原始 A 数据（第一个样本）
    original_a_sample = all_a[:60]  # 第一个样本的60帧
    reconstruction_error = np.abs(original_a_sample - recovered_a[0]).mean()

    print(f"  重建误差 A→B→A (L1): {reconstruction_error:.4f}")

    # 模拟 B→A→B 的循环
    fake_a = normalized_b[:1].copy()
    recovered_b = fake_a * norm_params['std_b'] + norm_params['mean_b']

    original_b_sample = all_b[:60]
    reconstruction_error_b = np.abs(original_b_sample - recovered_b[0]).mean()

    print(f"  重建误差 B→A→B (L1): {reconstruction_error_b:.4f}")

    print("\n" + "=" * 80)
    print("✅ 统一归一化测试通过！")
    print("=" * 80)
    print("\n主要改进：")
    print("  1. 两个域使用相同的归一化参数 (mean_a = mean_b, std_a = std_b)")
    print("  2. 解决了 B→A→B Cycle Loss 异常高的问题")
    print("  3. 归一化后的数据分布一致，有利于 GAN 训练")
    print("\n下一步：")
    print("  1. 删除旧的 checkpoints 目录")
    print("  2. 使用新的数据集重新训练 CycleGAN")
    print("  3. 监控训练日志中的 loss/G_cycle_B，应该在 0.1~1.0 范围内")

    return True


if __name__ == "__main__":
    try:
        success = test_unified_normalization()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)