# Analysis Service V2 - 架構說明

## 概述

Analysis Service V2 是一個基於 RabbitMQ 的分散式資料分析系統，支援多個 MongoDB 實例和動態配置管理。

## 主要變更 (相對於 V1)

### 移除
- ❌ MongoDB Watcher (Change Stream / Polling)
- ❌ 直接監聽資料庫變更

### 新增
- ✅ RabbitMQ 任務消費者
- ✅ 狀態管理系統整合
- ✅ 心跳機制
- ✅ 多 MongoDB 實例支援
- ✅ 動態配置管理

## 架構圖

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  上傳工具       │ ───> │  MongoDB (多實例) │      │ 狀態管理系統     │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                  │                          │
                                  │ Change Stream            │ 配置/路由
                                  ↓                          ↓
                         ┌──────────────────┐      ┌─────────────────┐
                         │  任務調度器       │ ───> │   RabbitMQ      │
                         │ (狀態管理系統)    │      │   任務隊列       │
                         └──────────────────┘      └─────────────────┘
                                                             │
                                                             │ 消費任務
                                                             ↓
                                                   ┌─────────────────┐
                                                   │ Analysis Node 1 │
                                                   │ Analysis Node 2 │
                                                   │ Analysis Node N │
                                                   └─────────────────┘
                                                             │
                                                             │ 心跳
                                                             ↓
                                                   ┌─────────────────┐
                                                   │  Redis (狀態)   │
                                                   └─────────────────┘
```

## 核心組件

### 1. 狀態管理系統 (`core/state_management`)

**職責**:
- 監聽所有 MongoDB 實例的新資料
- 根據路由規則匹配資料
- 創建分析任務並發送到 RabbitMQ
- 管理節點註冊和心跳
- 提供配置管理 API

**主要模組**:
- `task_scheduler.py` - 任務調度器
- `node_monitor.py` - 節點監控器
- `config_manager.py` - 配置管理器
- `api/` - REST API 端點

### 2. Analysis Service V2 (`a_sub_system/analysis_service_v2`)

**職責**:
- 從 RabbitMQ 消費分析任務
- 執行音訊分析流程
- 向狀態管理系統發送心跳
- 支援動態配置

**主要模組**:
- `analysis_main.py` - 主服務
- `rabbitmq_consumer.py` - RabbitMQ 消費者
- `heartbeat_sender.py` - 心跳發送器
- `state_client.py` - 狀態管理系統客戶端
- `analysis_pipeline.py` - 分析流程（保持不變）

## 資料流程

### 1. 資料上傳流程

```
1. 上傳工具 → MongoDB (某實例)
2. 狀態管理系統監聽到新資料
3. 讀取 info_features
4. 匹配路由規則
5. 創建任務 JSON
6. 發送到 RabbitMQ
```

### 2. 任務處理流程

```
1. Analysis Node 從 RabbitMQ 消費任務
2. 解析任務數據 (analyze_uuid, mongodb_instance, config_id)
3. 連接到指定的 MongoDB 實例
4. 獲取記錄
5. 執行分析流程:
   - Step 0: 音訊轉檔 (CSV → WAV)
   - Step 1: 音訊切割
   - Step 2: LEAF 特徵提取
   - Step 3: 分類預測
6. 更新結果到 MongoDB
7. ACK 消息到 RabbitMQ
```

### 3. 心跳機制

```
1. Analysis Node 啟動時向狀態管理系統註冊
2. 每 30 秒發送心跳到 /api/nodes/heartbeat
3. Redis 存儲心跳時間 (TTL 60秒)
4. 節點監控器檢查節點狀態
5. 超過 60 秒無心跳 → 標記為離線
```

## 配置說明

### RabbitMQ 配置 (`config.py`)

```python
RABBITMQ_CONFIG = {
    'host': 'localhost',           # RabbitMQ 主機
    'port': 5672,                  # AMQP 端口
    'username': 'admin',           # 用戶名
    'password': 'rabbitmq_admin_pass',
    'queue': 'analysis_tasks_queue',
    'prefetch_count': 1,           # 每次處理 1 個任務
    'max_retries': 3               # 最大重試次數
}
```

### 狀態管理系統配置

```python
STATE_MANAGEMENT_CONFIG = {
    'url': 'http://localhost:8000',
    'timeout': 10
}
```

## 任務消息格式

```json
{
  "task_id": "uuid",
  "mongodb_instance": "production",
  "analyze_uuid": "record_uuid",
  "analysis_method_id": "WAV_LEAF_RF_v1",
  "config_id": "config_001",
  "priority": 1,
  "created_at": "2025-11-10T10:00:00Z",
  "retry_count": 0,
  "metadata": {
    "rule_id": "rule_001",
    "rule_name": "CPC 批次上傳路由",
    "source_instance": "production"
  }
}
```

## 路由規則示例

```json
{
  "rule_id": "rule_001",
  "rule_name": "CPC 批次上傳路由",
  "priority": 1,
  "conditions": {
    "dataset_UUID": "cpc_batch_upload"
  },
  "actions": [
    {
      "analysis_method_id": "WAV_LEAF_RF_v1",
      "config_id": "config_001",
      "mongodb_instance": "production"
    }
  ],
  "enabled": true
}
```

## 啟動順序

### 1. 啟動核心服務

```bash
cd core
docker-compose up -d
```

啟動服務：
- MongoDB
- RabbitMQ (端口 5672, 15672)
- Redis (端口 6379)
- 狀態管理系統 (端口 8000)

### 2. 啟動分析節點

```bash
cd a_sub_system/analysis_service_v2
python analysis_main.py
```

## API 端點

### 狀態管理系統 API

#### 配置管理
- `GET /api/configs` - 獲取所有配置
- `POST /api/configs` - 創建配置
- `PUT /api/configs/<config_id>` - 更新配置
- `DELETE /api/configs/<config_id>` - 刪除配置
- `POST /api/configs/upload_model` - 上傳模型文件

#### 路由規則
- `GET /api/routing` - 獲取所有路由規則
- `POST /api/routing` - 創建路由規則
- `PUT /api/routing/<rule_id>` - 更新路由規則
- `DELETE /api/routing/<rule_id>` - 刪除路由規則

#### MongoDB 實例
- `GET /api/instances` - 獲取所有實例
- `POST /api/instances` - 創建實例配置
- `PUT /api/instances/<instance_id>` - 更新實例
- `POST /api/instances/<instance_id>/test` - 測試連接

#### 節點管理
- `POST /api/nodes/register` - 註冊節點
- `POST /api/nodes/heartbeat` - 發送心跳
- `GET /api/nodes` - 獲取所有節點
- `GET /api/nodes/<node_id>` - 獲取節點信息

## 環境變數

### Analysis Service V2

```bash
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27021
MONGODB_USERNAME=web_ui
MONGODB_PASSWORD=hod2iddfsgsrl

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=admin
RABBITMQ_PASSWORD=rabbitmq_admin_pass

# 狀態管理系統
STATE_MANAGEMENT_URL=http://localhost:8000
```

### 狀態管理系統

```bash
# MongoDB
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_USERNAME=web_ui
MONGODB_PASSWORD=hod2iddfsgsrl

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=admin
RABBITMQ_PASSWORD=rabbitmq_admin_pass

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=redis_password
```

## 監控與維護

### 查看 RabbitMQ 管理界面
- URL: http://localhost:15672
- 用戶名: admin
- 密碼: rabbitmq_admin_pass

### 查看任務隊列狀態
```bash
# 進入 RabbitMQ 容器
docker exec -it core_rabbitmq bash

# 查看隊列
rabbitmqctl list_queues
```

### 查看節點狀態
```bash
curl http://localhost:8000/api/nodes
```

### 查看配置版本
```bash
# 進入 Redis 容器
docker exec -it core_redis redis-cli -a redis_password

# 獲取配置版本
GET config:version

# 查看所有節點
KEYS nodes:*
```

## 故障排除

### 節點離線
1. 檢查心跳是否正常發送
2. 檢查 Redis 中的心跳記錄
3. 檢查網絡連接

### 任務未處理
1. 檢查 RabbitMQ 隊列中的消息數量
2. 檢查分析節點是否正常運行
3. 查看分析節點日誌

### 配置未生效
1. 檢查配置版本是否更新
2. 重啟分析節點以重新加載配置

## 未來擴展

### GUI 管理界面（待實現）
- 配置管理界面
- 路由規則編輯器
- 節點狀態監控
- 任務監控面板

### 進階功能
- 任務優先級隊列
- 動態擴縮容
- 任務結果緩存
- 分析結果通知

## 注意事項

1. **配置更新**: 配置變更後需要等待隊列清空才會生效，或手動重啟節點
2. **多實例支援**: 目前多 MongoDB 實例連接功能預留，需要進一步實現
3. **模型文件**: 模型文件上傳到 GridFS，但分析節點需要從 GridFS 下載到本地
4. **任務超時**: RabbitMQ 消息 TTL 設置為 24 小時
5. **心跳間隔**: 心跳每 30 秒發送一次，超過 60 秒無心跳則標記為離線

## 版本歷史

- **V2.0** (2025-11-10)
  - 完全重構為 RabbitMQ 架構
  - 添加狀態管理系統
  - 支援多 MongoDB 實例
  - 添加心跳機制
  - 動態配置管理

- **V1.1** (之前)
  - 基於 MongoDB Watcher
  - 單一 MongoDB 實例
  - 靜態配置
