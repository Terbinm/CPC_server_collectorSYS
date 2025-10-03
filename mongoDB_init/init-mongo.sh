#!/bin/bash

# MongoDB 初始化腳本
# 用途：創建資料庫、使用者和必要的權限

set -e

echo "========================================="
echo "開始初始化 MongoDB"
echo "========================================="

# 等待 MongoDB 服務完全啟動
sleep 5

# 使用 mongosh 連接並執行初始化
mongosh --host localhost --port 27017 <<EOF

// 切換到 admin 資料庫
use admin

// 創建 root 管理員（如果不存在）
db.createUser({
  user: "admin",
  pwd: "admin_password_here",
  roles: [
    { role: "root", db: "admin" }
  ]
})

// 切換到 web_db 資料庫
use web_db

// 創建 web_ui 使用者（用於前端和分析服務）
db.createUser({
  user: "web_ui",
  pwd: "hod2iddfsgsrl",
  roles: [
    { role: "readWrite", db: "web_db" },
    { role: "dbAdmin", db: "web_db" }
  ]
})

// 創建必要的集合
db.createCollection("recordings")

// 創建索引
db.recordings.createIndex({ "AnalyzeUUID": 1 }, { unique: true })
db.recordings.createIndex({ "info_features.device_id": 1 })
db.recordings.createIndex({ "info_features.upload_time": 1 })
db.recordings.createIndex({ "current_step": 1 })
db.recordings.createIndex({ "analysis_status": 1 })

print("========================================")
print("MongoDB 初始化完成！")
print("========================================")
print("已創建資料庫: web_db")
print("已創建使用者: web_ui")
print("已創建集合: recordings")
print("已創建必要索引")
print("========================================")

EOF

echo "MongoDB 初始化腳本執行完畢"