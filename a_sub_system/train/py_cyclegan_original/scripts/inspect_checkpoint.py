"""
检查 CycleGAN Checkpoint 内容

快速查看 checkpoint 中保存的所有模型和参数

使用方法：
    python scripts/inspect_checkpoint.py checkpoints/cyclegan-epoch=50.ckpt
"""

import sys
import argparse
import torch
from pathlib import Path


def inspect_checkpoint(checkpoint_path: str):
    """
    检查 checkpoint 内容

    Args:
        checkpoint_path: checkpoint 文件路径
    """
    print("=" * 70)
    print("CycleGAN Checkpoint 检查工具")
    print("=" * 70)

    # 加载 checkpoint
    print(f"\n📁 Checkpoint: {checkpoint_path}")
    print(f"📦 文件大小: {Path(checkpoint_path).stat().st_size / 1024 / 1024:.2f} MB")

    try:
        ckpt = torch.load(checkpoint_path, map_location='cpu')
        print("✓ Checkpoint 加载成功\n")
    except Exception as e:
        print(f"✗ 加载失败: {e}")
        return False

    # 显示顶层 keys
    print("=" * 70)
    print("📋 Checkpoint 内容")
    print("=" * 70)

    for key in ckpt.keys():
        print(f"  • {key}")

    # 显示超参数
    if 'hyper_parameters' in ckpt:
        print("\n" + "=" * 70)
        print("⚙️  超参数 (Hyperparameters)")
        print("=" * 70)

        hparams = ckpt['hyper_parameters']
        for key, value in hparams.items():
            print(f"  • {key}: {value}")

    # 显示状态字典中的模型
    if 'state_dict' in ckpt:
        print("\n" + "=" * 70)
        print("🤖 模型参数 (State Dict)")
        print("=" * 70)

        state_dict = ckpt['state_dict']

        # 统计各个模型的参数
        model_stats = {
            'generator_AB': 0,
            'generator_BA': 0,
            'discriminator_A': 0,
            'discriminator_B': 0,
        }

        for key in state_dict.keys():
            for model_name in model_stats.keys():
                if key.startswith(model_name):
                    model_stats[model_name] += state_dict[key].numel()

        # 显示统计
        print(f"\n  {'模型':<20} {'参数量':>15} {'大小 (MB)':>12}")
        print("  " + "-" * 50)

        total_params = 0
        for model_name, param_count in model_stats.items():
            if param_count > 0:
                size_mb = param_count * 4 / 1024 / 1024  # 假设 float32
                print(f"  {model_name:<20} {param_count:>15,} {size_mb:>12.2f}")
                total_params += param_count

        print("  " + "-" * 50)
        print(f"  {'总计':<20} {total_params:>15,} {total_params * 4 / 1024 / 1024:>12.2f}")

        # 显示详细的参数名称（前20个）
        print("\n  前 20 个参数键:")
        for i, key in enumerate(list(state_dict.keys())[:20]):
            shape = list(state_dict[key].shape)
            print(f"    {i+1:2d}. {key:<50} {str(shape):>20}")

        if len(state_dict) > 20:
            print(f"    ... 还有 {len(state_dict) - 20} 个参数")

    # 显示优化器状态
    if 'optimizer_states' in ckpt:
        print("\n" + "=" * 70)
        print("🔧 优化器状态 (Optimizer States)")
        print("=" * 70)

        opt_states = ckpt['optimizer_states']
        print(f"  优化器数量: {len(opt_states)}")

        for i, opt_state in enumerate(opt_states):
            if opt_state and 'param_groups' in opt_state:
                param_groups = opt_state['param_groups']
                if param_groups:
                    lr = param_groups[0].get('lr', 'N/A')
                    print(f"  • 优化器 {i}: lr={lr}")

    # 显示训练进度
    if 'epoch' in ckpt or 'global_step' in ckpt:
        print("\n" + "=" * 70)
        print("📊 训练进度")
        print("=" * 70)

        if 'epoch' in ckpt:
            print(f"  • Epoch: {ckpt['epoch']}")

        if 'global_step' in ckpt:
            print(f"  • Global Step: {ckpt['global_step']}")

    # 显示 callbacks 状态
    if 'callbacks' in ckpt:
        print("\n" + "=" * 70)
        print("📌 Callbacks 状态")
        print("=" * 70)

        callbacks = ckpt['callbacks']
        for callback_name, callback_state in callbacks.items():
            print(f"  • {callback_name}")
            if isinstance(callback_state, dict):
                for key, value in callback_state.items():
                    if not key.startswith('_'):  # 跳过私有属性
                        print(f"      - {key}: {value}")

    # 总结
    print("\n" + "=" * 70)
    print("✅ 总结")
    print("=" * 70)
    print(f"  这个 checkpoint 包含:")
    print(f"    ✓ 2 个生成器 (Generator A→B, Generator B→A)")
    print(f"    ✓ 2 个判别器 (Discriminator A, Discriminator B)")
    print(f"    ✓ 优化器状态")
    print(f"    ✓ 训练超参数")
    print(f"\n  推理时:")
    print(f"    • 只需要生成器")
    print(f"    • 使用 export_models.py 导出独立的模型文件")
    print(f"\n  恢复训练时:")
    print(f"    • 需要完整的 checkpoint")
    print(f"    • 使用 python scripts/train.py --resume {checkpoint_path}")

    print("\n" + "=" * 70)

    return True


def compare_checkpoints(checkpoint_paths: list):
    """比较多个 checkpoints"""
    print("=" * 70)
    print("比较多个 Checkpoints")
    print("=" * 70)

    checkpoints = []
    for path in checkpoint_paths:
        try:
            ckpt = torch.load(path, map_location='cpu')
            checkpoints.append((path, ckpt))
            print(f"  ✓ 加载: {path}")
        except Exception as e:
            print(f"  ✗ 无法加载 {path}: {e}")

    if len(checkpoints) < 2:
        print("\n需要至少2个有效的 checkpoints 进行比较")
        return

    print("\n" + "=" * 70)
    print("对比结果")
    print("=" * 70)

    # 对比 epoch
    print("\n📊 训练进度:")
    for path, ckpt in checkpoints:
        epoch = ckpt.get('epoch', 'N/A')
        step = ckpt.get('global_step', 'N/A')
        print(f"  {Path(path).name}")
        print(f"    Epoch: {epoch}, Step: {step}")

    # 对比文件大小
    print("\n📦 文件大小:")
    for path, _ in checkpoints:
        size_mb = Path(path).stat().st_size / 1024 / 1024
        print(f"  {Path(path).name:<40} {size_mb:>8.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="检查 CycleGAN checkpoint 内容")
    parser.add_argument(
        "checkpoint",
        type=str,
        nargs='+',
        help="Checkpoint 文件路径（可以指定多个进行比较）"
    )

    args = parser.parse_args()

    if len(args.checkpoint) == 1:
        # 检查单个 checkpoint
        success = inspect_checkpoint(args.checkpoint[0])
        return 0 if success else 1
    else:
        # 比较多个 checkpoints
        compare_checkpoints(args.checkpoint)
        return 0


if __name__ == "__main__":
    sys.exit(main())
