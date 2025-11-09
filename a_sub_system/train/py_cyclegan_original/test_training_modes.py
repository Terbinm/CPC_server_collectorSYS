"""
测试脚本：验证 slice 和 sequence 训练模式

使用方法：
    python test_training_modes.py
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import numpy as np
from data import LEAFDomainDataset

def test_slice_mode():
    """测试 slice 训练模式"""
    print("=" * 60)
    print("测试 Slice 训练模式")
    print("=" * 60)

    # 创建模拟数据 - slice 模式：每个样本是 (40,)
    domain_a_features = [np.random.randn(40).astype(np.float32) for _ in range(100)]
    domain_b_features = [np.random.randn(40).astype(np.float32) for _ in range(80)]

    print(f"Domain A: {len(domain_a_features)} samples, shape: {domain_a_features[0].shape}")
    print(f"Domain B: {len(domain_b_features)} samples, shape: {domain_b_features[0].shape}")

    # 创建数据集
    dataset = LEAFDomainDataset(
        domain_a_features=domain_a_features,
        domain_b_features=domain_b_features,
        normalize=True,
        augment=False,
        training_mode='slice'
    )

    print(f"\nDataset length: {len(dataset)}")

    # 获取一个样本
    feat_a, feat_b = dataset[0]
    print(f"Feature A shape: {feat_a.shape}")
    print(f"Feature B shape: {feat_b.shape}")

    assert feat_a.shape == (40,), f"Expected (40,), got {feat_a.shape}"
    assert feat_b.shape == (40,), f"Expected (40,), got {feat_b.shape}"

    print("✓ Slice 模式测试通过")
    return True


def test_sequence_mode():
    """测试 sequence 训练模式"""
    print("\n" + "=" * 60)
    print("测试 Sequence 训练模式")
    print("=" * 60)

    # 创建模拟数据 - sequence 模式：每个样本是 (seq_len, 40)
    domain_a_features = [np.random.randn(50, 40).astype(np.float32) for _ in range(100)]
    domain_b_features = [np.random.randn(45, 40).astype(np.float32) for _ in range(80)]

    print(f"Domain A: {len(domain_a_features)} samples, shape: {domain_a_features[0].shape}")
    print(f"Domain B: {len(domain_b_features)} samples, shape: {domain_b_features[0].shape}")

    # 创建数据集（带序列长度限制）
    max_seq_len = 60
    dataset = LEAFDomainDataset(
        domain_a_features=domain_a_features,
        domain_b_features=domain_b_features,
        normalize=True,
        augment=False,
        max_sequence_length=max_seq_len,
        training_mode='sequence'
    )

    print(f"\nDataset length: {len(dataset)}")
    print(f"Max sequence length: {max_seq_len}")

    # 获取一个样本
    feat_a, feat_b = dataset[0]
    print(f"Feature A shape: {feat_a.shape}")
    print(f"Feature B shape: {feat_b.shape}")

    assert feat_a.shape == (max_seq_len, 40), f"Expected ({max_seq_len}, 40), got {feat_a.shape}"
    assert feat_b.shape == (max_seq_len, 40), f"Expected ({max_seq_len}, 40), got {feat_b.shape}"

    print("✓ Sequence 模式测试通过")
    return True


def test_config_integration():
    """测试配置集成"""
    print("\n" + "=" * 60)
    print("测试配置集成")
    print("=" * 60)

    from config import DATA_CONFIG

    training_mode = DATA_CONFIG['preprocessing'].get('training_mode', 'sequence')
    print(f"当前配置的训练模式: {training_mode}")

    if training_mode == 'slice':
        print("✓ 配置为 slice 模式（逐 slice 训练）")
    elif training_mode == 'sequence':
        print("✓ 配置为 sequence 模式（序列训练）")
    else:
        print(f"✗ 未知的训练模式: {training_mode}")
        return False

    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("CycleGAN 训练模式测试")
    print("=" * 60 + "\n")

    try:
        # 测试 slice 模式
        test_slice_mode()

        # 测试 sequence 模式
        test_sequence_mode()

        # 测试配置集成
        test_config_integration()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print("\n使用说明：")
        print("1. Slice 模式（默认）：每个 slice 是独立训练样本")
        print("   - 训练样本更多")
        print("   - 与 RF 模型保持一致")
        print("   - 设置: export TRAINING_MODE=slice")
        print("\n2. Sequence 模式：完整序列作为一个样本")
        print("   - 保留时序信息")
        print("   - 学习序列级别的转换")
        print("   - 设置: export TRAINING_MODE=sequence")
        print("\n当前模式可在 config.py 中通过 TRAINING_MODE 环境变量设置")

        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
