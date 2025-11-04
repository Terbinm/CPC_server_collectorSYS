# 批量上传工具修改摘要

根据 problem.txt 的要求，已完成对三个批量上传工具（CPC、MAFAULDA、MIMII）的统一化修改。

## 修改概览

### 1. CPC 上传器修改

**文件**: `cpc_upload/config.py`, `cpc_upload/cpc_batch_upload.py`

#### 1.1 添加 obj_ID 支持
- ✓ 在 `DATASET_CONFIG` 中添加 `obj_ID: '-1'`
- ✓ 在 `info_features` 中记录 `obj_ID`

#### 1.2 删除 analysis_config，改用 target_channel
- ✓ 删除 `ANALYSIS_CONFIG` 配置
- ✓ 改为使用 `TARGET_CHANNEL = [0]`
- ✓ 在 `info_features` 中使用 `target_channel` 而非 `analysis_config`

#### 1.3 添加音频格式字段
- ✓ 添加 `sample_rate`, `channels`, `raw_format` 到 `info_features`

### 2. MAFAULDA 上传器修改

**文件**: `mafaulda_upload/mafaulda_batch_upload.py`

#### 2.1 删除冗余字段
- ✓ 删除 `info_features.upload_time`
- ✓ 删除 `info_features.batch_upload_metadata`
- ✓ 从 `mafaulda_metadata` 中删除 `num_channels` 和 `sample_rate_hz`

#### 2.2 修复 fault_variant 逻辑
修正路径解析逻辑（`_analyze_file_path` 方法）：

**只有 1 层子目录**：
- 示例：`horizontal-misalignment/0.5mm/12.288.csv`
- 结果：`fault_condition = "0.5mm"`，**不记录** `fault_variant`

**有 2 层或更多子目录**：
- 示例：`overhang/ball_fault/0g/14.1312.csv`
- 结果：`fault_variant = "ball_fault"`, `fault_condition = "0g"`

#### 2.3 添加音频格式字段
- ✓ 添加 `sample_rate`, `channels`, `raw_format` 到 `info_features`
- ✓ `raw_format` 统一为 `"CSV"`

#### 2.4 实现 fault_variant 平均分配采样
修改 `_apply_label_limit` 方法：
- ✓ 使用 round-robin 算法在不同 fault_variant 间均匀采样
- ✓ 使用 `fault_variant` 或 `fault_condition` 作为分组键
- ✓ 当平均分配后每个 variant 数量 < 1 时，发出警告但继续执行（不需要确认）
- ✓ 参考 MIMII 的实现方式，使用 OrderedDict 和 deque 进行采样

### 3. MIMII 上传器修改

**文件**: `mimii_upload/mimii_batch_upload.py`

#### 3.1 删除冗余字段
- ✓ 删除 `info_features.upload_time`
- ✓ 删除 `info_features.batch_upload_metadata`

#### 3.2 添加 fault_type
- ✓ 在 `mimii_metadata` 中添加 `fault_type`（值为 label）
- ✓ 参考 `mafaulda_metadata.fault_type` 的实现

#### 3.3 添加音频格式字段
- ✓ 添加 `sample_rate`, `channels`, `raw_format` 到 `info_features`
- ✓ 修改 `get_file_metadata` 方法以使用 `soundfile.info()` 获取音频信息

## 统一后的文档结构

### CPC 文档结构

```json
{
  "info_features": {
    "dataset_UUID": "cpc_batch_upload",
    "device_id": "cpc006",
    "testing": false,
    "obj_ID": "-1",
    "upload_complete": true,
    "file_hash": "...",
    "file_size": 123456,
    "duration": 10.0,
    "label": "factory_ambient",
    "sample_rate": 16000,
    "channels": 1,
    "raw_format": "WAV",
    "target_channel": [0],
    "cpc_metadata": {
      "subtype": "PCM_16"
    }
  }
}
```

### MAFAULDA 文档结构

```json
{
  "info_features": {
    "dataset_UUID": "mafaulda_batch_upload",
    "device_id": "BATCH_UPLOAD_NORMAL",
    "testing": false,
    "obj_ID": "-1",
    "upload_complete": true,
    "file_hash": "...",
    "file_size": 123456,
    "duration": 5.0,
    "label": "normal",
    "sample_rate": 51200,
    "channels": 8,
    "raw_format": "CSV",
    "target_channel": [7],
    "mafaulda_metadata": {
      "fault_type": "normal",
      "fault_variant": "ball_fault",  // 仅当有 2+ 层目录时存在
      "fault_condition": "0g",
      "fault_hierarchy": ["ball_fault", "0g"],
      "relative_path": "overhang/ball_fault/0g/14.1312.csv",
      "rotational_frequency_hz": 14.1312,
      "rotational_speed_rpm": 847.872
    }
  }
}
```

### MIMII 文档结构

```json
{
  "info_features": {
    "dataset_UUID": "mimii_batch_upload",
    "device_id": "BATCH_UPLOAD_NORMAL",
    "testing": false,
    "obj_ID": "id_00",
    "upload_complete": true,
    "file_hash": "...",
    "file_size": 2560080,
    "duration": 10.0,
    "label": "normal",
    "sample_rate": 16000,
    "channels": 1,
    "raw_format": "WAV",
    "target_channel": [5],
    "mimii_metadata": {
      "fault_type": "normal",
      "snr": "-6_dB",
      "machine_type": "fan",
      "obj_ID": "id_00",
      "relative_path": "-6_dB_fan/fan/id_00/normal/00000000.wav",
      "file_id_number": 0
    }
  }
}
```

## 共同字段规范

所有三个上传器的 `info_features` 现在都统一包含：

### 必需字段
- `dataset_UUID`: 数据集标识
- `device_id`: 设备 ID
- `testing`: 是否为测试数据
- `obj_ID`: 对象 ID（CPC 为 "-1"，MAFAULDA 为 "-1"，MIMII 从路径提取）
- `upload_complete`: 上传是否完成
- `file_hash`: 文件哈希值
- `file_size`: 文件大小
- `duration`: 音频时长
- `label`: 标签
- `target_channel`: 目标通道

### 音频格式字段（新增统一）
- `sample_rate`: 采样率
- `channels`: 声道数
- `raw_format`: 原始格式

### 已删除字段
- ❌ `upload_time`（MAFAULDA 和 MIMII）
- ❌ `batch_upload_metadata`（MAFAULDA 和 MIMII）
- ❌ `analysis_config`（CPC）

## 测试验证

所有修改已通过测试：

```bash
cd debug_tools/batch_upload
python test_all_changes.py
```

测试项目：
1. ✓ CPC obj_ID 设置为 -1
2. ✓ CPC TARGET_CHANNEL 存在，ANALYSIS_CONFIG 已删除
3. ✓ MAFAULDA fault_variant 逻辑正确
4. ✓ MAFAULDA fault_variant 平均分配采样
5. ✓ MIMII fault_type 已添加
6. ✓ 所有上传器的字段统一

## 注意事项

1. **CPC**：音频统一为单声道 16kHz，obj_ID 固定为 "-1"
2. **MAFAULDA**：CSV 格式，sample_rate 为 51200 Hz，会根据路径层级决定是否记录 fault_variant
3. **MIMII**：WAV 格式，obj_ID 从路径中提取（id_00, id_02 等）
4. **平均采样**：MAFAULDA 使用 fault_variant 进行平均分配，MIMII 使用文件夹路径

## 文件修改列表

- `cpc_upload/config.py`
- `cpc_upload/cpc_batch_upload.py`
- `mafaulda_upload/mafaulda_batch_upload.py`
- `mimii_upload/mimii_batch_upload.py`
- `test_all_changes.py`（新增）

## 版本信息

- 修改日期：2025-10-28
- 基于要求：problem.txt
- 测试状态：✓ 全部通过
