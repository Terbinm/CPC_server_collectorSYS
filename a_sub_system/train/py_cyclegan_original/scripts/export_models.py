"""
从 CycleGAN Checkpoint 中导出独立模型

使用方法：
    python scripts/export_models.py --checkpoint checkpoints/cyclegan-epoch=50.ckpt --output-dir exported_models

导出的模型：
    - generator_AB.pth: Domain A → Domain B 生成器
    - generator_BA.pth: Domain B → Domain A 生成器
    - discriminator_A.pth: Domain A 判别器
    - discriminator_B.pth: Domain B 判别器
"""

import sys
import argparse
import torch
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import CycleGANModule


def export_models(checkpoint_path: str, output_dir: str, export_discriminators: bool = True):
    """
    从checkpoint导出独立模型

    Args:
        checkpoint_path: checkpoint文件路径
        output_dir: 输出目录
        export_discriminators: 是否导出判别器（推理时通常不需要）
    """
    print("=" * 60)
    print("CycleGAN 模型导出工具")
    print("=" * 60)

    # 加载checkpoint
    print(f"\n1. 加载 checkpoint: {checkpoint_path}")
    try:
        model = CycleGANModule.load_from_checkpoint(checkpoint_path)
        print("   ✓ Checkpoint 加载成功")
    except Exception as e:
        print(f"   ✗ 加载失败: {e}")
        return False

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"\n2. 创建输出目录: {output_dir}")

    # 导出生成器 AB
    print("\n3. 导出生成器模型")
    generator_ab_path = output_path / "generator_AB.pth"
    torch.save(model.generator_AB.state_dict(), generator_ab_path)
    print(f"   ✓ Generator A→B: {generator_ab_path}")

    # 导出生成器 BA
    generator_ba_path = output_path / "generator_BA.pth"
    torch.save(model.generator_BA.state_dict(), generator_ba_path)
    print(f"   ✓ Generator B→A: {generator_ba_path}")

    # 导出判别器（可选）
    if export_discriminators:
        print("\n4. 导出判别器模型")
        discriminator_a_path = output_path / "discriminator_A.pth"
        torch.save(model.discriminator_A.state_dict(), discriminator_a_path)
        print(f"   ✓ Discriminator A: {discriminator_a_path}")

        discriminator_b_path = output_path / "discriminator_B.pth"
        torch.save(model.discriminator_B.state_dict(), discriminator_b_path)
        print(f"   ✓ Discriminator B: {discriminator_b_path}")
    else:
        print("\n4. 跳过判别器导出（推理不需要）")

    # 导出配置和归一化参数
    print("\n5. 导出配置信息")
    import json

    # 模型配置
    model_config = {
        "input_dim": model.hparams.input_dim,
        "generator_config": model.hparams.generator_config,
        "discriminator_config": model.hparams.discriminator_config,
        "training": {
            "learning_rate": model.hparams.learning_rate,
            "lambda_cycle": model.hparams.lambda_cycle,
            "lambda_identity": model.hparams.lambda_identity,
            "use_identity_loss": model.hparams.use_identity_loss,
        }
    }

    config_path = output_path / "model_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(model_config, f, indent=2, ensure_ascii=False)
    print(f"   ✓ 模型配置: {config_path}")

    # 复制归一化参数（如果存在）
    checkpoint_dir = Path(checkpoint_path).parent
    norm_params_src = checkpoint_dir / "normalization_params.json"

    if norm_params_src.exists():
        norm_params_dst = output_path / "normalization_params.json"
        import shutil
        shutil.copy(norm_params_src, norm_params_dst)
        print(f"   ✓ 归一化参数: {norm_params_dst}")
    else:
        print(f"   ⚠ 未找到归一化参数文件: {norm_params_src}")

    # 统计信息
    print("\n" + "=" * 60)
    print("导出完成！")
    print("=" * 60)

    # 计算模型大小
    def get_model_size(model):
        """计算模型参数量"""
        return sum(p.numel() for p in model.parameters())

    gen_ab_params = get_model_size(model.generator_AB)
    gen_ba_params = get_model_size(model.generator_BA)

    print(f"\n模型统计：")
    print(f"  Generator A→B: {gen_ab_params:,} 参数")
    print(f"  Generator B→A: {gen_ba_params:,} 参数")

    if export_discriminators:
        disc_a_params = get_model_size(model.discriminator_A)
        disc_b_params = get_model_size(model.discriminator_B)
        print(f"  Discriminator A: {disc_a_params:,} 参数")
        print(f"  Discriminator B: {disc_b_params:,} 参数")
        print(f"  总计: {gen_ab_params + gen_ba_params + disc_a_params + disc_b_params:,} 参数")
    else:
        print(f"  总计（仅生成器）: {gen_ab_params + gen_ba_params:,} 参数")

    print(f"\n输出目录: {output_path.absolute()}")
    print("\n使用说明：")
    print("  1. 推理时只需要加载生成器模型")
    print("  2. 使用 generator_AB.pth 进行 A→B 转换")
    print("  3. 使用 generator_BA.pth 进行 B→A 转换")
    print("  4. 记得使用 normalization_params.json 中的参数进行归一化")

    return True


def create_inference_script(output_dir: str):
    """创建简单的推理示例脚本"""
    output_path = Path(output_dir)
    inference_script = output_path / "inference_example.py"

    script_content = '''"""
CycleGAN 推理示例

使用导出的生成器模型进行推理
"""

import torch
import numpy as np
import json
from pathlib import Path

# 添加项目路径
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models import Generator


def load_generator(model_path: str, config_path: str, device: str = 'cuda'):
    """
    加载生成器模型

    Args:
        model_path: 模型权重路径（.pth）
        config_path: 配置文件路径（.json）
        device: 设备

    Returns:
        加载好的生成器模型
    """
    # 加载配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 创建模型
    generator = Generator(**config['generator_config'])

    # 加载权重
    state_dict = torch.load(model_path, map_location=device)
    generator.load_state_dict(state_dict)

    # 设置为评估模式
    generator.eval()
    generator.to(device)

    return generator


def load_normalization_params(norm_params_path: str):
    """加载归一化参数"""
    with open(norm_params_path, 'r', encoding='utf-8') as f:
        params = json.load(f)

    return {
        'mean_a': np.array(params['mean_a']),
        'std_a': np.array(params['std_a']),
        'mean_b': np.array(params['mean_b']),
        'std_b': np.array(params['std_b'])
    }


def normalize_features(features: np.ndarray, mean: np.ndarray, std: np.ndarray):
    """归一化特征"""
    return (features - mean) / std


def denormalize_features(features: np.ndarray, mean: np.ndarray, std: np.ndarray):
    """反归一化特征"""
    return features * std + mean


def convert_A_to_B(features_A: np.ndarray,
                   generator_AB: torch.nn.Module,
                   norm_params: dict,
                   device: str = 'cuda'):
    """
    将 Domain A 的特征转换到 Domain B

    Args:
        features_A: Domain A 的特征 (seq_len, 40) 或 (batch, seq_len, 40)
        generator_AB: A→B 生成器
        norm_params: 归一化参数
        device: 设备

    Returns:
        转换后的 Domain B 特征
    """
    # 归一化
    features_normalized = normalize_features(
        features_A,
        norm_params['mean_a'],
        norm_params['std_a']
    )

    # 转换为 tensor
    if features_normalized.ndim == 2:
        # (seq_len, 40) -> (1, seq_len, 40)
        features_tensor = torch.from_numpy(features_normalized).unsqueeze(0).float()
    else:
        # (batch, seq_len, 40)
        features_tensor = torch.from_numpy(features_normalized).float()

    features_tensor = features_tensor.to(device)

    # 推理
    with torch.no_grad():
        fake_B = generator_AB(features_tensor)

    # 转回 numpy
    fake_B_np = fake_B.cpu().numpy()

    # 反归一化到 Domain B
    fake_B_denorm = denormalize_features(
        fake_B_np,
        norm_params['mean_b'],
        norm_params['std_b']
    )

    # 移除 batch 维度（如果输入是单个样本）
    if features_A.ndim == 2:
        fake_B_denorm = fake_B_denorm.squeeze(0)

    return fake_B_denorm


def main():
    """主函数 - 推理示例"""
    # 设置路径
    model_dir = Path(__file__).parent

    # 加载生成器
    print("加载生成器模型...")
    generator_AB = load_generator(
        model_path=str(model_dir / "generator_AB.pth"),
        config_path=str(model_dir / "model_config.json"),
        device='cuda' if torch.cuda.is_available() else 'cpu'
    )
    print("✓ 生成器加载成功")

    # 加载归一化参数
    print("加载归一化参数...")
    norm_params = load_normalization_params(
        str(model_dir / "normalization_params.json")
    )
    print("✓ 归一化参数加载成功")

    # 示例：转换单个序列
    print("\\n测试推理...")
    test_features_A = np.random.randn(50, 40).astype(np.float32)

    fake_B = convert_A_to_B(
        test_features_A,
        generator_AB,
        norm_params,
        device='cuda' if torch.cuda.is_available() else 'cpu'
    )

    print(f"输入特征 A shape: {test_features_A.shape}")
    print(f"输出特征 B shape: {fake_B.shape}")
    print("✓ 推理成功")


if __name__ == "__main__":
    main()
'''

    with open(inference_script, 'w', encoding='utf-8') as f:
        f.write(script_content)

    print(f"   ✓ 推理示例脚本: {inference_script}")


def main():
    parser = argparse.ArgumentParser(description="从 CycleGAN checkpoint 导出独立模型")
    parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        help="Checkpoint 文件路径（.ckpt）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="exported_models",
        help="输出目录（默认: exported_models）"
    )
    parser.add_argument(
        "--no-discriminators",
        action="store_true",
        help="不导出判别器（推理时不需要）"
    )
    parser.add_argument(
        "--create-inference-script",
        action="store_true",
        help="创建推理示例脚本"
    )

    args = parser.parse_args()

    # 导出模型
    success = export_models(
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
        export_discriminators=not args.no_discriminators
    )

    if not success:
        print("\n导出失败！")
        return 1

    # 创建推理脚本
    if args.create_inference_script:
        print("\n" + "=" * 60)
        print("创建推理示例脚本")
        print("=" * 60)
        create_inference_script(args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
