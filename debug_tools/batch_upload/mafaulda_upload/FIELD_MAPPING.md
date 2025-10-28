# MAFAULDA 批次上傳欄位判斷說明

本文說明 `mafaulda_upload/batch_upload.py` 在產生 MongoDB 紀錄時，各欄位的來源與判斷邏輯。若需參考實作細節，可對照 `batch_upload.py` 及 `config.py` 內相對應的程式段落。

## 組態來源

- `UploadConfig.DATASET_CONFIG`：定義 `dataset_UUID` 與 `obj_ID` 等固定欄位。
- `UploadConfig.CSV_CONFIG`：提供預設取樣頻率 (`sample_rate_hz`) 與預期通道數 (`expected_channels`)。
- `UploadConfig.LABEL_FOLDERS`：決定哪些第一層資料夾會被視為有效標籤；未列入的資料夾會被忽略。

## 主要欄位判斷

| 欄位 | 判斷/來源說明 |
| ---- | ------------- |
| `AnalyzeUUID` | 每次上傳前以 `uuid.uuid4()` 產生全新 UUID (`MongoDBUploader.upload_file`)。 |
| `info_features.obj_ID` | 直接取自 `UploadConfig.DATASET_CONFIG['obj_ID']` (`config.py` 可調整)。 |
| `info_features.dataset_UUID` | 直接取自 `UploadConfig.DATASET_CONFIG['dataset_UUID']`。 |
| `info_features.device_id` | 以 `BATCH_UPLOAD_{label.upper()}` 組成，`label` 由路徑判斷（見下）。 |
| `info_features.label` | 第一層資料夾名稱對應 `UploadConfig.LABEL_FOLDERS` 的 key；若資料夾不在設定中則整個檔案略過 (`BatchUploader.scan_directory`)。 |
| `info_features.file_hash` | 針對檔案內容計算 SHA-256 (`BatchUploader.calculate_file_hash`)。 |
| `info_features.file_size` | 使用 `Path.stat().st_size` 取得原始檔案大小（位元組）。 |
| `info_features.duration` | 僅對 `.csv` 檔案計算：先逐行統計總筆數 `num_samples`，再以 `sample_rate_hz`（預設 51,200 Hz）換算時間 `num_samples / sample_rate_hz`。若任一步驟失敗則為 `None` (`BatchUploader._get_csv_metadata` 與 `get_file_metadata`)。 |
| `info_features.batch_upload_metadata` | 固定填入上傳方式、時間、來源程式名稱；若有 `fault_condition` 亦會附帶。 |
| `info_features.mafaulda_metadata.fault_type` | 等同 `label`。 |
| `info_features.mafaulda_metadata.fault_variant` | 取路徑第二層資料夾（例如 `underhang/ball_fault/6g` → `ball_fault`）。 |
| `info_features.mafaulda_metadata.fault_condition` | 以第二層之後的路徑名稱以 `/` 串接，例如 `underhang/ball_fault/6g`。 |
| `info_features.mafaulda_metadata.fault_hierarchy` | 將第二層開始直到檔案前一層的資料夾順序存成陣列。 |
| `info_features.mafaulda_metadata.relative_path` | 以上傳根目錄為參考，紀錄相對路徑（使用 `/` 分隔）。 |
| `info_features.mafaulda_metadata.rotational_frequency_hz` | 嘗試將檔名（不含副檔名）轉換成數值，例如 `13.5168.csv` → 13.5168。若轉換失敗則忽略。 |
| `info_features.mafaulda_metadata.rotational_speed_rpm` | 若有 `rotational_frequency_hz`，再乘以 60 計算成 RPM。 |
| `info_features.mafaulda_metadata.num_samples` | `.csv` 檔案逐行統計的資料列數。 |
| `info_features.mafaulda_metadata.num_channels` | `.csv` 第一列非空行的欄位數，用於檢查是否符合 `expected_channels`。 |
| `info_features.mafaulda_metadata.sample_rate_hz` | 來自 `UploadConfig.CSV_CONFIG['sample_rate_hz']`。 |

## 標籤與檔案篩選

- 只處理 `UploadConfig.SUPPORTED_FORMATS` 列出的副檔名（目前為 `.csv`）。
- 若第一層資料夾未出現在 `LABEL_FOLDERS`，日誌會顯示警告並跳過該檔案，計入統計 `filtered_invalid_label`。

## 相關提醒

- 調整 `obj_ID` 或 `dataset_UUID` 時，請更新 `config.py` 中的 `DATASET_CONFIG`。
- `duration` 計算依賴 `CSV_CONFIG['sample_rate_hz']`，若資料集實際取樣率不同需同步修改。
- 若 CSV 檔案欄位數與 `expected_channels` 不一致，程式會輸出警告方便檢查資料異常。*** End Patch
