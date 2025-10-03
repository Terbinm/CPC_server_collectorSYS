# gridfs_handler.py - GridFS 文件操作工具

from gridfs import GridFS, GridFSBucket
from pymongo import MongoClient
from bson.objectid import ObjectId
from config import Config
import logging
from typing import Optional, BinaryIO, Dict, Any
import io

logger = logging.getLogger(__name__)


class GridFSHandler:
    """GridFS 文件操作處理器"""

    def __init__(self, mongo_client: MongoClient = None):
        """
        初始化 GridFS 處理器

        Args:
            mongo_client: MongoDB 客戶端實例，如果為 None 則自動創建
        """
        if mongo_client is None:
            self.config = Config.MONGODB_CONFIG
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
        else:
            self.mongo_client = mongo_client
            self.config = Config.MONGODB_CONFIG

        self.db = self.mongo_client[self.config['database']]
        self.fs = GridFS(self.db)
        self.fs_bucket = GridFSBucket(self.db)

        logger.info("GridFS Handler 初始化成功")

    def upload_file(self, file_data: bytes, filename: str,
                    content_type: str = 'audio/wav',
                    metadata: Dict[str, Any] = None) -> ObjectId:
        """
        上傳文件到 GridFS

        Args:
            file_data: 文件二進制數據
            filename: 文件名稱
            content_type: 文件類型
            metadata: 附加元數據

        Returns:
            文件的 ObjectId
        """
        try:
            file_metadata = metadata or {}
            file_metadata['contentType'] = content_type

            file_id = self.fs.put(
                file_data,
                filename=filename,
                metadata=file_metadata
            )

            logger.info(f"文件上傳成功: {filename} (ID: {file_id})")
            return file_id

        except Exception as e:
            logger.error(f"文件上傳失敗 {filename}: {e}")
            raise

    def upload_file_stream(self, file_stream: BinaryIO, filename: str,
                           content_type: str = 'audio/wav',
                           metadata: Dict[str, Any] = None) -> ObjectId:
        """
        使用流式上傳文件到 GridFS（適合大文件）

        Args:
            file_stream: 文件流對象
            filename: 文件名稱
            content_type: 文件類型
            metadata: 附加元數據

        Returns:
            文件的 ObjectId
        """
        try:
            file_metadata = metadata or {}
            file_metadata['contentType'] = content_type

            file_id = self.fs_bucket.upload_from_stream(
                filename,
                file_stream,
                metadata=file_metadata
            )

            logger.info(f"文件流上傳成功: {filename} (ID: {file_id})")
            return file_id

        except Exception as e:
            logger.error(f"文件流上傳失敗 {filename}: {e}")
            raise

    def download_file(self, file_id: ObjectId) -> Optional[bytes]:
        """
        從 GridFS 下載文件

        Args:
            file_id: 文件 ObjectId

        Returns:
            文件二進制數據或 None
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            grid_out = self.fs.get(file_id)
            file_data = grid_out.read()

            logger.debug(f"文件下載成功 (ID: {file_id})")
            return file_data

        except Exception as e:
            logger.error(f"文件下載失敗 (ID: {file_id}): {e}")
            return None

    def download_file_stream(self, file_id: ObjectId) -> Optional[io.BytesIO]:
        """
        從 GridFS 下載文件流

        Args:
            file_id: 文件 ObjectId

        Returns:
            BytesIO 對象或 None
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            file_data = self.download_file(file_id)
            if file_data:
                return io.BytesIO(file_data)
            return None

        except Exception as e:
            logger.error(f"文件流下載失敗 (ID: {file_id}): {e}")
            return None

    def download_to_stream(self, file_id: ObjectId, output_stream: BinaryIO) -> bool:
        """
        將 GridFS 文件下載到指定流

        Args:
            file_id: 文件 ObjectId
            output_stream: 輸出流

        Returns:
            是否成功
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            self.fs_bucket.download_to_stream(file_id, output_stream)
            logger.debug(f"文件下載到流成功 (ID: {file_id})")
            return True

        except Exception as e:
            logger.error(f"文件下載到流失敗 (ID: {file_id}): {e}")
            return False

    def delete_file(self, file_id: ObjectId) -> bool:
        """
        從 GridFS 刪除文件

        Args:
            file_id: 文件 ObjectId

        Returns:
            是否刪除成功
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            self.fs.delete(file_id)
            logger.info(f"文件刪除成功 (ID: {file_id})")
            return True

        except Exception as e:
            logger.error(f"文件刪除失敗 (ID: {file_id}): {e}")
            return False

    def file_exists(self, file_id: ObjectId) -> bool:
        """
        檢查文件是否存在

        Args:
            file_id: 文件 ObjectId

        Returns:
            文件是否存在
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            return self.fs.exists(file_id)

        except Exception as e:
            logger.error(f"檢查文件存在失敗 (ID: {file_id}): {e}")
            return False

    def get_file_info(self, file_id: ObjectId) -> Optional[Dict[str, Any]]:
        """
        獲取文件信息

        Args:
            file_id: 文件 ObjectId

        Returns:
            文件信息字典或 None
        """
        try:
            if isinstance(file_id, str):
                file_id = ObjectId(file_id)

            grid_out = self.fs.get(file_id)

            info = {
                'file_id': str(grid_out._id),
                'filename': grid_out.filename,
                'length': grid_out.length,
                'upload_date': grid_out.upload_date,
                'md5': grid_out.md5,
                'metadata': grid_out.metadata
            }

            return info

        except Exception as e:
            logger.error(f"獲取文件信息失敗 (ID: {file_id}): {e}")
            return None

    def list_files(self, limit: int = 100) -> list:
        """
        列出 GridFS 中的文件

        Args:
            limit: 最大返回數量

        Returns:
            文件信息列表
        """
        try:
            files = []
            for grid_out in self.fs.find().limit(limit):
                files.append({
                    'file_id': str(grid_out._id),
                    'filename': grid_out.filename,
                    'length': grid_out.length,
                    'upload_date': grid_out.upload_date
                })
            return files

        except Exception as e:
            logger.error(f"列出文件失敗: {e}")
            return []

    def get_file_by_filename(self, filename: str) -> Optional[ObjectId]:
        """
        根據文件名獲取文件 ID

        Args:
            filename: 文件名稱

        Returns:
            文件 ObjectId 或 None
        """
        try:
            grid_out = self.fs.find_one({"filename": filename})
            if grid_out:
                return grid_out._id
            return None

        except Exception as e:
            logger.error(f"根據文件名獲取文件失敗 {filename}: {e}")
            return None

    def close(self):
        """關閉連接"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("GridFS Handler 連接已關閉")