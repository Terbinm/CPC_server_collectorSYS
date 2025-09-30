from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import logging
from config import Config
import os

# 設置日誌
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化 Flask 應用
app = Flask(__name__)
app.config.from_object(Config)


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


# 初始化數據庫
db = SQLAlchemy(app)

# 初始化 SocketIO，允許所有來源的跨域請求，並啟用日誌
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# 導入路由和事件處理器
from routes import *
from socket_events import *


# 初始化數據庫
def init_db():
    """
    初始化數據庫，創建所有表格
    """
    with app.app_context():
        db.create_all()
    logger.info("數據庫初始化完成")


# 主程序入口點
if __name__ == '__main__':
    # 初始化數據庫
    init_db()

    # 確保上傳文件夾存在
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        logger.info(f"創建上傳文件夾: {app.config['UPLOAD_FOLDER']}")

    logger.info("啟動應用程序")
    socketio.run(app,
                 host='0.0.0.0',
                 port=5000,
                 debug=True,
                 allow_unsafe_werkzeug=True)
