from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId
from config import Config
from datetime import datetime
import uuid
import logging
from gridfs_handler import GridFSHandler

logger = logging.getLogger(__name__)


class MongoDBHandler:
    """MongoDB 操作處理器"""

    def __init__(self):
        self.config = Config.MONGODB_CONFIG
        self.mongo_client = None
        self.db = None
        self.collection = None
        self.gridfs_handler = None
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

            # 初始化 GridFS Handler
            self.gridfs_handler = GridFSHandler(self.mongo_client)

            # 測試連接
            self.mongo_client.admin.command('ping')
            logger.info("MongoDB 連接成功")

            # 建立索引
            self._create_indexes()
        except Exception as e:
            logger.error(f"MongoDB 連接失敗: {e}")
            raise

    def _create_indexes(self):
        """建立資料庫索引"""
        for index_field in Config.DATABASE_INDEXES:
            try:
                self.collection.create_index([(index_field, ASCENDING)])
                logger.info(f"索引建立成功: {index_field}")
            except Exception as e:
                logger.warning(f"索引建立失敗 {index_field}: {e}")

    def close(self):
        """關閉連接"""
        if self.gridfs_handler:
            self.gridfs_handler.close()
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB 連接已關閉")


class AudioRecording:
    """音頻錄音文檔結構（使用 GridFS 儲存檔案）"""

    def __init__(self, filename, duration, device_id, file_size, file_hash,
                 file_id: ObjectId = None, upload_complete=True, metadata=None):
        self.analyze_uuid = str(uuid.uuid4())
        self.filename = filename
        self.duration = duration
        self.device_id = device_id
        self.file_size = file_size
        self.file_hash = file_hash
        self.file_id = file_id  # GridFS 文件 ID
        self.upload_complete = upload_complete
        self.metadata = metadata or {}
        self.timestamp = datetime.now(Config.TAIPEI_TZ)

    def to_mongodb_document(self):
        """轉換為 MongoDB 文檔格式（使用 GridFS）"""
        current_time = datetime.utcnow()

        # 獲取文件類型
        file_type = self.metadata.get('format', Config.AUDIO_CONFIG['default_format'])
        if file_type == 'WAV':
            file_type = 'wav'
        file_type = file_type.lower()

        document = {
            "AnalyzeUUID": self.analyze_uuid,
            "current_step": 0,
            "created_at": current_time,
            "updated_at": current_time,
            "files": {
                "raw": {
                    "fileId": self.file_id,  # GridFS ObjectId
                    "filename": self.filename,
                    "type": file_type
                }
            },
            "analyze_features": [],
            "info_features": {
                "dataset_UUID": Config.DATASET_CONFIG['dataset_UUID'],
                "device_id": self.device_id,
                "testing": False,
                "obj_ID": Config.DATASET_CONFIG['obj_ID'],
                "upload_time": self.timestamp.isoformat(),
                "upload_complete": self.upload_complete,
                "file_hash": self.file_hash,
                "file_size": self.file_size,
                "duration": self.duration,
                "web_ui_metadata": {
                    "sample_rate": self.metadata.get('sample_rate', Config.AUDIO_CONFIG['sample_rate']),
                    "channels": self.metadata.get('channels', Config.AUDIO_CONFIG['channels']),
                    "format": file_type,
                    "source": "WEB_UPLOAD" if self.device_id == "WEB_UPLOAD" else "EDGE_DEVICE"
                }
            }
        }

        return document

    @staticmethod
    def from_mongodb_document(document):
        """從 MongoDB 文檔轉換回物件"""
        try:
            info = document.get('info_features', {})
            files = document.get('files', {}).get('raw', {})
            web_meta = info.get('web_ui_metadata', {})

            # 獲取 GridFS 文件 ID
            file_id = files.get('fileId')
            if isinstance(file_id, dict) and '$oid' in file_id:
                file_id = ObjectId(file_id['$oid'])
            elif isinstance(file_id, str):
                file_id = ObjectId(file_id)

            # 獲取檔案大小
            file_size = info.get('file_size', 0)

            # 獲取設備 ID
            device_id = info.get('device_id') or info.get('equ_UUID', 'UNKNOWN')

            recording = AudioRecording(
                filename=files.get('filename', ''),
                duration=float(info.get('duration', 0)),
                device_id=device_id,
                file_size=file_size,
                file_hash=info.get('file_hash', ''),
                file_id=file_id,
                upload_complete=info.get('upload_complete', True),
                metadata=web_meta
            )

            recording.analyze_uuid = document.get('AnalyzeUUID', '')

            # 解析時間戳
            upload_time = info.get('upload_time')
            if upload_time:
                try:
                    if isinstance(upload_time, str):
                        upload_time_str = upload_time.split('+')[0].split('Z')[0]
                        recording.timestamp = datetime.fromisoformat(upload_time_str)
                        if recording.timestamp.tzinfo is None:
                            recording.timestamp = Config.TAIPEI_TZ.localize(recording.timestamp)
                    else:
                        recording.timestamp = upload_time
                except Exception as e:
                    logger.warning(f"解析時間戳失敗: {e}, 使用 created_at")
                    created_at = document.get('created_at')
                    if created_at:
                        recording.timestamp = created_at
                    else:
                        recording.timestamp = datetime.now(Config.TAIPEI_TZ)
            else:
                timestamp_field = info.get('timestamp') or document.get('created_at')
                if timestamp_field:
                    recording.timestamp = timestamp_field
                else:
                    recording.timestamp = datetime.now(Config.TAIPEI_TZ)

            return recording
        except Exception as e:
            logger.error(f"從 MongoDB 文檔轉換失敗: {e}, 文檔: {document}")
            raise

    def to_dict(self):
        """轉換為字典格式（用於 API 回應）"""
        try:
            if isinstance(self.timestamp, datetime):
                timestamp_str = self.timestamp.isoformat()
            else:
                timestamp_str = str(self.timestamp)

            return {
                'id': str(self.analyze_uuid),
                'filename': str(self.filename),
                'duration': float(self.duration),
                'timestamp': timestamp_str,
                'device_id': str(self.device_id),
                'upload_complete': bool(self.upload_complete),
                'file_size': int(self.file_size),
                'file_hash': str(self.file_hash),
                'file_id': str(self.file_id) if self.file_id else None
            }
        except Exception as e:
            logger.error(f"轉換為字典失敗: {e}")
            return {
                'id': str(self.analyze_uuid) if self.analyze_uuid else '',
                'filename': str(self.filename) if self.filename else '',
                'duration': 0.0,
                'timestamp': datetime.now(Config.TAIPEI_TZ).isoformat(),
                'device_id': str(self.device_id) if self.device_id else '',
                'upload_complete': False,
                'file_size': 0,
                'file_hash': '',
                'file_id': None
            }

    def __repr__(self):
        return f'<AudioRecording {self.filename}>'


class RecordingRepository:
    """錄音資料存取層（支援 GridFS）"""

    def __init__(self, db_handler: MongoDBHandler):
        self.db_handler = db_handler
        self.collection = db_handler.collection
        self.gridfs_handler = db_handler.gridfs_handler

    def insert(self, recording: AudioRecording):
        """新增錄音記錄"""
        try:
            document = recording.to_mongodb_document()
            result = self.collection.insert_one(document)
            logger.info(f"成功插入錄音記錄: {recording.filename}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"插入錄音記錄失敗: {e}")
            raise

    def find_all(self):
        """查詢所有錄音記錄"""
        try:
            documents = self.collection.find().sort('info_features.upload_time', -1)
            return [AudioRecording.from_mongodb_document(doc) for doc in documents]
        except Exception as e:
            logger.error(f"查詢錄音記錄失敗: {e}")
            return []

    def find_by_uuid(self, analyze_uuid):
        """根據 UUID 查詢錄音記錄"""
        try:
            document = self.collection.find_one({"AnalyzeUUID": analyze_uuid})
            if document:
                return AudioRecording.from_mongodb_document(document)
            return None
        except Exception as e:
            logger.error(f"查詢錄音記錄失敗: {e}")
            return None

    def find_by_filename(self, filename):
        """根據檔案名稱查詢錄音記錄"""
        try:
            document = self.collection.find_one({"files.raw.filename": filename})
            if document:
                return AudioRecording.from_mongodb_document(document)
            return None
        except Exception as e:
            logger.error(f"查詢錄音記錄失敗: {e}")
            return None

    def delete_by_uuid(self, analyze_uuid):
        """根據 UUID 刪除錄音記錄（包含 GridFS 文件）"""
        try:
            # 先獲取記錄以取得 file_id
            document = self.collection.find_one({"AnalyzeUUID": analyze_uuid})
            if document:
                file_id = document.get('files', {}).get('raw', {}).get('fileId')

                # 刪除 GridFS 文件
                if file_id:
                    if isinstance(file_id, dict) and '$oid' in file_id:
                        file_id = ObjectId(file_id['$oid'])
                    elif isinstance(file_id, str):
                        file_id = ObjectId(file_id)

                    self.gridfs_handler.delete_file(file_id)
                    logger.info(f"已刪除 GridFS 文件: {file_id}")

            # 刪除 MongoDB 記錄
            result = self.collection.delete_one({"AnalyzeUUID": analyze_uuid})
            if result.deleted_count > 0:
                logger.info(f"成功刪除錄音記錄: {analyze_uuid}")
                return True
            return False
        except Exception as e:
            logger.error(f"刪除錄音記錄失敗: {e}")
            return False

    def update_upload_status(self, analyze_uuid, upload_complete):
        """更新上傳狀態"""
        try:
            result = self.collection.update_one(
                {"AnalyzeUUID": analyze_uuid},
                {
                    "$set": {
                        "info_features.upload_complete": upload_complete,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新上傳狀態失敗: {e}")
            return False

    def count(self):
        """統計錄音總數"""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logger.error(f"統計錄音數量失敗: {e}")
            return 0

    def get_statistics(self):
        """獲取統計資訊"""
        try:
            stats = {
                'total': self.count(),
                'by_device': {},
                'by_source': {}
            }

            # 按設備統計
            pipeline_device = [
                {"$group": {"_id": "$info_features.device_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            device_stats = list(self.collection.aggregate(pipeline_device))
            stats['by_device'] = {stat['_id']: stat['count'] for stat in device_stats}

            # 按來源統計
            pipeline_source = [
                {"$group": {"_id": "$info_features.web_ui_metadata.source", "count": {"$sum": 1}}}
            ]
            source_stats = list(self.collection.aggregate(pipeline_source))
            stats['by_source'] = {stat['_id']: stat['count'] for stat in source_stats}

            return stats
        except Exception as e:
            logger.error(f"獲取統計資訊失敗: {e}")
            return {}