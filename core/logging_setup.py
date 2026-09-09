import logging
import csv
import os
from datetime import datetime
from pathlib import Path
from config.settings import LOG_DIRECTORY, LOG_LEVEL, LOG_ROTATION_SIZE, KEEP_LOGS_DAYS

# Create log directory if it doesn't exist
LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Configure logging
log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

logging.basicConfig(
    level=log_levels.get(LOG_LEVEL.value, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIRECTORY / 'trading_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Clean old logs
def clean_old_logs():
    """Remove log files older than KEEP_LOGS_DAYS"""
    cutoff_date = datetime.now().timestamp() - (KEEP_LOGS_DAYS * 24 * 60 * 60)
    
    for log_file in LOG_DIRECTORY.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_date:
            try:
                log_file.unlink()
                logger.info(f"Removed old log file: {log_file}")
            except:
                pass

# Initialize log cleaning
clean_old_logs()

def log_csv(filename: str, data: dict):
    """Log data to CSV file"""
    try:
        filepath = LOG_DIRECTORY / filename
        
        # Create file with headers if it doesn't exist
        if not filepath.exists():
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                writer.writeheader()
        
        # Append data
        with open(filepath, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writerow(data)
            
    except Exception as e:
        logger.error(f"Failed to log to CSV {filename}: {str(e)}")

def log_info(message: str):
    """Log info message"""
    logger.info(message)

def log_warning(message: str):
    """Log warning message"""
    logger.warning(message)

def log_error(message: str):
    """Log error message"""
    logger.error(message)

def log_debug(message: str):
    """Log debug message"""
    logger.debug(message)

def log_critical(message: str):
    """Log critical message"""
    logger.critical(message)

def log_trade(trade_data: dict):
    """Log trade with structured format"""
    log_info(f"TRADE: {trade_data}")
    log_csv("trades_detailed.csv", trade_data)

def log_signal(signal_data: dict):
    """Log trading signal"""
    log_debug(f"SIGNAL: {signal_data}")
    log_csv("signals_detailed.csv", signal_data)

def log_performance(metrics: dict):
    """Log performance metrics"""
    log_info(f"PERFORMANCE: {metrics}")
    log_csv("performance_metrics.csv", metrics)

def rotate_logs():
    """Rotate log files if they get too large"""
    for log_file in LOG_DIRECTORY.glob("*.log"):
        if log_file.stat().st_size > LOG_ROTATION_SIZE:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = log_file.with_suffix(f".{timestamp}.log")
            try:
                log_file.rename(new_name)
                logger.info(f"Rotated log file: {log_file} -> {new_name}")
            except:
                logger.error(f"Failed to rotate log file: {log_file}")

# Initialize
rotate_logs()