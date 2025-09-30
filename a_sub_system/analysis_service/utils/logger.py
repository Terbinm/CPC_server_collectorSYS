# utils/logger.py - 日誌管理工具

import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOGGING_CONFIG


def setup_logger(name: str = 'analysis_service') -> logging.Logger:
    """
    設置日誌記錄器
    
    Args:
        name: 日誌記錄器名稱
        
    Returns:
        配置好的日誌記錄器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOGGING_CONFIG['level']))
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 格式化器
    formatter = logging.Formatter(LOGGING_CONFIG['format'])
    
    # 檔案處理器（使用 RotatingFileHandler）
    file_handler = RotatingFileHandler(
        LOGGING_CONFIG['log_file'],
        maxBytes=LOGGING_CONFIG['max_bytes'],
        backupCount=LOGGING_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 添加處理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# 建立全域 logger
logger = setup_logger()