from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import logging
from config import Config
import os
from models import MongoDBHandler

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化 Flask 應用
app = Flask(__name__)
app.config.from_object(Config)


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


# 初始化 SQLAlchemy（僅用於排程資料）
db = SQLAlchemy(app)

# 初始化 MongoDB（用於錄音資料）
mongodb_handler = None

try:
    mongodb_handler = MongoDBHandler()
    logger.info("MongoDB 初始化成功")
except Exception as e:
    logger.error(f"MongoDB 初始化失敗: {e}")
    raise

# 初始化 SocketIO，允許所有來源的跨域請求，並啟用日誌
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# 導入路由和事件處理器
from routes import *
from socket_events import *


# 初始化數據庫
def init_db():
    """
    初始化數據庫
    - SQLite: 用於排程資料（如果需要）
    - MongoDB: 用於錄音資料（已在上方初始化）
    """
    with app.app_context():
        # SQLite 表格（如果排程需要持久化）
        # db.create_all()
        pass
    logger.info("資料庫初始化完成")


# 清理資源
def cleanup():
    """清理資源"""
    global mongodb_handler
    if mongodb_handler:
        mongodb_handler.close()
        logger.info("MongoDB 連接已關閉")


# 主程序入口點
if __name__ == '__main__':
    # 初始化數據庫
    init_db()

    # 確保上傳文件夾存在
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        logger.info(f"創建上傳文件夾: {app.config['UPLOAD_FOLDER']}")

    try:
        logger.info("啟動應用程序")
        socketio.run(app,
                     host='0.0.0.0',
                     port=5000,
                     debug=True,
                     allow_unsafe_werkzeug=True)
    finally:
        cleanup()