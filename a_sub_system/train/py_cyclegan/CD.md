# 聲音分析系統開發文件

## 系統架構

這是一個基於 Flask 的 RESTful API 服務，用於處理音訊檔案分析任務。系統使用 MongoDB 儲存資料，RabbitMQ 處理非同步任務。

### 部署新版本：
```shell
.\scripts\build.ps1 1.0.6
```

### 更新版本： (允許傳遞版本，不船則是使用 latest，搭配 watchtower實現自動更新)
```shell
.\scripts\deploy.ps1 1.0.6
```

### 部署至集群 - 更新

```shell
.\scripts\docker_sound_analysis_cluster_deploy.ps1 1.0.6
```

### 部署至集群 - 刪除
```shell
.\scripts\docker_sound_analysis_cluster_delete.ps1
```


# 檢查部署所有設定
1. dockerfile記得修改版本！
2. 設定所有 `/scripts` 腳本以下配置 
   * 除了 `$DOCKER_REGISTRY` 其他基本要改
    ```powershell
    $DOCKER_REGISTRY="terbinm"
    $IMAGE_NAME="sound_analysis-pcr-step4"
    $CONTAINER_NAME="sound_analysis-pcr-step4"
    $CONTAINER_PORT=57124
    $HOST_PORT=57124
    ```
3. 檢查`R`/`Python`安裝包的設定是否正確
    * `install_r_packages.R` R 自動安裝與檢查程式
    * `requirements.txt` Python 環境依賴檢查器(不包括Rpy2)
4. 檢查 `config.py` 設定是否正確
5. 檢查 `dockerfile` 設定是否正確
    * `install_r_packages.R` R 自動安裝與檢查程式
    ```dockerfile
    # 設定環境變數
    ENV FLASK_APP=???.py
    ENV PYTHONPATH=/app
    ENV SERVER_NAME=???
    ENV SERVER_VISION=1.0.0
    
    # 暴露服務端口
    EXPOSE ???
    
    # 健康檢查
    HEALTHCHECK --interval=30s --timeout=3s \
        CMD curl -f http://localhost:???/health || exit 1
    
    
    CMD ["python3", "???.py"]
    ```
6. 檢查 `CD.md` 所有快捷命令是否有填上正確的版本號！ 
7. 檢查port是否都有修改到 