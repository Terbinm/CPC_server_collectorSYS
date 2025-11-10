# 移除 Redis 的替代方案規劃

## 背景與現況
- 目前 `core/state_management/utils/redis_handler.py` 提供單例連線，負責節點註冊、心跳 TTL、節點查詢，以及 `config:version` 版本遞增。
- `core/state_management/api/node_api.py`、`services/node_monitor.py`、`services/config_manager.py`、`models/*` 都透過 `redis_handler` 讀寫節點狀態與配置版本。
- Analysis Service V2 的節點只需呼叫 REST API (`/api/nodes/register`, `/api/nodes/heartbeat`)，對底層儲存無感；因此只要 API 行為不變，就能透明地替換後端儲存。
- 系統中已經有 MongoDB（核心資料庫）以及 Flask 內建可用的 SQLite；本規劃採用 MongoDB 作為唯一儲存層以移除 Redis。

## 方案 A：以 MongoDB 單一儲存層取代 Redis

### 核心概念
利用 MongoDB 的 TTL Index 與原生原子操作，將節點狀態與配置版本存回核心資料庫，維持單一儲存層，降低維運負擔。

### 資料模型
1. `nodes_status` 集合（新）
   - `_id`: `node_id`
   - `info`: Redis `info` 欄位的 JSON
   - `current_tasks`: 整數
   - `last_heartbeat`: ISODate（建立 TTL Index，`expireAfterSeconds = NODE_HEARTBEAT_TIMEOUT`）
   - `status_cache`: 可選，快取最後一次判定狀態
2. `system_metadata` 集合（可沿用或新增）
   - `_id`: `config_version`
   - `value`: 整數

### 服務調整
1. **共用儲存層元件**
   - 新增 `core/state_management/models/node_status.py`，封裝 Mongo 查詢、upsert、TTL index 建立。
   - 新建 `ConfigVersionRepository`，以 `findOneAndUpdate` / `$inc` 取代 `redis_handler.increment_config_version`。
2. **API 與服務**
   - `node_api`：`register_node`、`heartbeat` 直接呼叫新的 repository；`get_all_nodes` 透過 `nodes_status` 查詢並計算 `online/offline`。
   - `node_monitor`：改成直接查 `nodes_status`，無需 Redis scan。
   - `config_manager` 與 `models/*`：注入 `ConfigVersionRepository` 以讀/寫版本號，其他流程不變。
3. **資料遷移**
   - 啟動腳本：從 Redis dump 現有 `nodes:*`、`nodes:heartbeat:*`，轉寫入 `nodes_status`；若可接受短暫重註冊，也可直接讓節點重新心跳。
   - 將 `config:version` 寫入 `system_metadata`，之後 Redis 可停用。
4. **部署調整**
   - 移除 `redis` service（`core/docker-compose.yml`、`docker_run.md`）。
   - 取消 `requirements.txt` 的 `redis` 依賴。

## 整體整合藍圖：儲存層重構 + WebUI
- **階段 0：基礎準備** — 盤點 Redis 既有資料鍵、確認 Mongo index 欄位，以及拉出 `core/state_management` 目前 API 的呼叫面。
- **階段 1：儲存層重構（方案 A）** — 先完成 Mongo repository、資料遷移與 Redis 移除，確保 REST API 行為維持不變。
- **階段 2：WebUI API 擴充** — 在新 repository 之上補齊 GUI 需求的後端端點（節點查詢、配置檢視/編修、操作審計）。
- **階段 3：WebUI 前端實作與整合** — 建立管理員登入入口、儀表板與配置編輯流，驗證與既有 CLI/腳本協同運作。
- **階段 4：驗證與切換** — 進行整合測試 (E2E)、安全性檢測與回滾策略演練，最後下線 Redis 併發佈 WebUI。

## 方案 B：State Management WebUI 實作

### 目標與使用者
- **目標**：提供管理員登入後即可視覺化監控節點狀態、調整配置版本、追蹤操作紀錄，減少直接透過 API/CLI 的門檻。
- **角色**：`Platform Admin`（全權）與 `Observer`（唯讀）；之後可再擴充至客製權限。
- **成功指標**：節點異常反應時間下降、配置異動流程可追蹤、Redis 完全移除後仍維持作業效率。

### 後端架構調整
1. **Blueprint / 模組劃分**
   - 新增 `core/state_management/webui`（Flask Blueprint）供頁面與 `admin/api/*` 端點使用。
   - Repository 層沿用方案 A 的 `NodeStatusRepository`、`ConfigVersionRepository`，避免重複查詢邏輯。
2. **身份驗證**
   - 建立 `AuthService`，採 JWT + HttpOnly Cookie；登入資料寫入 Mongo `admin_users` 集合（含雜湊密碼、角色）。
   - Flask before_request 驗證權杖並將角色資訊注入 g 物件供 API 使用。
3. **新 API 端點規劃**
   - `POST /admin/api/login`、`POST /admin/api/logout`
   - `GET /admin/api/nodes?status=online&region=xx`
   - `POST /admin/api/nodes/<node_id>/actions/force-offline`
   - `GET /admin/api/configs`、`GET /admin/api/configs/<version>`、`POST /admin/api/configs`（提交新草稿）
   - `GET /admin/api/audits`（查操作紀錄）
4. **審計與事件**
   - 新增 `admin_audit_logs` 集合，記錄操作人、操作對象、前後狀態與時間戳。
   - 重要操作（發佈配置、強制下線節點）推送到現有通知機制或新增 Webhook/SMS Gateway。
5. **即時狀態**
   - 若需要秒級刷新，可在 Flask 中加上 Server-Sent Events 或以 Socket.IO（Flask-SocketIO）訂閱 Mongo 變更；初期可 5 秒輪詢 REST API，待穩定後再升級。

### 前端實作建議
1. **技術選擇**
   - 採 Vite + Vue 3（或 React）單頁式應用，透過 Axios 呼叫 `admin/api/*`；若希望單一語言也可用 Flask + HTMX/Alpine.js 伺服端渲染。
   - 使用 Tailwind CSS / DaisyUI 快速建立一致 UI；Chart.js 或 ECharts 呈現節點統計。
2. **模組規畫**
   - 儀表板：節點總數、線上/離線比、平均心跳延遲、最後一次配置發佈時間。
   - 節點視圖：以表格顯示 `node_id`、版本、CPU/任務負載、最後心跳；支援篩選、批次操作。
   - 配置管理：歷史版本列表、差異比較（可利用 Monaco Editor Diff）、建立草稿、送審/發佈流程。
   - 操作紀錄：篩選使用者、動作、結果；提供匯出 CSV。
   - 通知中心：顯示 heartbeat 超時、部署失敗等系統事件。
3. **狀態管理**
   - 前端使用 Pinia/Redux 只存放介面狀態，所有儲存資料仍在 Mongo。
   - 與後端透過 `/admin/api` 命名空間隔離，避免與現有 `/api/nodes` 混淆。
4. **表單/流程**
   - 配置編輯器支援 YAML/JSON schema 驗證，提交前調用後端 `dry-run` API 驗證語法。
   - 節點操作需二次確認 modal 並寫入審計日誌。

### 權限與操作流程
1. **登入與會話管理**
   - 管理員輸入憑證後，後端驗證密碼雜湊，若成功則產生 JWT 搭配角色資訊並以 HttpOnly Cookie 回傳。
   - 伺服端維護 `active_sessions` 集合，記錄 token jti、登入 IP/UA、到期時間，提供異地登入分析與強制登出。
2. **節點監控流程**
   - WebUI 週期性向 `GET /admin/api/nodes` 拉取節點列表，前端根據 `last_heartbeat` 計算狀態標籤。
   - 管理員點選節點可觸發 `GET /admin/api/nodes/<node_id>`，顯示詳細指標與最近操作記錄。
   - 若需隔離節點，呼叫 `POST /admin/api/nodes/<node_id>/actions/force-offline`，後端更新 `nodes_status` 並記錄審計。
3. **配置管理流程**
   - 建立草稿：`POST /admin/api/configs` 接收內容與說明，狀態標記為 `draft`。
   - 審核：`POST /admin/api/configs/<id>/actions/approve`，需 `Platform Admin` 權限。
   - 發佈：`POST /admin/api/configs/<id>/actions/publish`，後端遞增 `config_version` 並發送通知。
4. **審計追蹤**
   - 所有 `POST/PUT/DELETE` 請求透過 decorator 自動寫入 `admin_audit_logs`，包含 payload hash、舊新值摘要與 request id。
   - WebUI 提供篩選介面，支援依使用者、節點、配置版本查詢，並可導出 JSON/CSV。

### 整體測試與驗證
1. **單元測試**：為 repository、AuthService、新 API 補足 pytest 用例（mock Mongo）。
2. **整合測試**：使用 `docker-compose` 啟動 Mongo + Flask + WebUI，透過 Playwright/Cypress 自動化操控登入、節點視圖與配置發佈。
3. **安全檢查**
   - CSRF：所有有副作用的 API 加 CSRF token（或僅允許 JSON + 自定 Header）。
   - 權限：以 decorator 驗證角色；關鍵操作需 `Platform Admin`。
   - 日誌：集中至 `admin_audit_logs` 並輸出至 ELK/CloudWatch 方便追蹤。
4. **回滾計畫**：WebUI 啟用初期以 feature flag 控制；若出現問題可快速關閉 UI 端點，仍保留 REST API。
