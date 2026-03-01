"""
日志配置模块
============

统一的日志配置，支持控制台和文件输出。
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str | None = None,
    level: int = logging.INFO,
    log_file: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    配置日志器
    
    Args:
        name: 日志器名称，None则返回根日志器
        level: 日志级别
        log_file: 日志文件路径，None则不写入文件
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件数量
        
    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    
    formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


ROOT_LOGGER = setup_logger(
    name='maplanavi',
    level=logging.INFO,
    log_file='logs/maplanavi.log'
)

__all__ = ['setup_logger', 'get_logger', 'ROOT_LOGGER']
