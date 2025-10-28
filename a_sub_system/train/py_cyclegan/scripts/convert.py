"""
CycleGAN 域转换脚本

将 Domain A 的 LEAF 特征转换到 Domain B

使用方法：
    python scripts/convert.py --checkpoint checkpoints/best.ckpt --input data.json --output converted.json --direction AB
"""

import sys
import argparse
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
import numpy as np

from models import CycleGANModule
from data import FileLEAFLoader
from utils import setup_logger


def main():
    parser = argparse.ArgumentParser(description="Convert LEAF features using trained CycleGAN")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to model checkpoint")
    parser.add_argument("--input", type=str, required=True, help="Input features file (JSON or NPY)")
    parser.add_argument("--output", type=str, required=True, help="Output file path")
    parser.add_argument("--direction", type=str, default="AB", choices=["AB", "BA"], help="Conversion direction")
    parser.add_argument("--device", type=str, default="cuda", choices=["cuda", "cpu"], help="Device to use")
    args = parser.parse_args()

    # 设置日志
    logger = setup_logger()
    logger.info("=== CycleGAN Feature Conversion ===")

    # 检查设备
    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, using CPU")
        device = torch.device("cpu")
    else:
        device = torch.device(args.device)

    # 加载模型
    logger.info(f"Loading model from {args.checkpoint}")
    model = CycleGANModule.load_from_checkpoint(args.checkpoint)
    model = model.to(device)
    model.eval()
    logger.info("Model loaded successfully")

    # 加载输入特征
    logger.info(f"Loading input features from {args.input}")
    if args.input.endswith('.json'):
        features_list = FileLEAFLoader.load_from_json(args.input)
    elif args.input.endswith('.npy'):
        features_list = FileLEAFLoader.load_from_npy(args.input)
    else:
        raise ValueError(f"Unsupported file format: {args.input}")

    logger.info(f"Loaded {len(features_list)} samples")

    # 转换特征
    logger.info(f"Converting features: {args.direction}")
    converted_features = []

    with torch.no_grad():
        for i, features in enumerate(features_list):
            # 转换为 Tensor
            feat_tensor = torch.FloatTensor(features).unsqueeze(0).to(device)

            # 执行转换
            if args.direction == "AB":
                converted = model.convert_A_to_B(feat_tensor)
            else:
                converted = model.convert_B_to_A(feat_tensor)

            # 转回 numpy
            converted_np = converted.squeeze(0).cpu().numpy()
            converted_features.append(converted_np)

            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(features_list)} samples")

    logger.info(f"Conversion completed: {len(converted_features)} samples")

    # 保存结果
    logger.info(f"Saving results to {args.output}")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.output.endswith('.json'):
        # 保存为 JSON
        output_data = [feat.tolist() for feat in converted_features]
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
    elif args.output.endswith('.npy'):
        # 保存为 NPY
        FileLEAFLoader.save_to_npy(converted_features, args.output)
    else:
        raise ValueError(f"Unsupported output format: {args.output}")

    logger.info("=== Conversion Completed ===")


if __name__ == "__main__":
    main()
