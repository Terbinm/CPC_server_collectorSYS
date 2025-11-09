# 使用 Ubuntu 22.04 作為基礎映像
FROM ubuntu:22.04

# 設定環境變數避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 設定時區為台北時間
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    # 基礎開發工具
    python3.10 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    build-essential \
    cmake \
    cmake-data \
    gfortran \
    # R 相關
    r-base \
    r-base-dev \
    # 音訊處理
    libfftw3-dev \
    libsndfile1-dev \
    libjack-jackd2-dev \
    portaudio19-dev \
    # 圖像和繪圖
    libcairo2-dev \
    libpango1.0-dev \
    librsvg2-dev \
    libtiff5-dev \
    libharfbuzz-dev \
    # 數值計算
    libblas-dev \
    liblapack-dev \
    # 網路和加密
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    # 地理資訊
    libudunits2-dev \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    # X11 相關
    libxt-dev \
    # 其他工具
    ca-certificates \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# 更新pip工具並安裝基礎Python工具
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# 配置R環境
ENV R_LIBS_USER=/usr/local/lib/R/site-library
COPY install_r_packages.R /tmp/
RUN mkdir -p /usr/local/lib/R/site-library && \
    chmod -R 777 /usr/local/lib/R/site-library && \
    Rscript /tmp/install_r_packages.R

# 安裝Python套件
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && \
    pip3 install --no-cache-dir rpy2==3.5.14

# 建立應用目錄
WORKDIR /app

# 複製應用程式檔案
COPY . .

# 設定環境變數
ENV FLASK_APP=customer_R_slice_Extract_Features.py
ENV PYTHONPATH=/app
ENV SERVER_NAME=customer_R_slice_Extract_Features
ENV SERVER_VISION=1.0.0
ENV FLASK_PORT=57122

# 暴露服務端口
EXPOSE ${FLASK_PORT}

# 健康檢查
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:${FLASK_PORT}/health || exit 1


CMD ["python3", "customer_R_slice_Extract_Features.py"]