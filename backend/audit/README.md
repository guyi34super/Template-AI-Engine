# Audit Logs

This directory contains comprehensive audit trails of all AI Engine operations.

## Generated Files

- `logs/activity_YYYYMMDD_HHMMSS.log` - Detailed activity log
- `logs/session_YYYYMMDD_HHMMSS.json` - Structured JSON session report
- `logs/latest.log` - Most recent activity log
- `logs/latest.json` - Most recent session report

## What Gets Logged

1. **Extractions** - Document processing, data extraction operations
2. **Mappings** - Field mapping operations, schema transformations
3. **Chat Interactions** - Natural language data modifications
4. **API Calls** - All API endpoint requests and responses
5. **Errors** - Detailed error tracking with tracebacks
6. **Warnings** - Non-critical issues and alerts
7. **Operations** - General system operations

## Usage

```python
from audit import get_audit_logger

audit = get_audit_logger()

# Log extraction
audit.log_extraction(
    operation="pdf_extract",
    file_path="document.pdf",
    template="Employee",
    record_count=150,
    duration=2.5
)

# Log mapping
audit.log_mapping(
    source_schema="CSV",
    target_schema="Employee Template",
    mapping_count=12,
    confidence=0.95
)

# Log chat interaction
audit.log_chat_interaction(
    query="Update salary for employee 001",
    operation="update_values",
    records_affected=1,
    records_modified=1
)

# Log errors
audit.log_error(
    error_type="ValidationError",
    error_message="Invalid field format",
    context={"field": "email", "value": "invalid"}
)

# Finalize session
audit.finalize()
```

## Log Retention

Logs are preserved indefinitely for compliance and debugging. Consider archiving old logs periodically.
