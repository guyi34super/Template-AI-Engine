"""
Audit Logger - Comprehensive activity tracking for AI Engine
Logs all operations: extractions, mappings, chat interactions, API calls
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import traceback


class AuditLogger:
    """Centralized audit logging for AI Engine operations"""
    
    def __init__(self, log_dir: str = "audit/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped session file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{self.session_id}.json"
        self.log_file = self.log_dir / f"activity_{self.session_id}.log"
        
        # Setup file logging
        self.logger = logging.getLogger(f'AuditLogger_{self.session_id}')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()  # Clear any existing handlers
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Session data
        self.session_data = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "operations": [],
            "extractions": [],
            "mappings": [],
            "chat_interactions": [],
            "api_calls": [],
            "errors": [],
            "warnings": []
        }
        
        self.logger.info("="*100)
        self.logger.info(f"AI ENGINE AUDIT SESSION STARTED: {self.session_id}")
        self.logger.info("="*100)
    
    def log_extraction(self, operation: str, file_path: str, template: str = None, 
                      record_count: int = 0, duration: float = 0, status: str = "success",
                      error: str = None):
        """Log extraction operation"""
        extraction_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "file_path": file_path,
            "template": template,
            "record_count": record_count,
            "duration_seconds": round(duration, 3),
            "status": status
        }
        
        if error:
            extraction_data["error"] = error
            self.logger.error(f"❌ EXTRACTION FAILED: {operation}")
            self.logger.error(f"   File: {file_path}")
            self.logger.error(f"   Error: {error}")
        else:
            self.logger.info(f"📄 EXTRACTION: {operation}")
            self.logger.info(f"   File: {file_path}")
            self.logger.info(f"   Template: {template}")
            self.logger.info(f"   Records: {record_count}")
            self.logger.info(f"   Duration: {duration:.3f}s")
        
        self.session_data["extractions"].append(extraction_data)
    
    def log_mapping(self, source_schema: str, target_schema: str, 
                   mapping_count: int = 0, strategy: str = "auto",
                   confidence: float = 0.0, duration: float = 0,
                   status: str = "success", error: str = None):
        """Log mapping operation"""
        mapping_data = {
            "timestamp": datetime.now().isoformat(),
            "source_schema": source_schema,
            "target_schema": target_schema,
            "mapping_count": mapping_count,
            "strategy": strategy,
            "confidence": round(confidence, 2),
            "duration_seconds": round(duration, 3),
            "status": status
        }
        
        if error:
            mapping_data["error"] = error
            self.logger.error(f"❌ MAPPING FAILED")
            self.logger.error(f"   Source: {source_schema}")
            self.logger.error(f"   Target: {target_schema}")
            self.logger.error(f"   Error: {error}")
        else:
            self.logger.info(f"🔗 MAPPING: {strategy.upper()}")
            self.logger.info(f"   Source: {source_schema}")
            self.logger.info(f"   Target: {target_schema}")
            self.logger.info(f"   Mappings: {mapping_count}")
            self.logger.info(f"   Confidence: {confidence:.2f}")
            self.logger.info(f"   Duration: {duration:.3f}s")
        
        self.session_data["mappings"].append(mapping_data)
    
    def log_chat_interaction(self, query: str, operation: str, 
                            records_affected: int = 0, records_modified: int = 0,
                            duration: float = 0, status: str = "success",
                            error: str = None):
        """Log chat-based data modification"""
        chat_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "operation": operation,
            "records_affected": records_affected,
            "records_modified": records_modified,
            "duration_seconds": round(duration, 3),
            "status": status
        }
        
        if error:
            chat_data["error"] = error
            self.logger.error(f"❌ CHAT INTERACTION FAILED")
            self.logger.error(f"   Query: {query}")
            self.logger.error(f"   Error: {error}")
        else:
            self.logger.info(f"💬 CHAT: {operation}")
            self.logger.info(f"   Query: {query}")
            self.logger.info(f"   Affected: {records_affected} records")
            self.logger.info(f"   Modified: {records_modified} records")
            self.logger.info(f"   Duration: {duration:.3f}s")
        
        self.session_data["chat_interactions"].append(chat_data)
    
    def log_api_call(self, endpoint: str, method: str, status_code: int = 200,
                    duration: float = 0, request_data: Dict = None,
                    response_data: Dict = None, error: str = None):
        """Log API call"""
        api_data = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_seconds": round(duration, 3)
        }
        
        if request_data:
            api_data["request_data"] = request_data
        if response_data:
            api_data["response_data"] = response_data
        if error:
            api_data["error"] = error
            self.logger.error(f"❌ API ERROR: {method} {endpoint}")
            self.logger.error(f"   Status: {status_code}")
            self.logger.error(f"   Error: {error}")
        else:
            self.logger.info(f"🌐 API: {method} {endpoint}")
            self.logger.info(f"   Status: {status_code}")
            self.logger.info(f"   Duration: {duration:.3f}s")
        
        self.session_data["api_calls"].append(api_data)
    
    def log_operation(self, operation_type: str, operation_name: str,
                     details: Dict[str, Any] = None, duration: float = 0,
                     status: str = "success", error: str = None):
        """Log generic operation"""
        operation_data = {
            "timestamp": datetime.now().isoformat(),
            "type": operation_type,
            "name": operation_name,
            "duration_seconds": round(duration, 3),
            "status": status
        }
        
        if details:
            operation_data["details"] = details
        if error:
            operation_data["error"] = error
            self.logger.error(f"❌ OPERATION FAILED: {operation_name}")
            self.logger.error(f"   Type: {operation_type}")
            self.logger.error(f"   Error: {error}")
        else:
            self.logger.info(f"⚙️  OPERATION: {operation_name}")
            self.logger.info(f"   Type: {operation_type}")
            if details:
                for key, value in details.items():
                    self.logger.info(f"   {key}: {value}")
            self.logger.info(f"   Duration: {duration:.3f}s")
        
        self.session_data["operations"].append(operation_data)
    
    def log_error(self, error_type: str, error_message: str, 
                 context: Dict[str, Any] = None, traceback_str: str = None):
        """Log error with context"""
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message
        }
        
        if context:
            error_data["context"] = context
        if traceback_str:
            error_data["traceback"] = traceback_str
        
        self.logger.error(f"💥 ERROR: {error_type}")
        self.logger.error(f"   Message: {error_message}")
        if context:
            self.logger.error(f"   Context: {json.dumps(context, indent=2)}")
        if traceback_str:
            self.logger.error(f"   Traceback:\n{traceback_str}")
        
        self.session_data["errors"].append(error_data)
    
    def log_warning(self, warning_type: str, warning_message: str,
                   context: Dict[str, Any] = None):
        """Log warning"""
        warning_data = {
            "timestamp": datetime.now().isoformat(),
            "warning_type": warning_type,
            "warning_message": warning_message
        }
        
        if context:
            warning_data["context"] = context
        
        self.logger.warning(f"⚠️  WARNING: {warning_type}")
        self.logger.warning(f"   Message: {warning_message}")
        if context:
            self.logger.warning(f"   Context: {json.dumps(context, indent=2)}")
        
        self.session_data["warnings"].append(warning_data)
    
    def log_info(self, message: str, details: Dict[str, Any] = None):
        """Log informational message"""
        self.logger.info(f"ℹ️  {message}")
        if details:
            for key, value in details.items():
                self.logger.info(f"   {key}: {value}")
    
    def finalize(self):
        """Finalize audit session and save JSON report"""
        self.session_data["end_time"] = datetime.now().isoformat()
        
        # Calculate duration
        start = datetime.fromisoformat(self.session_data["start_time"])
        end = datetime.fromisoformat(self.session_data["end_time"])
        duration = (end - start).total_seconds()
        self.session_data["total_duration_seconds"] = round(duration, 3)
        
        # Calculate statistics
        self.session_data["statistics"] = {
            "total_extractions": len(self.session_data["extractions"]),
            "total_mappings": len(self.session_data["mappings"]),
            "total_chat_interactions": len(self.session_data["chat_interactions"]),
            "total_api_calls": len(self.session_data["api_calls"]),
            "total_operations": len(self.session_data["operations"]),
            "total_errors": len(self.session_data["errors"]),
            "total_warnings": len(self.session_data["warnings"])
        }
        
        # Save JSON report
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info("="*100)
        self.logger.info(f"SESSION COMPLETE - Duration: {duration:.2f}s")
        self.logger.info(f"Statistics: {json.dumps(self.session_data['statistics'], indent=2)}")
        self.logger.info(f"Audit log saved: {self.log_file}")
        self.logger.info(f"JSON report saved: {self.session_file}")
        self.logger.info("="*100)
        
        # Create latest symlinks/copies for easy access
        self._create_latest_reports()
    
    def _create_latest_reports(self):
        """Create 'latest' copies of reports for easy access"""
        import shutil
        
        latest_log = self.log_dir / "latest.log"
        latest_json = self.log_dir / "latest.json"
        
        try:
            shutil.copy2(self.log_file, latest_log)
            shutil.copy2(self.session_file, latest_json)
        except Exception as e:
            self.logger.error(f"Failed to create latest reports: {e}")


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

def reset_audit_logger():
    """Reset global audit logger (for new sessions)"""
    global _audit_logger
    if _audit_logger:
        _audit_logger.finalize()
    _audit_logger = None
