# Flask 前端 Dockerfile
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements (如果有的話,先複製以利用快取)
COPY requirements.txt* ./

# 安裝 Python 依賴
RUN pip install --no-cache-dir flask flask-socketio flask-sqlalchemy pymongo python-socketio soundfile pydub librosa python-engineio werkzeug pytz gridfs || \
    pip install --no-cache-dir flask flask-socketio flask-sqlalchemy pymongo soundfile librosa pytz

# 複製應用程式檔案
COPY config.py .
COPY main.py .
COPY models.py .
COPY routes.py .
COPY socket_events.py .
COPY shared_state.py .
COPY utils.py .
COPY gridfs_handler.py .

# 複製靜態檔案和模板(如果有)
COPY static/ ./static/
COPY templates/ ./templates/

# 建立上傳目錄
RUN mkdir -p /app/uploads

# 暴露埠
EXPOSE 5000

# 設定環境變數
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# 啟動應用
CMD ["python", "main.py"]