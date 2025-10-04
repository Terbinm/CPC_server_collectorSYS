# Analyze Features 資料結構說明（簡化版）

## 統一格式結構

每個處理步驟的結果都遵循以下統一格式：

```json
{
  "features_step": <步驟編號>,
  "features_state": "completed",
  "features_name": "<步驟名稱>",
  "features_data": [<具體資料陣列>],
  "processor_metadata": {<處理器元資料>},
  "error_message": null,
  "started_at": <時間>,
  "completed_at": <時間>
}
```

## Step 1: Audio Slicing

### features_data 格式
```json
[
  {
    "selec": 1,
    "channel": 6,
    "start": 0.0,
    "end": 0.16,
    "bottom_freq": 0.002,
    "top_freq": 8.0
  },
  {
    "selec": 2,
    "channel": 6,
    "start": 0.2,
    "end": 0.36,
    "bottom_freq": 0.002,
    "top_freq": 8.0
  }
]
```

### processor_metadata 格式
```json
{
  "segments_count": 50,
  "total_duration": 10.0
}
```

## Step 2: LEAF Features（簡化版）

### ✨ 新的 features_data 格式（二維陣列）
```json
[
  [0.3178420960903168, 0.2894523143768311, ..., 0.3178386390209198],
  [0.31787213683128357, 0.2894830107688904, ..., 0.31784170866012573],
  [0.3178693652153015, 0.28948208689689636, ..., 0.31784239411354065]
]
```
- 每個內層陣列是一個 40 維的特徵向量
- 陣列索引對應 Step 1 的 selec 編號（從 0 開始）
- 如果某個切片提取失敗，使用零向量 `[0.0, 0.0, ..., 0.0]`

### processor_metadata 格式
```json
{
  "extractor_type": "LEAF",
  "feature_dtype": "float32",
  "n_filters": 40,
  "sample_rate": 16000,
  "window_len": 25.0,
  "window_stride": 10.0,
  "pcen_compression": true,
  "device": "cpu",
  "feature_dim": 40
}
```

### 優點
- ✅ **節省空間**: 去除每個切片的重複元資料
- ✅ **提升效率**: 減少資料傳輸和解析時間
- ✅ **簡化使用**: Step 3 直接使用二維陣列進行計算
- ✅ **保持對應**: 透過索引與 Step 1 的切片資訊對應

## Step 3: Classification

### features_data 格式（保持不變）
```json
[
  {
    "segment_id": 1,
    "prediction": "normal",
    "confidence": 0.85,
    "proba_normal": 0.85,
    "proba_abnormal": 0.15
  },
  {
    "segment_id": 2,
    "prediction": "abnormal",
    "confidence": 0.72,
    "proba_normal": 0.28,
    "proba_abnormal": 0.72
  }
]
```

### processor_metadata 格式
```json
{
  "method": "rf_model",
  "model_type": "RandomForest",
  "aggregation": "mean",
  "feature_normalized": true,
  "total_segments": 50,
  "normal_count": 30,
  "abnormal_count": 18,
  "unknown_count": 2,
  "normal_percentage": 60.0,
  "abnormal_percentage": 36.0,
  "final_prediction": "normal",
  "average_confidence": 0.78
}
```

## 資料使用範例

### 讀取 LEAF 特徵
```python
# 獲取記錄
record = db.recordings.find_one({'AnalyzeUUID': 'xxx'})
analyze_features = record['analyze_features']

# Step 1: 切片資訊
slice_step = analyze_features[0]
slices = slice_step['features_data']

# Step 2: LEAF 特徵
leaf_step = analyze_features[1]
features = leaf_step['features_data']  # [[feat1], [feat2], ...]

# 獲取第 3 個切片的資訊和特徵
slice_info = slices[2]  # {'selec': 3, 'start': 0.4, 'end': 0.56, ...}
slice_feature = features[2]  # [0.318, 0.289, ..., 0.317] (40維)
```

### 從 Step 2 過渡到 Step 3
```python
# Step 2 輸出
leaf_features = [[feat1], [feat2], [feat3], ...]  # 二維陣列

# Step 3 直接使用
classifier.classify(leaf_features)

# 無需再從每個字典中提取 feature_vector
```

## 向後相容性說明

**注意**: 本次修改**不提供**向後相容性，因為：
1. 使用者明確表示不需要資料遷移
2. 舊格式和新格式差異較大，相容處理會增加複雜度
3. 新系統啟動後，所有新資料將使用新格式

如需處理舊資料，請：
- 重新處理舊記錄（刪除後重新上傳）
- 或手動調整程式碼以支援舊格式讀取