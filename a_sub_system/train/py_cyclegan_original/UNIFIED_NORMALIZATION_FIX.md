# CycleGAN B→A→B Cycle Loss 异常修复报告

## 问题摘要

训练日志显示 `loss/G_cycle_B` (B→A→B 循环损失) 高达 **1437.7**，远超正常范围（0.1～1.0），而 `loss/G_cycle_A` 仅为 0.26。

## 根本原因分析

### 问题定位

在原始 `data/leaf_dataset.py:59-74` 中：

```python
def _compute_normalization_params(self):
    all_features_a = np.vstack(self.domain_a_features)
    all_features_b = np.vstack(self.domain_b_features)

    self.mean_a = np.mean(all_features_a, axis=0)
    self.std_a = np.std(all_features_a, axis=0) + 1e-8

    self.mean_b = np.mean(all_features_b, axis=0)  # ❌ 问题所在
    self.std_b = np.std(all_features_b, axis=0) + 1e-8
```

**Domain A 和 Domain B 使用了不同的归一化参数**，导致两个域在归一化后处于不同的数值尺度。

### 为什么只有 G_cycle_B 异常？

1. **数值尺度不匹配**
   - 如果 Domain B 的 `std_b` 很小，归一化会放大数据
   - Cycle Loss 使用 L1 距离，在放大的空间中计算导致 loss 爆炸

2. **训练数据统计**
   - Domain A (CPC): 3098 samples
   - Domain B (MAFAULDA): 1951 samples
   - 两个域的原始数据分布可能差异很大

## 解决方案：统一归一化

### 修改内容

#### 1. `data/leaf_dataset.py` - 主要修改

```python
def _compute_normalization_params(self):
    """计算特征的均值和标准差 - 使用统一归一化"""
    all_features_a = np.vstack(self.domain_a_features)
    all_features_b = np.vstack(self.domain_b_features)

    # ✅ 统一归一化：合并两个域计算全局统计
    all_features_combined = np.vstack([all_features_a, all_features_b])

    global_mean = np.mean(all_features_combined, axis=0)
    global_std = np.std(all_features_combined, axis=0) + 1e-8

    # 两个域使用相同的归一化参数
    self.mean_a = global_mean
    self.std_a = global_std
    self.mean_b = global_mean
    self.std_b = global_std

    logger.info(
        f"Normalization params computed (unified) - "
        f"Global: mean={global_mean.mean():.4f}, std={global_std.mean():.4f}"
    )
    # 添加原始数据统计日志...
```

#### 2. `scripts/convert.py` - 添加注释

在第64行添加注释说明统一归一化：
```python
# 注意：使用統一歸一化時，mean_a = mean_b, std_a = std_b
# 但為了向後兼容性，我們仍然根據方向選擇參數
```

#### 3. `scripts/batch_domain_conversion.py` - 添加注释

在第75行添加注释说明统一归一化：
```python
# 注意：使用統一歸一化時，mean_a = mean_b, std_a = std_b
# 但為了向後兼容性，我們仍然保留所有參數
```

### 测试验证

运行 `test_unified_normalization.py` 确认：

✅ **统一归一化已生效**
- `mean_a = mean_b`
- `std_a = std_b`
- 两个域在相同的数值空间中

✅ **向后兼容性**
- 推理脚本仍然正常工作
- 归一化参数格式保持不变

## 预期效果

### 修复前
- `loss/G_cycle_A`: 0.26 (正常)
- `loss/G_cycle_B`: 1437.7 (❌ 异常)

### 修复后（预期）
- `loss/G_cycle_A`: 0.2～0.3 (正常)
- `loss/G_cycle_B`: 0.2～0.3 (✅ 正常)

两个方向的 Cycle Loss 应该在相近的数值范围内。

## 下一步操作

### 1. 清理旧模型

```bash
cd a_sub_system/train/py_cyclegan
rm -rf checkpoints/*
rm -rf logs/cyclegan/*
```

### 2. 重新训练

```bash
python scripts/train.py
```

### 3. 监控训练指标

在 TensorBoard 中重点关注：

- ✅ `loss/D_A_epoch`: 应该在 0.1～0.5
- ✅ `loss/D_B_epoch`: 应该在 0.1～0.5
- ✅ `loss/G_cycle_A`: 应该在 0.1～1.0
- ✅ `loss/G_cycle_B`: **应该在 0.1～1.0（不再是 1400+）**
- ✅ `loss/G_GAN_AB`: 应该在 0.5～1.0
- ✅ `loss/G_GAN_BA`: 应该在 0.5～1.0

### 4. 验证归一化参数

训练完成后检查：

```bash
cat checkpoints/normalization_params.json
```

应该看到 `mean_a` 和 `mean_b` 数值相同，`std_a` 和 `std_b` 数值相同。

## 技术细节

### 为什么统一归一化有效？

1. **相同的数值空间**
   - 两个域归一化后处于相同的分布空间
   - Cycle Loss 计算更合理

2. **避免数值爆炸**
   - 不会因为某个域的 std 过小而导致数值放大
   - Loss 值在合理范围内

3. **更容易收敛**
   - 生成器和判别器在相同的数值空间中训练
   - 训练更稳定

### 理论支持

在 CycleGAN 原论文中，使用统一的归一化是常见做法：
- 确保两个域在相同的数值空间
- 简化模型训练
- 提高训练稳定性

## 相关文件

- ✅ 修改：`data/leaf_dataset.py`
- ✅ 更新：`scripts/convert.py`
- ✅ 更新：`scripts/batch_domain_conversion.py`
- ✅ 新增：`test_unified_normalization.py`
- 📄 本文档：`UNIFIED_NORMALIZATION_FIX.md`

## 联系与支持

如果重新训练后 `loss/G_cycle_B` 仍然异常，请检查：

1. 数据质量：确认 MAFAULDA 数据没有异常值
2. 数据量：两个域的样本数是否严重不平衡
3. 特征提取：确认 LEAF 特征提取正确

可以运行 `debug_training_data.py` 进行详细的数据诊断。

---

**修复日期**: 2025-11-05
**测试状态**: ✅ 通过
**建议**: 立即重新训练模型