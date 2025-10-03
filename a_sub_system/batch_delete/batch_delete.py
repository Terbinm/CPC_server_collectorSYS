# batch_delete.py - 批量刪除工具

import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pymongo import MongoClient
from gridfs import GridFS
from bson.objectid import ObjectId
import json
from tqdm import tqdm

from batch_delete_config import DeleteConfig


class BatchDeleteLogger:
    """日誌管理器"""

    @staticmethod
    def setup_logger(name: str = 'batch_delete') -> logging.Logger:
        """設置日誌記錄器"""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, DeleteConfig.LOGGING_CONFIG['level']))

        if logger.handlers:
            return logger

        formatter = logging.Formatter(DeleteConfig.LOGGING_CONFIG['format'])

        # 檔案處理器
        file_handler = RotatingFileHandler(
            DeleteConfig.LOGGING_CONFIG['log_file'],
            maxBytes=DeleteConfig.LOGGING_CONFIG['max_bytes'],
            backupCount=DeleteConfig.LOGGING_CONFIG['backup_count'],
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # 控制台處理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger


logger = BatchDeleteLogger.setup_logger()


class MongoDBDeleter:
    """MongoDB + GridFS 刪除器"""

    def __init__(self):
        """初始化 MongoDB 連接"""
        self.config = DeleteConfig.MONGODB_CONFIG
        self.mongo_client = None
        self.db = None
        self.collection = None
        self.fs = None
        self._connect()

    def _connect(self):
        """建立 MongoDB 連接"""
        try:
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
            self.db = self.mongo_client[self.config['database']]
            self.collection = self.db[self.config['collection']]
            self.fs = GridFS(self.db)

            # 測試連接
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB 連接成功")

        except Exception as e:
            logger.error(f"✗ MongoDB 連接失敗: {e}")
            raise

    def build_query(self) -> Dict:
        """根據配置建立查詢條件"""
        conditions = DeleteConfig.DELETE_CONDITIONS
        query = {}

        # 標籤條件
        if conditions['label']:
            query['info_features.label'] = conditions['label']

        # Dataset UUID 條件
        if conditions['dataset_UUID']:
            query['info_features.dataset_UUID'] = conditions['dataset_UUID']

        # 批量上傳條件
        if conditions['batch_upload_only']:
            query['info_features.batch_upload_metadata'] = {'$exists': True}

        # 時間範圍條件
        if conditions['uploaded_before'] or conditions['uploaded_after']:
            time_query = {}
            if conditions['uploaded_before']:
                date_before = datetime.fromisoformat(
                    conditions['uploaded_before'].replace(' ', 'T')
                )
                time_query['$lt'] = date_before
            if conditions['uploaded_after']:
                date_after = datetime.fromisoformat(
                    conditions['uploaded_after'].replace(' ', 'T')
                )
                time_query['$gt'] = date_after

            if time_query:
                query['created_at'] = time_query

        # 設備 ID 條件
        if conditions['device_id']:
            query['info_features.device_id'] = conditions['device_id']

        # Obj ID 條件
        if conditions['obj_ID']:
            query['info_features.obj_ID'] = conditions['obj_ID']

        return query

    def count_records(self, query: Dict) -> int:
        """計算符合條件的記錄數量"""
        try:
            return self.collection.count_documents(query)
        except Exception as e:
            logger.error(f"計算記錄數量失敗: {e}")
            return 0

    def preview_records(self, query: Dict, limit: int = 10) -> List[Dict]:
        """預覽將被刪除的記錄"""
        try:
            cursor = self.collection.find(query).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"預覽記錄失敗: {e}")
            return []

    def get_statistics(self, query: Dict) -> Dict:
        """獲取統計資訊"""
        try:
            pipeline = [
                {'$match': query},
                {'$group': {
                    '_id': '$info_features.label',
                    'count': {'$sum': 1},
                    'total_size': {'$sum': '$info_features.file_size'},
                    'total_duration': {'$sum': '$info_features.duration'}
                }}
            ]

            stats = list(self.collection.aggregate(pipeline))

            result = {
                'by_label': {},
                'total_count': 0,
                'total_size': 0,
                'total_duration': 0
            }

            for stat in stats:
                label = stat['_id'] or 'unknown'
                result['by_label'][label] = {
                    'count': stat['count'],
                    'size': stat['total_size'],
                    'duration': stat['total_duration']
                }
                result['total_count'] += stat['count']
                result['total_size'] += stat['total_size']
                result['total_duration'] += stat['total_duration']

            return result

        except Exception as e:
            logger.error(f"獲取統計失敗: {e}")
            return {}

    def backup_records(self, query: Dict, backup_file: str) -> bool:
        """備份將被刪除的記錄"""
        try:
            records = list(self.collection.find(query))

            # 轉換 ObjectId 為字串
            for record in records:
                if '_id' in record:
                    record['_id'] = str(record['_id'])
                if 'files' in record and 'raw' in record['files']:
                    if 'fileId' in record['files']['raw']:
                        record['files']['raw']['fileId'] = str(record['files']['raw']['fileId'])

            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"✓ 備份完成: {backup_file} ({len(records)} 筆記錄)")
            return True

        except Exception as e:
            logger.error(f"✗ 備份失敗: {e}")
            return False

    def delete_records(self, query: Dict) -> Dict:
        """刪除記錄"""
        behavior = DeleteConfig.DELETE_BEHAVIOR
        stats = {
            'deleted_count': 0,
            'gridfs_deleted': 0,
            'failed_count': 0,
            'failed_ids': []
        }

        try:
            # 獲取所有符合條件的記錄
            records = list(self.collection.find(query))
            total = len(records)

            logger.info(f"開始刪除 {total} 筆記錄...")

            # 使用 tqdm 顯示進度
            if behavior['show_progress']:
                records_iter = tqdm(records, desc="刪除進度", unit="筆")
            else:
                records_iter = records

            for record in records_iter:
                try:
                    analyze_uuid = record.get('AnalyzeUUID', 'unknown')

                    # 軟刪除
                    if behavior['soft_delete']:
                        self.collection.update_one(
                            {'_id': record['_id']},
                            {
                                '$set': {
                                    behavior['soft_delete_field']: True,
                                    'deleted_at': datetime.utcnow()
                                }
                            }
                        )
                        stats['deleted_count'] += 1

                    # 硬刪除
                    else:
                        # 刪除 GridFS 檔案
                        if behavior['delete_gridfs_files']:
                            file_id = record.get('files', {}).get('raw', {}).get('fileId')
                            if file_id:
                                try:
                                    self.fs.delete(ObjectId(file_id))
                                    stats['gridfs_deleted'] += 1
                                except Exception as e:
                                    logger.warning(f"刪除 GridFS 檔案失敗 {file_id}: {e}")

                        # 刪除記錄
                        self.collection.delete_one({'_id': record['_id']})
                        stats['deleted_count'] += 1

                    logger.debug(f"✓ 已刪除: {analyze_uuid}")

                except Exception as e:
                    logger.error(f"✗ 刪除失敗 {record.get('AnalyzeUUID', 'unknown')}: {e}")
                    stats['failed_count'] += 1
                    stats['failed_ids'].append(str(record.get('_id', 'unknown')))

            return stats

        except Exception as e:
            logger.error(f"刪除過程發生錯誤: {e}")
            return stats

    def close(self):
        """關閉連接"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB 連接已關閉")


class BatchDeleter:
    """批量刪除管理器"""

    def __init__(self):
        """初始化批量刪除器"""
        self.deleter = MongoDBDeleter()
        logger.info("批量刪除器初始化完成")

    def preview_deletion(self):
        """預覽將被刪除的記錄"""
        logger.info("=" * 60)
        logger.info("預覽模式 - 查看將被刪除的記錄")
        logger.info("=" * 60)

        # 建立查詢
        query = self.deleter.build_query()
        logger.info(f"\n查詢條件: {json.dumps(query, indent=2, ensure_ascii=False, default=str)}")

        # 計算數量
        count = self.deleter.count_records(query)
        logger.info(f"\n符合條件的記錄數量: {count} 筆")

        if count == 0:
            logger.info("\n沒有符合條件的記錄")
            return

        # 獲取統計
        stats = self.deleter.get_statistics(query)
        if stats:
            logger.info(f"\n統計資訊:")
            logger.info(f"  總數量: {stats['total_count']} 筆")
            logger.info(f"  總大小: {stats['total_size'] / (1024 ** 2):.2f} MB")
            logger.info(f"  總時長: {stats['total_duration'] / 60:.2f} 分鐘")

            if stats['by_label']:
                logger.info(f"\n按標籤統計:")
                for label, data in stats['by_label'].items():
                    logger.info(f"  - {label}: {data['count']} 筆, "
                                f"{data['size'] / (1024 ** 2):.2f} MB, "
                                f"{data['duration'] / 60:.2f} 分鐘")

        # 顯示範例記錄
        sample_size = DeleteConfig.SAFETY_CONFIG['preview_sample_size']
        samples = self.deleter.preview_records(query, limit=sample_size)

        if samples:
            logger.info(f"\n前 {len(samples)} 筆記錄範例:")
            for i, record in enumerate(samples, 1):
                logger.info(f"\n  [{i}] AnalyzeUUID: {record.get('AnalyzeUUID', 'N/A')}")
                logger.info(f"      檔名: {record.get('files', {}).get('raw', {}).get('filename', 'N/A')}")
                logger.info(f"      標籤: {record.get('info_features', {}).get('label', 'N/A')}")
                logger.info(f"      上傳時間: {record.get('created_at', 'N/A')}")
                logger.info(f"      設備: {record.get('info_features', {}).get('device_id', 'N/A')}")

    def execute_deletion(self):
        """執行刪除操作"""
        logger.info("\n" + "=" * 60)
        logger.info("執行刪除")
        logger.info("=" * 60)

        # 建立查詢
        query = self.deleter.build_query()
        count = self.deleter.count_records(query)

        if count == 0:
            logger.info("\n沒有符合條件的記錄")
            return

        # 檢查數量上限
        max_count = DeleteConfig.SAFETY_CONFIG['max_delete_count']
        if max_count > 0 and count > max_count:
            logger.error(f"\n✗ 錯誤: 符合條件的記錄數量 ({count}) 超過上限 ({max_count})")
            logger.error("請調整刪除條件或修改配置中的 max_delete_count")
            return

        logger.info(f"\n即將刪除 {count} 筆記錄")

        # 二次確認
        if DeleteConfig.SAFETY_CONFIG['require_confirmation']:
            logger.info(f"\n⚠️  警告: 此操作{'可以' if DeleteConfig.DELETE_BEHAVIOR['soft_delete'] else '無法'}復原")
            print("\n確認要刪除這些記錄嗎? 請輸入 'DELETE' 以確認: ", end='')
            confirm = input().strip()

            if confirm != 'DELETE':
                logger.info("取消刪除")
                return

        # 備份
        backup_file = None
        if DeleteConfig.DELETE_BEHAVIOR['backup_before_delete']:
            import os
            os.makedirs(DeleteConfig.DELETE_BEHAVIOR['backup_directory'], exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(
                DeleteConfig.DELETE_BEHAVIOR['backup_directory'],
                f"backup_{timestamp}.json"
            )

            logger.info(f"\n正在備份記錄...")
            if not self.deleter.backup_records(query, backup_file):
                logger.error("備份失敗，取消刪除")
                return

        # 執行刪除
        logger.info("\n開始刪除...\n")
        stats = self.deleter.delete_records(query)

        # 顯示結果
        self._print_summary(stats, backup_file)

        # 儲存報告
        self._save_report(stats, query)

    def _print_summary(self, stats: Dict, backup_file: Optional[str] = None):
        """顯示刪除摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("刪除完成")
        logger.info("=" * 60)

        mode = "標記" if DeleteConfig.DELETE_BEHAVIOR['soft_delete'] else "刪除"

        logger.info(f"成功{mode}: {stats['deleted_count']} 筆記錄")

        if DeleteConfig.DELETE_BEHAVIOR['delete_gridfs_files'] and not DeleteConfig.DELETE_BEHAVIOR['soft_delete']:
            logger.info(f"刪除 GridFS 檔案: {stats['gridfs_deleted']} 個")

        if stats['failed_count'] > 0:
            logger.info(f"失敗: {stats['failed_count']} 筆")

            if stats['failed_ids']:
                logger.info(f"\n失敗的記錄 ID:")
                for failed_id in stats['failed_ids'][:10]:
                    logger.info(f"  - {failed_id}")
                if len(stats['failed_ids']) > 10:
                    logger.info(f"  ... 還有 {len(stats['failed_ids']) - 10} 筆")

        if backup_file:
            logger.info(f"\n備份檔案: {backup_file}")

    def _save_report(self, stats: Dict, query: Dict):
        """儲存刪除報告"""
        if not DeleteConfig.REPORT_OUTPUT['save_report']:
            return

        try:
            import os
            report_dir = DeleteConfig.REPORT_OUTPUT['report_directory']
            os.makedirs(report_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = os.path.join(
                report_dir,
                f"delete_report_{timestamp}.json"
            )

            report = {
                'timestamp': timestamp,
                'query': query,
                'statistics': stats,
                'config': {
                    'soft_delete': DeleteConfig.DELETE_BEHAVIOR['soft_delete'],
                    'delete_gridfs': DeleteConfig.DELETE_BEHAVIOR['delete_gridfs_files'],
                    'conditions': DeleteConfig.DELETE_CONDITIONS
                }
            }

            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"\n報告已儲存: {report_file}")

        except Exception as e:
            logger.error(f"儲存報告失敗: {e}")

    def cleanup(self):
        """清理資源"""
        self.deleter.close()


def main():
    """主程式"""
    print("""
╔══════════════════════════════════════════════════════════╗
║      批量刪除工具 v1.0                                     ║
║                                                          ║
║  功能:                                                    ║
║  1. 根據多種條件批量刪除記錄                               ║
║  2. 支援軟刪除（標記）或硬刪除                             ║
║  3. 自動備份被刪除的記錄                                   ║
║  4. 同步刪除 GridFS 中的檔案                              ║
║                                                          ║
║  配置檔案: batch_delete_config.py                         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 驗證配置
    from batch_delete_config import validate_delete_config
    errors, warnings = validate_delete_config()

    if errors:
        logger.error("配置錯誤:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    if warnings:
        logger.warning("配置警告:")
        for warning in warnings:
            logger.warning(f"  - {warning}")

    # 詢問模式
    print("\n選擇執行模式:")
    print("  1. 預覽模式 (只顯示將被刪除的記錄，不實際刪除)")
    print("  2. 執行刪除")
    print("\n請輸入選項 (1 或 2): ", end='')

    mode = input().strip()

    # 創建刪除器
    deleter = BatchDeleter()

    try:
        if mode == '1':
            deleter.preview_deletion()
        elif mode == '2':
            deleter.execute_deletion()
        else:
            logger.error("無效的選項")

    except KeyboardInterrupt:
        logger.info("\n\n操作被使用者中斷")
    except Exception as e:
        logger.error(f"操作過程發生錯誤: {e}")
    finally:
        deleter.cleanup()
        logger.info("\n程式結束")


if __name__ == '__main__':
    main()