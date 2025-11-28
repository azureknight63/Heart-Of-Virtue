# Browser Logging System

This directory contains browser console logs captured from the frontend application.

## Overview

The browser logging system automatically captures all console output (log, error, warn, info, debug) from the frontend and sends it to the backend for persistent storage.

## Features

- **Automatic Capture**: Intercepts all console methods while maintaining normal console behavior
- **Batching**: Logs are batched and sent in groups to reduce network overhead
- **Session Tracking**: Each browser session gets a unique ID for log organization
- **Periodic Flushing**: Logs are automatically sent every 5 seconds or when batch size is reached
- **Page Unload Handling**: Remaining logs are flushed when the page is closed
- **Automated Cleanup**: Old logs are automatically removed based on retention policy

## Automated Log Cleanup

The system automatically cleans up old log files to prevent disk space issues:

- **Retention Period**: Logs older than 7 days are automatically deleted
- **Size Limit**: If total logs exceed 100MB, oldest files are deleted first
- **Cleanup Trigger**: Runs automatically after each log write operation
- **Silent Operation**: Cleanup failures don't affect log writing

### Cleanup Configuration

Default settings (configurable in `src/api/routes/logs.py`):
- **Retention Days**: 7 days
- **Max Total Size**: 100 MB

## Log File Format

Log files are stored with the naming convention:
```
YYYY-MM-DD_session_TIMESTAMP_RANDOMID.log
```

Each log entry follows this format:
```
[TIMESTAMP] [LEVEL] [URL] MESSAGE
```

Example:
```
[2025-11-27T18:41:11.123Z] [ERROR] [http://localhost:3000/game] Failed to fetch combat status
```

## API Endpoints

### POST /api/logs/browser
Receives browser logs from the frontend and triggers automatic cleanup.

**Payload:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-27T18:41:11.123Z",
      "level": "ERROR",
      "message": "Error message",
      "url": "http://localhost:3000/",
      "userAgent": "Mozilla/5.0..."
    }
  ],
  "session_id": "session_1234567890_abc123"
}
```

### GET /api/logs/browser/files
Lists all available browser log files.

**Response:**
```json
{
  "files": [
    {
      "filename": "2025-11-27_session_1234567890_abc123.log",
      "size": 12345,
      "modified": "2025-11-27T18:41:11.123Z"
    }
  ]
}
```

### GET /api/logs/browser/files/<filename>
Retrieves the contents of a specific log file.

**Response:**
```json
{
  "filename": "2025-11-27_session_1234567890_abc123.log",
  "content": "[2025-11-27T18:41:11.123Z] [ERROR] [http://localhost:3000/] Error message\n..."
}
```

### DELETE /api/logs/browser/files/<filename>
Deletes a specific browser log file.

**Response:**
```json
{
  "message": "Successfully deleted 2025-11-27_session_1234567890_abc123.log",
  "deleted_size": 12345
}
```

### POST /api/logs/browser/cleanup
Manually trigger log cleanup with optional custom settings.

**Optional Payload:**
```json
{
  "retention_days": 7,
  "max_size_mb": 100
}
```

**Response:**
```json
{
  "message": "Cleanup completed",
  "result": {
    "age_cleanup": {
      "deleted_count": 5,
      "deleted_size_mb": 2.5
    },
    "size_cleanup": {
      "deleted_count": 2,
      "deleted_size_mb": 1.2
    },
    "total_deleted_count": 7,
    "total_deleted_size_mb": 3.7
  }
}
```

### GET /api/logs/browser/stats
Get statistics about browser log files and cleanup configuration.

**Response:**
```json
{
  "stats": {
    "total_files": 10,
    "total_size_mb": 5.2,
    "oldest_file": {
      "name": "2025-11-20_session_123.log",
      "date": "2025-11-20T10:30:00"
    },
    "newest_file": {
      "name": "2025-11-27_session_456.log",
      "date": "2025-11-27T18:41:11"
    }
  },
  "cleanup_config": {
    "retention_days": 7,
    "max_size_mb": 100
  }
}
```

## Frontend Implementation

The logger is initialized in `frontend/src/main.jsx`:

```javascript
import logger from './utils/logger.js'

// Initialize browser logging
logger.init()
```

## Configuration

### Frontend
- **BATCH_SIZE**: 10 logs (configurable in `frontend/src/utils/logger.js`)
- **FLUSH_INTERVAL**: 5000ms (5 seconds)
- **LOG_ENDPOINT**: `/api/logs/browser`

### Backend Cleanup
- **RETENTION_DAYS**: 7 days (configurable in `src/api/routes/logs.py`)
- **MAX_SIZE_MB**: 100 MB (configurable in `src/api/routes/logs.py`)

## Disabling Logging

To disable browser logging, comment out the logger initialization in `frontend/src/main.jsx`:

```javascript
// logger.init()
```

## Notes

- Log files are automatically excluded from version control via `.gitignore`
- The logger maintains original console behavior, so developer tools continue to work normally
- Session IDs are stored in `sessionStorage` and reset when the browser tab is closed
- Automated cleanup runs silently and doesn't affect log writing operations
- Manual cleanup can be triggered via the API with custom retention settings

