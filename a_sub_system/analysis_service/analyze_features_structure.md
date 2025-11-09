# Analyze Features 資料結構說明（多次分析版）

## 多次分析容器

自 2025-01 起，`analyze_features` 由原本的「步驟列表」改為「分析容器」：

```json
"analyze_features": {
  "active_analysis_id": "run_20250125T120000Z",
  "latest_analysis_id": "run_20250125T120000Z",
  "latest_summary_index": 3,
  "total_runs": 3,
  "last_requested_at": "2025-01-25T12:00:00Z",
  "last_started_at": "2025-01-25T12:00:05Z",
  "last_completed_at": "2025-01-25T12:01:42Z",
  "runs": [
    {
      "analysis_id": "run_20250125T120000Z",
      "run_index": 3,
      "analysis_summary": {...},
      "analysis_context": {...},
      "steps": [
        {"features_step": 0, "features_state": "completed", ...},
        {"features_step": 1, ...},
        {"features_step": 2, ...},
        {"features_step": 3, ...}
      ],
      "requested_at": "2025-01-25T11:59:00Z",
      "started_at": "2025-01-25T12:00:05Z",
      "completed_at": "2025-01-25T12:01:42Z",
      "error_message": null
    }
  ]
}
```

- **active_analysis_id**：當前正在執行的分析（若有）  
- **latest_analysis_id**：最後一次成功或正在執行的分析 ID  
- **latest_summary_index**：1-based index，指向 `runs` 中最新完成分類的紀錄  
- **total_runs / last_* 欄位**：放在容器頂層，避免再巢狀 `metadata`  
- **runs**：歷史紀錄，每個 run 內含完整步驟與上下文  

> 舊有資料若仍是陣列格式，系統會在重新分析時自動轉換；程式碼層面仍應使用 `dict` 與 `runs` 來讀取，以確保未來相容性。

## 步驟統一格式

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

## Step 0: Audio Conversion / Pass

所有分析都會寫入 Step 0：
- 如果需要轉檔，`features_state = "completed"`，`processor_metadata.converted_path` 指向新檔案。
- 若原始檔案已符合條件，仍會記錄 Step 0，但 `features_state = "pass"`，metadata 會註記 `needs_conversion: false`，確保各 run 的步驟數量一致。

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

### 讀取最新完成的 LEAF 特徵
```python
record = db.recordings.find_one({'AnalyzeUUID': 'xxx'})
container = record.get('analyze_features', {})
runs = container.get('runs', [])

# 取得最新完成的 run（若 active_analysis_id 正在執行，可改用該 ID）
latest_id = container.get('latest_analysis_id')
target_run = next((r for r in runs if r.get('analysis_id') == latest_id), runs[-1] if runs else None)

if not target_run:
    raise ValueError("沒有可用的分析紀錄")

def find_step(run, step_no):
    return next((s for s in run.get('steps', []) if s.get('features_step') == step_no), None)

slice_step = find_step(target_run, 1)
leaf_step = find_step(target_run, 2)

slices = slice_step.get('features_data', [])
features = leaf_step.get('features_data', [])
slice_info = slices[2]
slice_feature = features[2]
```

### 從 Step 2 過渡到 Step 3
```python
leaf_step = find_step(target_run, 2)
leaf_features = leaf_step.get('features_data', [])  # 直接為二維陣列
classifier.classify(leaf_features)
```

## 向後相容性說明

**注意**: 本次修改**不提供**向後相容性，因為：
1. 使用者明確表示不需要資料遷移
2. 舊格式和新格式差異較大，相容處理會增加複雜度
3. 新系統啟動後，所有新資料將使用新格式

如需處理舊資料，請：
- 重新處理舊記錄（刪除後重新上傳）
- 或手動調整程式碼以支援舊格式讀取
