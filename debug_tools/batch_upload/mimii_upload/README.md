# MIMII 批量資料上傳工具 v2.0

## 概述

這是一個專門為 MIMII 資料集設計的批量上傳工具，能夠自動解析路徑中的所有參數並上傳至 MongoDB 資料庫。

## 主要功能

1. **自動路徑解析**：自動從檔案路徑提取以下參數
   - SNR 等級（-6_dB, 0_dB, 6_dB）
   - 機器類型（pump, fan, slider, valve）
   - obj_ID（id_00, id_02, id_04, id_06）
   - 標籤（normal, abnormal）
   - 檔案序號

2. **完整元數據記錄**：生成的 MongoDB 文檔包含
   - 基本資訊（AnalyzeUUID, 時間戳記等）
   - 檔案資訊（檔案大小、時長、雜湊值）
   - MIMII 特定元數據（SNR, machine_type, obj_ID 等）
   - 批次上傳元數據

3. **支援功能**
   - 直接寫入 MongoDB + GridFS
   - 並行上傳（可設定線程數）
   - 斷點續傳（自動跳過已上傳檔案）
   - Dry Run 預覽模式
   - 完整的進度追蹤與錯誤處理

## MIMII 資料集結構

```
mimii_data/
├── 6_dB_pump/
│   └── pump/
│       ├── id_00/
│       │   ├── normal/
│       │   │   ├── 00000000.wav
│       │   │   └── ...
│       │   └── abnormal/
│       │       └── ...
│       ├── id_02/
│       └── id_04/
├── -6_dB_pump/
├── 0_dB_pump/
└── ... (其他 SNR 和機器類型組合)
```

## 配置說明

編輯 `config.py` 中的設定：

### 1. 上傳資料夾路徑

```python
UPLOAD_DIRECTORY = r"C:\path\to\mimii_data"
```

**重要**：設定到 `mimii_data` 根目錄，以便掃描所有 SNR、機器類型和 obj_ID。

### 2. MongoDB 配置

```python
MONGODB_CONFIG = {
    'host': 'localhost',
    'port': 27021,
    'username': 'web_ui',
    'password': 'your_password',
    'database': 'web_db',
    'collection': 'recordings'
}
```

### 3. 上傳行為配置

```python
UPLOAD_BEHAVIOR = {
    'skip_existing': True,       # 是否跳過已存在的檔案
    'check_duplicates': True,    # 是否檢查重複檔案
    'concurrent_uploads': 3,     # 並行上傳數量
    'retry_attempts': 3,         # 失敗重試次數
    'retry_delay': 2,            # 重試延遲(秒)
    'per_label_limit': 0,        # 限制每個 label 上傳數量, 0 為不限制
}
```

## 使用方式

### 1. 測試配置

```bash
python config.py
```

### 2. Dry Run 模式（預覽）

```bash
python mimii_batch_upload.py
# 選擇選項 1
```

Dry Run 模式會：
- 掃描所有檔案
- 生成每個標籤的樣本 JSON 預覽
- 不實際上傳到資料庫
- 預覽檔案儲存在 `reports/dry_run_previews/` 目錄

### 3. 正式上傳

```bash
python mimii_batch_upload.py
# 選擇選項 2
# 確認後開始上傳
```

## 生成的 MongoDB 文檔結構

```json
{
  "AnalyzeUUID": "uuid-string",
  "current_step": 0,
  "created_at": "2025-10-28T13:37:23.657272",
  "updated_at": "2025-10-28T13:37:23.657272",
  "files": {
    "raw": {
      "fileId": "gridfs-file-id",
      "filename": "00000000.wav",
      "type": "wav"
    }
  },
  "analyze_features": {
    "active_analysis_id": null,
    "latest_analysis_id": null,
    "latest_summary_index": null,
    "total_runs": 0,
    "last_requested_at": null,
    "last_started_at": null,
    "last_completed_at": null,
    "runs": []
  },
  "info_features": {
    "dataset_UUID": "mimii_batch_upload",
    "device_id": "BATCH_UPLOAD_NORMAL",
    "testing": false,
    "obj_ID": "id_00",
    "upload_time": "2025-10-28T13:37:23.657272",
    "upload_complete": true,
    "file_hash": "sha256-hash",
    "file_size": 2560080,
    "duration": 10.0,
    "label": "normal",
    "batch_upload_metadata": {
      "upload_method": "BATCH_UPLOAD",
      "upload_timestamp": "2025-10-28T13:37:23.657272",
      "label": "normal",
      "source": "mimii_batch_uploader_v2.0"
    },
    "mimii_metadata": {
      "snr": "-6_dB",
      "machine_type": "fan",
      "obj_ID": "id_00",
      "relative_path": "-6_dB_fan/fan/id_00/normal/00000000.wav",
      "file_id_number": 0
    },
    "target_channel": [5]
  }
}
```

## 測試工具

專案包含三個測試腳本：

1. **test_path_parsing.py**：測試路徑解析邏輯
   ```bash
   python test_path_parsing.py
   ```

2. **test_scan.py**：測試檔案掃描功能
   ```bash
   python test_scan.py
   ```

3. **test_dry_run.py**：測試 Dry Run 預覽生成
   ```bash
   python test_dry_run.py
   ```

## 報告與日誌

- **上傳報告**：`reports/upload_report_YYYYMMDD_HHMMSS.json`
- **日誌檔案**：`reports/batch_upload.log`
- **Dry Run 預覽**：`reports/dry_run_previews/dry_run_YYYYMMDD_HHMMSS/`
- **進度記錄**：`reports/upload_progress.json`

## 統計資訊

根據測試掃描結果，MIMII 資料集包含：

- **總檔案數**：52,168 個音頻檔案

- **標籤分布**：
  - normal: 42,424 個 (81.3%)
  - abnormal: 9,744 個 (18.7%)

- **SNR 分布**：
  - -6_dB: 18,021 個
  - 0_dB: 18,021 個
  - 6_dB: 16,126 個

- **機器類型分布**：
  - fan: 16,653 個
  - pump: 10,703 個
  - slider: 12,300 個
  - valve: 12,512 個

- **obj_ID 分布**：
  - id_00: 15,323 個
  - id_02: 13,962 個
  - id_04: 11,273 個
  - id_06: 11,610 個

## 注意事項

1. 確保 MongoDB 服務正在運行且可連接
2. 確保有足夠的磁碟空間儲存 GridFS 檔案
3. 建議先使用 Dry Run 模式驗證設定
4. 上傳過程中請勿中斷程式，否則需要依賴斷點續傳功能
5. 定期檢查日誌檔案以監控上傳狀態

## 版本歷史

### v2.0 (2025-10-28)
- ✓ 完整的 MIMII 路徑參數解析
- ✓ 支援 SNR、machine_type、obj_ID 自動提取
- ✓ 完整的 mimii_metadata 記錄
- ✓ 改進的文檔結構

### v1.0
- 基本的 normal/abnormal 上傳功能
- 簡單的路徑偵測

## 技術支援

如遇問題，請檢查：
1. `reports/batch_upload.log` 日誌檔案
2. 配置檔案設定是否正確
3. MongoDB 連接是否正常
4. 檔案路徑結構是否符合預期格式
