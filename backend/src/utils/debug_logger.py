#!/usr/bin/env python3
"""
Debug Logger for TITAN POS
Structured logging with colors and levels
"""

from typing import Optional
from datetime import datetime
import json
import logging
from pathlib import Path
import sys


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)

class DebugLogger:
    """Enhanced debug logger for development."""
    
    def __init__(self, name="TITAN_POS", level=logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers = []
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (no colors)
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_dir / f"debug_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def debug(self, msg, **kwargs):
        """Debug message."""
        self.logger.debug(self._format_msg(msg, kwargs))
    
    def info(self, msg, **kwargs):
        """Info message."""
        self.logger.info(self._format_msg(msg, kwargs))
    
    def warning(self, msg, **kwargs):
        """Warning message."""
        self.logger.warning(self._format_msg(msg, kwargs))
    
    def error(self, msg, **kwargs):
        """Error message."""
        self.logger.error(self._format_msg(msg, kwargs))
    
    def critical(self, msg, **kwargs):
        """Critical message."""
        self.logger.critical(self._format_msg(msg, kwargs))
    
    def sql(self, query, params=None, duration=None):
        """Log SQL query."""
        msg = f"SQL: {query[:100]}..."
        if params:
            msg += f" | Params: {params}"
        if duration:
            msg += f" | {duration:.2f}ms"
        self.debug(msg)
    
    def api_request(self, method, url, status_code=None, duration=None):
        """Log API request."""
        msg = f"API {method} {url}"
        if status_code:
            msg += f" → {status_code}"
        if duration:
            msg += f" ({duration:.0f}ms)"
        self.info(msg)
    
    def exception(self, exc):
        """Log exception."""
        self.logger.exception(f"Exception: {exc}")
    
    def _format_msg(self, msg, kwargs):
        """Format message with extra data."""
        if kwargs:
            return f"{msg} | {json.dumps(kwargs)}"
        return msg

# Global logger instance
logger = DebugLogger()

if __name__ == '__main__':
    # Test logging
    logger.debug("This is a debug message", user_id=123)
    logger.info("Application started successfully", version="2.0.0")
    logger.warning("Low stock alert", product="Laptop", stock=2)
    logger.error("Failed to process payment", order_id=456)
    logger.sql("SELECT * FROM products WHERE id = %s", params=(1,), duration=45.2)
    logger.api_request("POST", "/api/orders", status_code=201, duration=234)
    
    try:
        1 / 0
    except Exception as e:
        logger.exception(e)
