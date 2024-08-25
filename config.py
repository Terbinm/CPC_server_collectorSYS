import pytz


class Config:
    """
    Application配置類
    """
    SECRET_KEY = 'your_secret_key'  # 設定密鑰
    SQLALCHEMY_DATABASE_URI = 'sqlite:///audio_recordings.db'  # 設定數據庫URI
    UPLOAD_FOLDER = 'uploads'  # 設定上傳文件的存儲目錄
    TAIPEI_TZ = pytz.timezone('Asia/Taipei')  # 設定時區為台北時區
