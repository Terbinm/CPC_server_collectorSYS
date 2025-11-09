"""
MongoDB 和 GridFS 操作模組
提供資料庫連接和檔案上傳功能
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, Optional

from bson.objectid import ObjectId
from gridfs import GridFS
from pymongo import MongoClient

from .utils import build_analysis_container


class MongoDBUploader:
    """封裝 MongoDB 與 GridFS 操作的類別"""

    def __init__(
        self,
        mongodb_config: Dict[str, Any],
        use_gridfs: bool,
        logger: logging.Logger
    ) -> None:
        """
        初始化 MongoDB 上傳器

        Args:
            mongodb_config: MongoDB 配置字典，包含 host, port, username, password, database, collection
            use_gridfs: 是否使用 GridFS 儲存檔案
            logger: 日誌記錄器
        """
        self.config = mongodb_config
        self.use_gridfs = use_gridfs
        self.logger = logger
        self.mongo_client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        self.fs: Optional[GridFS] = None
        self._connect()

    def _connect(self) -> None:
        """建立 MongoDB 連接"""
        try:
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
            self.db = self.mongo_client[self.config['database']]
            self.collection = self.db[self.config['collection']]

            if self.use_gridfs:
                self.fs = GridFS(self.db)

            self.mongo_client.admin.command("ping")
            self.logger.info("成功連線至 MongoDB。")
        except Exception as exc:
            self.logger.error("無法連線至 MongoDB：%s", exc)
            raise

    def file_exists(self, file_hash: str, check_duplicates: bool = True) -> bool:
        """
        檢查檔案是否已存在

        Args:
            file_hash: 檔案雜湊值
            check_duplicates: 是否檢查重複

        Returns:
            檔案是否存在
        """
        if not check_duplicates:
            return False
        existing = self.collection.find_one({'info_features.file_hash': file_hash})
        return existing is not None

    def upload_file(
        self,
        file_path: Path,
        label: str,
        file_hash: str,
        info_features: Dict[str, Any],
        gridfs_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        上傳檔案到 MongoDB/GridFS

        Args:
            file_path: 檔案路徑
            label: 標籤
            file_hash: 檔案雜湊值
            info_features: 資訊特徵字典
            gridfs_metadata: GridFS 元數據（可選）

        Returns:
            AnalyzeUUID，如果失敗則為 None
        """
        analyze_uuid = str(uuid.uuid4())

        try:
            with open(file_path, 'rb') as handle:
                file_data = handle.read()

            file_id = None
            if self.fs:
                metadata = gridfs_metadata or {
                    'file_hash': file_hash,
                    'label': label,
                }
                file_id = self.fs.put(
                    file_data,
                    filename=file_path.name,
                    metadata=metadata,
                )
                self.logger.debug("檔案已寫入 GridFS：%s", file_id)

            document = self._create_document(
                analyze_uuid=analyze_uuid,
                filename=file_path.name,
                file_id=file_id,
                info_features=info_features,
            )

            self.collection.insert_one(document)
            self.logger.debug("已新增 MongoDB 文件：%s", analyze_uuid)
            return analyze_uuid

        except Exception as exc:
            self.logger.error("上傳檔案 %s 時發生錯誤：%s", file_path.name, exc)
            return None

    def _create_document(
        self,
        analyze_uuid: str,
        filename: str,
        file_id: Optional[ObjectId],
        info_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        建立 MongoDB 文檔

        Args:
            analyze_uuid: 分析 UUID
            filename: 檔案名稱
            file_id: GridFS 檔案 ID
            info_features: 資訊特徵字典

        Returns:
            MongoDB 文檔
        """
        current_time = datetime.now(UTC)
        file_type = Path(filename).suffix.lstrip('.').lower()

        document = {
            "AnalyzeUUID": analyze_uuid,
            "current_step": 0,
            "created_at": current_time,
            "updated_at": current_time,
            "files": {
                "raw": {
                    "fileId": file_id,
                    "filename": filename,
                    "type": file_type,
                }
            },
            "analyze_features": build_analysis_container(),
            "info_features": info_features,
        }

        return document

    def close(self) -> None:
        """關閉 MongoDB 連接"""
        if self.mongo_client:
            self.mongo_client.close()
            self.logger.info("已關閉 MongoDB 連線。")
