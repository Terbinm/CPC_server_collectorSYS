<!--
本檔為專案給 AI 編碼/助理代理的精簡指引。請以繁體中文回答與寫入註解，並遵守 repo 中現有慣例。
--> 

# CPC_server_collectorSYS — Copilot 使用說明（精簡版）

目的：快速讓 AI 代理在此程式庫內可立即上手與安全修改程式碼。

- **回答與註解語言**：所有回覆、log 與程式內註解皆使用繁體中文（見 `readme.md`）。
- **檔案開頭慣例**：每個 `.py` 檔案應在最上方以繁體中文摘要功能與用途。

**一、主要架構速覽（必要參考檔）**
- 前端 (Flask + SocketIO)：`a_sub_system/frontend/` — 入口 `flask_main.py`，事件在 `socket_events.py`。
- 分析服務（Analysis）：`a_sub_system/analysis_service/` — 入口 `analysis_main.py`，pipeline 在 `analysis_pipeline.py`，處理器在 `processors/`。
- 邊緣客戶端 (Edge)：`a_sub_system/edge_client/edge_client.py`，設定檔 `device_config.json`。
- 資料層：MongoDB + GridFS；GridFS 操作在 `gridfs_handler.py`，資料模型在 `models.py`。
- 系統設計與詳細說明：`系統架構文檔.md`（強烈建議閱讀）。

**二、重要開發/執行指令（例子）**
- 啟動 Flask 伺服器（開發）：
```powershell
cd a_sub_system/frontend
python flask_main.py
```
- 啟動分析服務（開發）：
```powershell
cd a_sub_system/analysis_service
python analysis_main.py
```
- 啟動 Edge client：
```powershell
cd a_sub_system/edge_client
python edge_client.py
```
- 使用 Docker Compose（整套服務）：
```powershell
docker-compose up -d
docker-compose logs -f
```

**三、專案特定約定（務必遵守）**
- 日誌：使用 `logging`，不要用 `print()`。
- 時間：內部儲存採 UTC，顯示使用 `Asia/Taipei`（見 `config.py`）。
- 檔案安全：上傳檔名須使用 `secure_filename()`；上傳必須檢查 `file_size` 與 SHA-256 `file_hash`。
- SocketIO 事件：常用事件包括 `register_device` / `record` / `new_recording` / `assign_id`（請參考 `socket_events.py` 與 `a_sub_system/frontend/CLAUDE.md` 範例）。

**四、常見修改場景（範例與注意事項）**
- 新增 API 路由：修改 `routes.py`，同時更新前端 template（`templates/`）與必要的 permission 檢查。
- 修改上傳流程：變更請在 `upload_recording` 路由、`gridfs_handler.py` 與 `models.py` 同步更新，並保留檔案 hash 驗證。
- 調整分析流程參數：修改 `a_sub_system/analysis_service/config.py`（例如 `SERVICE_CONFIG['use_change_stream']` 與 `polling_interval`），若更改監聽模式需同步檢查 `mongodb_watcher.py`。

**五、整合/佈署注意事項**
- MongoDB 預設在本專案 Docker Compose 中映射為 `27020`；在本機測試請確認相同 port 與 `MONGODB_CONFIG`（機密請使用環境變數）。
- 若要水平擴展 Flask + SocketIO，請記得啟用 sticky sessions 並使用共享狀態（Redis 等）。

**六、快速 API 範例（實作提示）**
- 發送錄音指令給裝置（Server 端示例）：
```python
# socket.emit('record', {'duration': 10})
```
- 客戶端上傳表單需包含欄位：`file`, `device_id`, `duration`, `file_size`, `file_hash`。

**七、安全與敏感資訊**
- repository 中可能包含範例密碼（例如 `web_ui` 帳號、`hod2iddfsgsrl`），請勿在公開環境直接使用，改以環境變數注入。

**八、可參考檔案（快速索引）**
- `系統架構文檔.md`：全面系統設計與部署。
- `a_sub_system/frontend/flask_main.py`, `socket_events.py`, `models.py`, `gridfs_handler.py`。
- `a_sub_system/analysis_service/analysis_main.py`, `analysis_pipeline.py`, `mongodb_watcher.py`。
- `a_sub_system/edge_client/edge_client.py`, `device_config.json`。

若有不清楚的部分或需要把某段 instruction 更擴充為更長的 AGENT.md，請告訴我要補強的區域（例如：SocketIO 測試流程、GridFS 效能建議、或分析服務本地測試指令）。
