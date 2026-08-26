# Browser Logging Implementation Summary

## Status: ✅ COMPLETE (updated for the structured JSONL format, 2026-08-25)

The frontend is fully set up to ship browser console logs to the backend as
structured JSONL, merged with backend logs by `tools/logcat.py`.

## What Was Implemented

### Frontend Components

1. **Logger Utility** (`frontend/src/utils/logger.js`)
   - Intercepts all console methods (log, error, warn, info, debug)
   - Exposes `logger.event()` / `logger.eventOnChange()` for structured
     named debug events with payload data, collapsing repeated identical
     lines into one entry with a repeat count
   - Batches logs for efficient transmission
   - Sends logs to backend every 5 seconds or when 10 logs accumulate
   - Assigns unique session IDs to track browser sessions
   - Maintains original console behavior for developer tools

2. **Logger Initialization** (`frontend/src/main.jsx`)
   - Logger is automatically initialized when the app starts
   - No manual intervention required

### Backend Components

1. **API Routes** (`src/api/routes/logs.py`)
   - `POST /api/logs/browser` - Receives browser logs and writes one JSONL
     envelope per entry (see `src/api/structured_log.py`)
   - `GET /api/logs/browser/files` - Lists all log files (current `.jsonl`
     plus pre-migration `.log` files until they age out of retention)
   - `GET /api/logs/browser/files/<filename>` - Retrieves specific log file

2. **Blueprint Registration** (`src/api/app.py`)
   - Registered logs blueprint at `/api/logs` prefix

3. **`tools/logcat.py`** - condensed live viewer that merges backend and
   browser JSONL chronologically into one colorized stream (`--tail` to
   follow, `--json` for raw output). `tools/start_servers.ps1` opens it
   automatically (opt out with `-NoLogcat`).

### File Storage

- **Location**: `logs/browser/` (frontend), `logs/backend/` (backend, via
  `LOG_JSONL_DIR`, set by default in `tools/run_api.py`)
- **Format**: `YYYY-MM-DD_bucketNN.jsonl` — one JSON envelope per line
- **Envelope fields**: `ts`, `src` (`be`/`fe`), `lvl`, `event`, `session`,
  plus optional `url`, `msg`, `data`, `n` — full schema in `logs/README.md`

### Configuration

- `.gitignore` updated to exclude log files but include documentation
- `logs/README.md` created with comprehensive documentation

## Verification

✅ Log files are being created in `logs/browser/` and `logs/backend/`
✅ Browser console output is being captured (verified with sample logs)
✅ Session tracking is working correctly
✅ Logs include timestamps, levels, event names, and structured data

## Example Log Output

```json
{"ts":"2026-08-22T16:13:23.901Z","src":"fe","lvl":"debug","event":"event.enqueue","session":"session_123_abc","data":{"name":"Passage_Camp Entrance","needsInput":true}}
```

## Benefits

1. **Persistent Debugging**: Console logs are preserved even after browser is closed
2. **Session Tracking**: Each browser session gets its own unique identifier
3. **Non-Intrusive**: Original console behavior is maintained
4. **Automatic**: No manual intervention required
5. **Organized**: Logs are organized by date and session

## Future Enhancements (Optional)

- Add log rotation to prevent disk space issues (✅ done — 7-day retention + 100MB cap, see `logs/README.md`)
- Implement log level filtering (e.g., only capture errors)
- Add compression for older log files
- Create a web UI to view logs
- Add search/filter capabilities (✅ done for viewing — `tools/logcat.py` filters by level/session/source; full-text search still open)

