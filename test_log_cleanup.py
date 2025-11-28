"""
Test script for browser log cleanup functionality.
Run this to verify the cleanup system is working correctly.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent

# Import directly from the module file to avoid Flask dependencies
import importlib.util
spec = importlib.util.spec_from_file_location(
    "log_cleanup",
    project_root / "src" / "api" / "utils" / "log_cleanup.py"
)
log_cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log_cleanup)
LogCleanupManager = log_cleanup.LogCleanupManager
from datetime import datetime, timedelta
import os

def test_cleanup():
    """Test the log cleanup functionality."""
    
    logs_dir = project_root / 'logs' / 'browser'
    
    print("=" * 60)
    print("Browser Log Cleanup Test")
    print("=" * 60)
    
    # Initialize cleanup manager
    manager = LogCleanupManager(logs_dir, retention_days=7, max_size_mb=100)
    
    # Get current stats
    print("\n1. Current Log Statistics:")
    print("-" * 60)
    stats = manager.get_stats()
    
    if stats['total_files'] == 0:
        print("No log files found.")
    else:
        print(f"Total Files: {stats['total_files']}")
        print(f"Total Size: {stats['total_size_mb']} MB")
        print(f"Oldest File: {stats['oldest_file']['name']} ({stats['oldest_file']['date']})")
        print(f"Newest File: {stats['newest_file']['name']} ({stats['newest_file']['date']})")
    
    # Test cleanup
    print("\n2. Running Cleanup Test:")
    print("-" * 60)
    print(f"Retention Policy: {manager.retention_days} days")
    print(f"Max Size: {manager.max_size_bytes / (1024 * 1024)} MB")
    
    result = manager.cleanup()
    
    print("\n3. Cleanup Results:")
    print("-" * 60)
    
    age_cleanup = result['age_cleanup']
    print(f"Age-based cleanup:")
    print(f"  - Deleted {age_cleanup['deleted_count']} files")
    print(f"  - Freed {age_cleanup.get('deleted_size_mb', 0)} MB")
    
    size_cleanup = result['size_cleanup']
    print(f"Size-based cleanup:")
    print(f"  - Deleted {size_cleanup['deleted_count']} files")
    print(f"  - Freed {size_cleanup.get('deleted_size_mb', 0)} MB")
    
    print(f"\nTotal:")
    print(f"  - Deleted {result['total_deleted_count']} files")
    print(f"  - Freed {result['total_deleted_size_mb']} MB")
    
    # Get updated stats
    print("\n4. Updated Statistics:")
    print("-" * 60)
    stats = manager.get_stats()
    
    if stats['total_files'] == 0:
        print("No log files remaining.")
    else:
        print(f"Total Files: {stats['total_files']}")
        print(f"Total Size: {stats['total_size_mb']} MB")
        print(f"Oldest File: {stats['oldest_file']['name']} ({stats['oldest_file']['date']})")
        print(f"Newest File: {stats['newest_file']['name']} ({stats['newest_file']['date']})")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == '__main__':
    test_cleanup()
