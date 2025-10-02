# RF 模型訓練與部署套件

## 📦 套件內容

本套件提供完整的隨機森林(Random Forest)分類器訓練與部署工具,用於音頻異常檢測系統。

### 產出檔案清單

```
RF_Model_Package/
├── train_rf_model.py              # 模型訓練主腳本
├── evaluate_model.py              # 模型評估工具
├── step3_classifier_updated.py   # 更新的分類器(支援 RF 模型)
├── quick_start.py                 # 快速啟動腳本(一鍵完成訓練與部署)
├── RF_MODEL_GUIDE.md             # 完整使用指南
└── README.md                      # 本文件
```

---

## 🚀 快速開始

### 方法 1: 使用快速啟動腳本(推薦)

最簡單的方式是使用 `quick_start.py`,它會自動完成所有步驟:

```bash
# 1. 將所有檔案放到專案根目錄
cd /path/to/your/project

# 2. 執行快速啟動腳本
python quick_start.py
```

腳本會自動:
- ✅ 檢查環境和依賴套件
- ✅ 檢查 MongoDB 訓練資料
- ✅ 訓練 RF 模型
- ✅ 評估模型效能
- ✅ 部署到分析服務

### 方法 2: 手動執行(進階使用者)

如果您需要更多控制,可以手動執行各個步驟:

```bash
# 步驟 1: 訓練模型
python train_rf_model.py

# 步驟 2: 評估模型
python evaluate_model.py

# 步驟 3: 手動部署(參考 RF_MODEL_GUIDE.md)
```

---

## 📋 前置需求

### 1. 系統需求

- Python 3.8+
- MongoDB 正常運行
- 足夠的訓練資料(建議 200+ 筆,最少 50 筆)

### 2. 依賴套件

```bash
pip install scikit-learn matplotlib seaborn --break-system-packages
```

### 3. 資料準備

確保 MongoDB 中有已完成分析且有標籤的記錄:

```python
# 檢查資料數量
from pymongo import MongoClient

client = MongoClient("mongodb://web_ui:hod2iddfsgsrl@localhost:27020/admin")
db = client['web_db']

count = db.recordings.count_documents({
    'current_step': 4,
    'analysis_status': 'completed',
    'info_features.label': {'$in': ['normal', 'abnormal']}
})

print(f"可用訓練資料: {count} 筆")
```

如果資料不足,請使用 `batch_upload` 工具上傳更多已標記的音頻。

---

## 📝 檔案說明

### 1. train_rf_model.py

**功能**: 從 MongoDB 讀取資料並訓練隨機森林模型

**使用方式**:
```bash
python train_rf_model.py
```

**輸出**:
- `models/rf_classifier.pkl` - 訓練好的模型
- `models/feature_scaler.pkl` - 特徵標準化器
- `models/model_metadata.json` - 模型元資料
- `training_reports/` - 訓練報告和視覺化圖表

**配置**:
在腳本內的 `ModelConfig` 類中調整參數:
- 特徵聚合方式: `FEATURE_CONFIG['aggregation']`
- 模型參數: `MODEL_CONFIG['rf_params']`
- 訓練配置: `TRAINING_CONFIG`

### 2. evaluate_model.py

**功能**: 評估已訓練的模型效能

**使用方式**:
```bash
python evaluate_model.py
```

**評估模式**:
1. 跨資料集評估 - 在所有可用資料上評估
2. 單一記錄預測 - 測試特定記錄的預測結果
3. 顯示模型資訊 - 查看模型參數和訓練歷史

**輸出**:
- `evaluation_results/cross_dataset_evaluation.json` - 評估報告
- `evaluation_results/confusion_matrix_eval.png` - 混淆矩陣
- `evaluation_results/roc_curve_eval.png` - ROC 曲線

### 3. step3_classifier_updated.py

**功能**: 更新的分類器,支援載入和使用訓練好的 RF 模型

**特性**:
- ✅ 自動載入模型、Scaler 和元資料
- ✅ 支援特徵聚合
- ✅ 向後相容(模型不存在時自動降級為隨機分類)
- ✅ 詳細的預測資訊(包含機率)

**部署**:
```bash
# 替換原始分類器
cp step3_classifier_updated.py \
   a_sub_system/analysis_service/processors/step3_classifier.py
```

### 4. quick_start.py

**功能**: 一鍵完成訓練與部署的快速啟動腳本

**使用方式**:
```bash
python quick_start.py
```

**執行步驟**:
1. 環境檢查 - 檢查依賴套件和必要檔案
2. 資料檢查 - 檢查 MongoDB 訓練資料數量和品質
3. 模型訓練 - 自動執行訓練流程
4. 模型評估 - 評估模型效能並給出建議
5. 模型部署 - 自動更新配置和替換分類器

**優點**:
- 自動化所有步驟
- 智能檢查和建議
- 安全備份原始檔案
- 清晰的進度顯示

### 5. RF_MODEL_GUIDE.md

**功能**: 完整的使用指南和參考文件

**內容**:
- 系統概述和工作流程
- 詳細的環境準備步驟
- 模型訓練教學
- 模型評估指南
- 部署步驟說明
- 配置參數詳解
- 常見問題解答
- 使用範例

---

## 🎯 典型工作流程

### 情境 1: 首次訓練與部署

```bash
# 1. 準備環境
pip install scikit-learn matplotlib seaborn --break-system-packages

# 2. 上傳訓練資料(如果還沒有)
cd a_sub_system/batch_upload
python batch_upload.py

# 3. 等待分析服務處理完成
cd ../analysis_service
python main.py
# 等待所有資料分析完成後按 Ctrl+C

# 4. 回到專案根目錄執行快速啟動
cd ../../
python quick_start.py

# 5. 按照提示完成訓練與部署

# 6. 重啟分析服務使用新模型
cd a_sub_system/analysis_service
python main.py
```

### 情境 2: 重新訓練模型(資料更新後)

```bash
# 1. 訓練新模型
python train_rf_model.py

# 2. 評估新模型
python evaluate_model.py

# 3. 如果效能改善,無需重新部署
#    (模型檔案已自動更新,重啟分析服務即可)

# 4. 重啟分析服務
cd a_sub_system/analysis_service
python main.py
```

### 情境 3: 調整模型參數

```bash
# 1. 編輯 train_rf_model.py 中的參數
#    例如: n_estimators, max_depth, aggregation 等

# 2. 重新訓練
python train_rf_model.py

# 3. 評估新模型
python evaluate_model.py

# 4. 重啟分析服務
```

### 情境 4: 回退到隨機分類器

```bash
# 1. 編輯配置檔案
#    a_sub_system/analysis_service/config.py
#    將 method 改為 'random'

# 2. (可選)恢復原始分類器
cd a_sub_system/analysis_service/processors
cp step3_classifier_backup.py step3_classifier.py

# 3. 重啟分析服務
cd ..
python main.py
```

---

## 📊 效能指標說明

### 準確率 (Accuracy)
- 定義: 預測正確的比例
- 範圍: 0-1 (越高越好)
- 建議: > 0.7 可部署, > 0.85 優秀

### 精確率 (Precision)
- 定義: 預測為異常的樣本中真正異常的比例
- 意義: 減少誤報(False Positive)
- 重要性: 在不希望誤報的場景中很重要

### 召回率 (Recall)
- 定義: 實際異常樣本中被正確預測的比例
- 意義: 減少漏報(False Negative)
- 重要性: 在不能漏掉異常的場景中很重要

### F1 分數
- 定義: 精確率和召回率的調和平均
- 意義: 平衡考慮精確率和召回率
- 建議: > 0.7 可接受

### ROC-AUC
- 定義: ROC 曲線下面積
- 範圍: 0-1 (越高越好)
- 建議: > 0.8 良好, > 0.9 優秀

---

## 🔧 進階配置

### 調整訓練參數

編輯 `train_rf_model.py` 中的 `ModelConfig`:

```python
# 特徵聚合方式
FEATURE_CONFIG = {
    'aggregation': 'mean'  # 可選: mean, max, median, all
}

# 隨機森林參數
MODEL_CONFIG = {
    'rf_params': {
        'n_estimators': 100,      # 樹的數量(增加可提升效能但變慢)
        'max_depth': None,        # 樹的最大深度(限制可防止過擬合)
        'min_samples_split': 2,   # 分裂所需最小樣本數
        'min_samples_leaf': 1,    # 葉節點最小樣本數
        'max_features': 'sqrt',   # 每次分裂考慮的特徵數
        'class_weight': 'balanced'  # 處理類別不平衡
    }
}

# 啟用網格搜尋
MODEL_CONFIG = {
    'grid_search': True,  # 自動尋找最佳參數
    'grid_params': {
        'n_estimators': [50, 100, 200],
        'max_depth': [None, 10, 20, 30]
    }
}
```

### 處理類別不平衡

如果 normal 和 abnormal 樣本數量差異很大:

1. **使用 class_weight='balanced'** (已預設啟用)
2. **調整採樣策略**:
```python
from imblearn.over_sampling import SMOTE

# 在訓練前使用 SMOTE 平衡資料
smote = SMOTE(random_state=42)
X_train_balanced, y_train_balanced = smote.fit_resample(X_train, y_train)
```

3. **調整決策閾值**:
```python
# 在 config.py 中
CLASSIFICATION_CONFIG = {
    'threshold': 0.3  # 降低閾值以提高召回率
}
```

---

## ❓ 常見問題

### Q: 訓練時記憶體不足怎麼辦?

**解決方案**:
```python
# 減少樹的數量
'n_estimators': 50  # 從 100 改為 50

# 限制樹的深度
'max_depth': 20  # 限制最大深度

# 減少並行數量
'n_jobs': 2  # 從 -1 改為 2
```

### Q: 模型準確率很低(<70%)怎麼辦?

**可能原因**:
1. 訓練資料不足
2. 資料標籤錯誤
3. 特徵聚合方式不適合
4. 類別嚴重不平衡

**解決方案**:
1. 增加訓練資料(建議 500+ 筆)
2. 檢查並修正資料標籤
3. 嘗試不同的聚合方式('mean', 'max', 'all')
4. 使用 SMOTE 或調整 class_weight

### Q: 部署後仍使用隨機分類?

**檢查清單**:
1. ✅ 確認 config.py 中 `method='rf_model'`
2. ✅ 確認 `model_path` 路徑正確
3. ✅ 確認模型檔案存在
4. ✅ 檢查分析服務日誌
5. ✅ 確認已重啟分析服務

### Q: 如何改善模型效能?

**策略**:
1. **增加資料量**: 更多資料通常能改善效能
2. **資料品質**: 確保標籤正確
3. **特徵工程**: 嘗試不同聚合方式
4. **超參數調整**: 使用網格搜尋
5. **集成學習**: 考慮 XGBoost 或 LightGBM

---

## 📚 參考資料

- **RF_MODEL_GUIDE.md** - 完整使用指南
- [Scikit-learn 文件](https://scikit-learn.org/stable/)
- [隨機森林介紹](https://en.wikipedia.org/wiki/Random_forest)
- [LEAF 論文](https://arxiv.org/abs/2101.08596)

---

## 🐛 故障排除

### 問題: ImportError: No module named 'sklearn'

```bash
pip install scikit-learn --break-system-packages
```

### 問題: MongoDB 連接失敗

檢查:
1. MongoDB 服務是否運行
2. 連接字串是否正確
3. 使用者權限是否足夠

### 問題: 訓練非常慢

調整:
```python
# 減少樹的數量
'n_estimators': 50

# 使用更少的 CPU
'n_jobs': 2

# 關閉交叉驗證
TRAINING_CONFIG = {
    'cross_validation': False
}
```

### 問題: 視覺化圖表無法生成

```bash
# 安裝或更新 matplotlib
pip install --upgrade matplotlib seaborn --break-system-packages

# 如果在無 GUI 環境(如伺服器),使用 Agg 後端
import matplotlib
matplotlib.use('Agg')
```

---

## 🔄 更新日誌

### v1.0 (2025-10-03)
- ✅ 初始版本發布
- ✅ RF 模型訓練功能
- ✅ 模型評估工具
- ✅ 自動部署腳本
- ✅ 完整文件

---

## 📧 技術支援

如有問題或建議:
1. 查看 **RF_MODEL_GUIDE.md** 中的常見問題
2. 檢查訓練日誌: `batch_upload.log`, `analysis_service.log`
3. 建立 Issue 或聯繫開發團隊

---

## 📄 授權

本套件為內部工具,請遵循專案授權規範使用。

---

**祝訓練順利! 🚀**
