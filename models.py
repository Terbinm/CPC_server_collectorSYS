from main import db
from config import Config
from datetime import datetime


class AudioRecording(db.Model):
    """
    聲音數據庫 model
    """
    id = db.Column(db.Integer, primary_key=True)  # 編號
    filename = db.Column(db.String(100), nullable=False)  # 檔案名稱
    duration = db.Column(db.Float, nullable=False)  # 錄製時長
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(Config.TAIPEI_TZ))  # 上傳完成的時間
    device_id = db.Column(db.String(36), nullable=False)  # 錄製使用的設備
    upload_complete = db.Column(db.Boolean, default=False)  # 上傳完整性標記
    file_size = db.Column(db.Integer, nullable=False)  # 文件大小
    file_hash = db.Column(db.String(64), nullable=False)  # 文件哈希值

    def __repr__(self):
        return f'<AudioRecording {self.filename}>'

    def to_dict(self):
        """
        將 model 轉換為 dict
        """
        return {
            'id': self.id,
            'filename': self.filename,
            'duration': self.duration,
            'timestamp': self.timestamp.isoformat(),
            'device_id': self.device_id,
            'upload_complete': self.upload_complete,
            'file_size': self.file_size,
            'file_hash': self.file_hash
        }
