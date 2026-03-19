"""
Test Audit Logger
Demonstrates audit logging capabilities
"""

import time
from audit import get_audit_logger

def main():
    # Get audit logger
    audit = get_audit_logger()
    
    print("🔍 Testing Audit Logger...")
    print("-" * 60)
    
    # Test extraction logging
    audit.log_extraction(
        operation="pdf_extract",
        file_path="documents/employee_data.pdf",
        template="Employee Template",
        record_count=150,
        duration=2.5,
        status="success"
    )
    
    # Test mapping logging
    audit.log_mapping(
        source_schema="Uploaded CSV",
        target_schema="Employee Template",
        mapping_count=12,
        strategy="auto",
        confidence=0.95,
        duration=1.2,
        status="success"
    )
    
    # Test chat interaction logging
    audit.log_chat_interaction(
        query="Update salary for employee 001 to $75000",
        operation="update_values",
        records_affected=1,
        records_modified=1,
        duration=0.8,
        status="success"
    )
    
    # Test API call logging
    audit.log_api_call(
        endpoint="/api/extract",
        method="POST",
        status_code=200,
        duration=3.2
    )
    
    # Test operation logging
    audit.log_operation(
        operation_type="data_validation",
        operation_name="validate_employee_records",
        details={"records_validated": 150, "errors_found": 0},
        duration=0.5,
        status="success"
    )
    
    # Test warning logging
    audit.log_warning(
        warning_type="DataQuality",
        warning_message="Missing values detected in optional fields",
        context={"field": "middle_name", "missing_count": 25}
    )
    
    # Test error logging (simulated)
    audit.log_error(
        error_type="ValidationError",
        error_message="Invalid email format",
        context={"field": "email", "value": "not-an-email", "record_id": "EMP-123"}
    )
    
    # Test failed operation
    audit.log_extraction(
        operation="corrupted_pdf_extract",
        file_path="documents/corrupted.pdf",
        template="Employee Template",
        record_count=0,
        duration=0.1,
        status="failed",
        error="PDF file is corrupted or encrypted"
    )
    
    # General info logging
    audit.log_info(
        "Processing batch completed",
        details={"batch_size": 100, "processing_time": "2.5s"}
    )
    
    # Finalize session
    audit.finalize()
    
    print("-" * 60)
    print("✅ Audit logging test complete!")
    print(f"\n📋 Check audit logs at:")
    print(f"   - audit/logs/latest.log")
    print(f"   - audit/logs/latest.json")

if __name__ == "__main__":
    main()
