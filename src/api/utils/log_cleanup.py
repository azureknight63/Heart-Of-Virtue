"""
Log cleanup utility for managing browser log files.
Automatically removes old log files based on retention policy.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LogCleanupManager:
    """Manages cleanup of old browser log files."""
    
    def __init__(self, logs_dir, retention_days=7, max_size_mb=100):
        """
        Initialize the log cleanup manager.
        
        Args:
            logs_dir: Path to the browser logs directory
            retention_days: Number of days to retain logs (default: 7)
            max_size_mb: Maximum total size of logs in MB (default: 100)
        """
        self.logs_dir = Path(logs_dir)
        self.retention_days = retention_days
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
    def cleanup_old_logs(self):
        """
        Remove log files older than the retention period.
        
        Returns:
            dict: Statistics about the cleanup operation
        """
        if not self.logs_dir.exists():
            return {
                'deleted_count': 0,
                'deleted_size': 0,
                'error': 'Logs directory does not exist'
            }
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        try:
            for log_file in self.logs_dir.glob('*.log'):
                try:
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    
                    # Delete if older than retention period
                    if file_mtime < cutoff_date:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        deleted_count += 1
                        deleted_size += file_size
                        logger.info(f"Deleted old log file: {log_file.name}")
                        
                except Exception as e:
                    error_msg = f"Error deleting {log_file.name}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    
        except Exception as e:
            error_msg = f"Error during cleanup: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        result = {
            'deleted_count': deleted_count,
            'deleted_size': deleted_size,
            'deleted_size_mb': round(deleted_size / (1024 * 1024), 2)
        }
        
        if errors:
            result['errors'] = errors
            
        return result
    
    def cleanup_by_size(self):
        """
        Remove oldest log files if total size exceeds maximum.
        
        Returns:
            dict: Statistics about the cleanup operation
        """
        if not self.logs_dir.exists():
            return {
                'deleted_count': 0,
                'deleted_size': 0,
                'error': 'Logs directory does not exist'
            }
        
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        try:
            # Get all log files with their sizes and modification times
            log_files = []
            total_size = 0
            
            for log_file in self.logs_dir.glob('*.log'):
                try:
                    stat = log_file.stat()
                    log_files.append({
                        'path': log_file,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
                    total_size += stat.st_size
                except Exception as e:
                    logger.error(f"Error reading {log_file.name}: {str(e)}")
            
            # If total size exceeds maximum, delete oldest files
            if total_size > self.max_size_bytes:
                # Sort by modification time (oldest first)
                log_files.sort(key=lambda x: x['mtime'])
                
                # Delete oldest files until we're under the limit
                for log_info in log_files:
                    if total_size <= self.max_size_bytes:
                        break
                    
                    try:
                        log_info['path'].unlink()
                        deleted_count += 1
                        deleted_size += log_info['size']
                        total_size -= log_info['size']
                        logger.info(f"Deleted log file for size limit: {log_info['path'].name}")
                    except Exception as e:
                        error_msg = f"Error deleting {log_info['path'].name}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        
        except Exception as e:
            error_msg = f"Error during size-based cleanup: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        result = {
            'deleted_count': deleted_count,
            'deleted_size': deleted_size,
            'deleted_size_mb': round(deleted_size / (1024 * 1024), 2)
        }
        
        if errors:
            result['errors'] = errors
            
        return result
    
    def cleanup(self):
        """
        Perform both age-based and size-based cleanup.
        
        Returns:
            dict: Combined statistics from both cleanup operations
        """
        age_result = self.cleanup_old_logs()
        size_result = self.cleanup_by_size()
        
        return {
            'age_cleanup': age_result,
            'size_cleanup': size_result,
            'total_deleted_count': age_result['deleted_count'] + size_result['deleted_count'],
            'total_deleted_size_mb': age_result.get('deleted_size_mb', 0) + size_result.get('deleted_size_mb', 0)
        }
    
    def get_stats(self):
        """
        Get statistics about current log files.
        
        Returns:
            dict: Statistics about log files
        """
        if not self.logs_dir.exists():
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None
            }
        
        log_files = list(self.logs_dir.glob('*.log'))
        
        if not log_files:
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0,
                'oldest_file': None,
                'newest_file': None
            }
        
        total_size = sum(f.stat().st_size for f in log_files)
        
        # Find oldest and newest files
        files_with_time = [(f, f.stat().st_mtime) for f in log_files]
        oldest = min(files_with_time, key=lambda x: x[1])
        newest = max(files_with_time, key=lambda x: x[1])
        
        return {
            'total_files': len(log_files),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'oldest_file': {
                'name': oldest[0].name,
                'date': datetime.fromtimestamp(oldest[1]).isoformat()
            },
            'newest_file': {
                'name': newest[0].name,
                'date': datetime.fromtimestamp(newest[1]).isoformat()
            }
        }
