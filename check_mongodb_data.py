#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MongoDB 資料結構檢查腳本
用於診斷 dashboard 載入問題
"""

from pymongo import MongoClient
import json
from datetime import datetime

# MongoDB 連接配置
MONGODB_CONFIG = {
    'host': 'localhost',
    'port': 27020,
    'username': 'web_ui',
    'password': 'hod2iddfsgsrl',
    'database': 'web_db',
    'collection': 'recordings'
}


def check_mongodb_data():
    """檢查 MongoDB 中的資料結構"""
    try:
        # 建立連接
        connection_string = (
            f"mongodb://{MONGODB_CONFIG['username']}:{MONGODB_CONFIG['password']}"
            f"@{MONGODB_CONFIG['host']}:{MONGODB_CONFIG['port']}/admin"
        )
        client = MongoClient(connection_string)
        db = client[MONGODB_CONFIG['database']]
        collection = db[MONGODB_CONFIG['collection']]

        # 測試連接
        client.admin.command('ping')
        print("✓ MongoDB 連接成功\n")

        # 統計資料
        count = collection.count_documents({})
        print(f"總記錄數: {count}\n")

        if count == 0:
            print("⚠ 資料庫中沒有記錄")
            return

        # 獲取第一筆記錄
        first_doc = collection.find_one()

        print("=" * 80)
        print("第一筆記錄結構:")
        print("=" * 80)
        print(json.dumps(first_doc, indent=2, default=str))
        print("\n")

        # 檢查關鍵欄位
        print("=" * 80)
        print("關鍵欄位檢查:")
        print("=" * 80)

        checks = {
            'AnalyzeUUID': first_doc.get('AnalyzeUUID'),
            'files.raw.filename': first_doc.get('files', {}).get('raw', {}).get('filename'),
            'info_features.duration': first_doc.get('info_features', {}).get('duration'),
            'info_features.device_id': first_doc.get('info_features', {}).get('device_id'),
            'info_features.equ_UUID': first_doc.get('info_features', {}).get('equ_UUID'),
            'info_features.upload_time': first_doc.get('info_features', {}).get('upload_time'),
            'info_features.file_hash': first_doc.get('info_features', {}).get('file_hash'),
            'info_features.file_size': first_doc.get('info_features', {}).get('file_size'),
            'files.raw.size_mb': first_doc.get('files', {}).get('raw', {}).get('size_mb'),
            'created_at': first_doc.get('created_at'),
        }

        for key, value in checks.items():
            status = "✓" if value is not None else "✗"
            print(f"{status} {key:40s} = {value}")

        print("\n")

        # 檢查所有記錄的一致性
        print("=" * 80)
        print("檢查所有記錄:")
        print("=" * 80)

        all_docs = list(collection.find().limit(10))

        for idx, doc in enumerate(all_docs, 1):
            info = doc.get('info_features', {})
            files = doc.get('files', {}).get('raw', {})

            print(f"\n記錄 {idx}:")
            print(f"  AnalyzeUUID: {doc.get('AnalyzeUUID', 'MISSING')}")
            print(f"  filename: {files.get('filename', 'MISSING')}")
            print(f"  duration: {info.get('duration', 'MISSING')}")
            print(f"  device_id: {info.get('device_id', 'N/A')}")
            print(f"  equ_UUID: {info.get('equ_UUID', 'N/A')}")
            print(f"  upload_time: {info.get('upload_time', 'MISSING')}")

            # 檢查是否有 web_ui_metadata
            if 'web_ui_metadata' in info:
                print(f"  web_ui_metadata: {info['web_ui_metadata']}")
            else:
                print(f"  web_ui_metadata: 無")

        print("\n")
        print("=" * 80)
        print("資料結構分析完成")
        print("=" * 80)

        client.close()

    except Exception as e:
        print(f"✗ 錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    check_mongodb_data()