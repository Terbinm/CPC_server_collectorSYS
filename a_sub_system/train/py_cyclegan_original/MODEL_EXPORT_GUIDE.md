# CycleGAN 模型保存与导出指南

## 训练时的模型保存

### PyTorch Lightning Checkpoint（训练用）

训练时，PyTorch Lightning 会将**所有 4 个模型**保存在一个 `.ckpt` 文件中：

```
checkpoints/
├── cyclegan-epoch=50-val_cycle_A=0.1234.ckpt  # 包含所有4个模型
├── cyclegan-last.ckpt                          # 最后一个epoch
└── normalization_params.json                   # 归一化参数
```

**一个 `.ckpt` 文件包含：**
1. ✅ Generator A→B (`generator_AB`)
2. ✅ Generator B→A (`generator_BA`)
3. ✅ Discriminator A (`discriminator_A`)
4. ✅ Discriminator B (`discriminator_B`)
5. ✅ 优化器状态
6. ✅ 训练超参数

**优点：**
- 可以从任意 epoch 恢复训练
- 保持完整的训练状态

**缺点：**
- 文件较大（包含不必要的判别器）
- 推理时不方便

---

## 推理时的模型导出

### 导出独立模型文件

使用导出脚本将 checkpoint 分解为独立的模型文件：

```bash
# 导出所有模型（包括判别器）
python scripts/export_models.py \
    --checkpoint checkpoints/cyclegan-epoch=50.ckpt \
    --output-dir exported_models

# 仅导出生成器（推荐，推理不需要判别器）
python scripts/export_models.py \
    --checkpoint checkpoints/cyclegan-epoch=50.ckpt \
    --output-dir exported_models \
    --no-discriminators

# 同时生成推理示例脚本
python scripts/export_models.py \
    --checkpoint checkpoints/cyclegan-epoch=50.ckpt \
    --output-dir exported_models \
    --no-discriminators \
    --create-inference-script
```

### 导出后的文件结构

```
exported_models/
├── generator_AB.pth              # A→B 生成器（推理必需）
├── generator_BA.pth              # B→A 生成器（推理必需）
├── discriminator_A.pth           # 判别器A（可选）
├── discriminator_B.pth           # 判别器B（可选）
├── model_config.json             # 模型配置
├── normalization_params.json     # 归一化参数
└── inference_example.py          # 推理示例脚本
```

---

## 模型详细说明

### 1. Generator A→B (`generator_AB.pth`)

**功能：** 将 Domain A 的特征转换到 Domain B

**典型用途：**
- 将 cpc006 设备的特征转换为类似 BATCH_UPLOAD 的特征
- 域适应推理

**参数量：** ~100K-500K（取决于配置）

### 2. Generator B→A (`generator_BA.pth`)

**功能：** 将 Domain B 的特征转换到 Domain A

**典型用途：**
- 将 BATCH_UPLOAD 设备的特征转换为类似 cpc006 的特征
- 反向域适应

**参数量：** ~100K-500K

### 3. Discriminator A (`discriminator_A.pth`)

**功能：** 判别特征是否来自真实的 Domain A

**用途：**
- ⚠️ **推理时不需要**
- 仅在训练时使用

### 4. Discriminator B (`discriminator_B.pth`)

**功能：** 判别特征是否来自真实的 Domain B

**用途：**
- ⚠️ **推理时不需要**
- 仅在训练时使用

---

## 推理使用示例

### 方法 1：使用生成的推理脚本

```bash
cd exported_models
python inference_example.py
```

### 方法 2：手动加载模型

```python
import torch
import numpy as np
import json
from models import Generator

# 1. 加载配置
with open('exported_models/model_config.json', 'r') as f:
    config = json.load(f)

# 2. 创建生成器
generator_AB = Generator(**config['generator_config'])

# 3. 加载权重
state_dict = torch.load('exported_models/generator_AB.pth')
generator_AB.load_state_dict(state_dict)
generator_AB.eval()

# 4. 推理
features_A = torch.randn(1, 50, 40)  # (batch, seq_len, feature_dim)
with torch.no_grad():
    features_B = generator_AB(features_A)

print(f"Converted: {features_A.shape} -> {features_B.shape}")
```

### 方法 3：使用完整的 CycleGAN Module

```python
from models import CycleGANModule

# 直接加载 checkpoint
model = CycleGANModule.load_from_checkpoint(
    'checkpoints/cyclegan-epoch=50.ckpt'
)

# 使用便捷方法进行推理
features_B = model.convert_A_to_B(features_A)
features_A_reconstructed = model.convert_B_to_A(features_B)
```

---

## 模型大小对比

| 文件类型 | 大小 | 包含内容 |
|---------|------|---------|
| `.ckpt` (完整) | ~5-20 MB | 4个模型 + 优化器 + 状态 |
| `generator_*.pth` | ~1-3 MB | 单个生成器 |
| `discriminator_*.pth` | ~1-3 MB | 单个判别器 |

**推荐做法：**
- ✅ 训练时：使用 `.ckpt` 保存所有内容
- ✅ 推理时：只导出并使用 `generator_*.pth`
- ✅ 部署时：只分发生成器文件（节省 60-70% 空间）

---

## FAQ

### Q: 为什么训练时只看到一个文件？

A: PyTorch Lightning 将所有模型打包在一个 `.ckpt` 文件中，便于恢复训练。

### Q: 推理时需要判别器吗？

A: **不需要**。判别器只在训练时用于对抗学习，推理时只需要生成器。

### Q: 如何选择使用哪个生成器？

A:
- 如果你的输入来自 Domain A（如 cpc006），使用 `generator_AB`
- 如果你的输入来自 Domain B（如 BATCH_UPLOAD），使用 `generator_BA`

### Q: 可以删除 .ckpt 文件吗？

A:
- 如果不需要继续训练，导出模型后可以删除
- 但建议保留最佳的 checkpoint，以备将来微调使用

### Q: 两个生成器的架构一样吗？

A: 是的，它们使用相同的架构，但参数不同：
- `generator_AB` 学习 A→B 的转换
- `generator_BA` 学习 B→A 的转换

---

## 相关命令总结

```bash
# 训练（自动保存 checkpoint）
python scripts/train.py

# 导出模型（仅生成器）
python scripts/export_models.py \
    --checkpoint checkpoints/best.ckpt \
    --output-dir exported_models \
    --no-discriminators \
    --create-inference-script

# 查看 checkpoint 内容
python -c "import torch; ckpt = torch.load('checkpoints/xxx.ckpt'); print(ckpt.keys())"

# 查看模型参数量
python scripts/export_models.py --checkpoint checkpoints/xxx.ckpt --output-dir tmp
```
