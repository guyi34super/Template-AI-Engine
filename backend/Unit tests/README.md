# AI Engine Unit Tests

Comprehensive unit test suite for the AI-RAG Engine, organized into three main categories:

## 📁 Test Structure

```
Unit tests/
├── chat/                    # Chat Engine Tests
│   ├── test_chat_handler.py       - Chat-based JSON modification
│   ├── test_json_manager.py       - JSON manipulation utilities
│   └── test_hash_protector.py     - Hash value protection
│
├── mapping/                 # Mapping Engine Tests
│   ├── test_mapping_engine.py     - Intelligent field mapping
│   ├── test_mapping_models.py     - Data models for mapping
│   └── test_mapping_prompts.py    - Prompt templates
│
├── extraction/             # Extraction Tests
│   ├── test_atomic_extractor.py   - Schema-based extraction
│   ├── test_extract_flow.py       - Extraction pipeline
│   ├── test_file_extractors.py    - CSV, XLSX, DOCX, TXT extractors
│   └── test_easyocr_extractor.py  - OCR extraction
│
└── run_tests.py            # Main test runner
```

## 🚀 Running Tests

### Run All Tests
```bash
# Windows (use py launcher)
py run_tests.py --module all

# Or if python is in PATH
python run_tests.py --module all

# Linux/Mac
python3 run_tests.py --module all
```

### Run Specific Module Tests

**Chat Engine Tests Only:**
```bash
py run_tests.py --module chat
```

**Mapping Engine Tests Only:**
```bash
py run_tests.py --module mapping
```

**Windows - use py launcher
py -m unittest chat.test_chat_handler
py -m unittest chat.test_json_manager
py -m unittest chat.test_hash_protector

# Mapping tests
py -m unittest mapping.test_mapping_engine
py -m unittest mapping.test_mapping_models
py -m unittest mapping.test_mapping_prompts

# Extraction tests
py -m unittest extraction.test_atomic_extractor
py -m unittest extraction.test_extract_flow
py -m unittest extraction.test_file_extractors
py -m unittest extraction.test_easyocr_extractor
python -m unittest "Unit tests.mapping.test_mapping_prompts"

# Extraction tests
python -m unittest "Unit tests.extraction.test_atomic_extractor"
python -m unittest "Unit tests.extraction.test_extract_flow"
python -m unittest "Unit tests.extraction.test_file_extractors"
python -m unittest "Unit tests.extraction.test_easyocr_extractor"
```

## 📊 Test Coverage

### Chat Engine Tests (3 files, ~40 test cases)
- ✅ Query processing and operation detection
- ✅ JSON filtering and manipulation
- ✅ Hash value protection during modifications
- ✅ Edge cases: empty data, malformed JSON, special characters
- ✅ Large dataset handling
- ✅ Nested JSON structures

### Mapping Engine Tests (3 files, ~35 test cases)
- ✅ Automatic field mapping with LLM
- ✅ Manual and hybrid mapping strategies
- ✅ Field type detection and conversion
- ✅ Fuzzy field matching
- ✅ Confidence thresholds
- ✅ Data transformation
- ✅ Nested and complex schema handling

### Extraction Tests (4 files, ~45 test cases)
- ✅ Atomic record extraction with vector DB
- ✅ Multi-format file extraction (CSV, XLSX, DOCX, TXT)
- ✅ OCR extraction for images and PDFs
- ✅ Pipeline routing and orchestration
- ✅ Template classification
- ✅ Unicode and special character handling
- ✅ Large file processing

## 🧪 Test Categories

Each test module includes:

1. **Basic Functionality Tests** - Core feature testing
2. **Advanced Scenario Tests** - Complex use cases
3. **Edge Case Tests** - Boundary conditions and error handling
4. **Integration Tests** - Component interaction testing

## 📋 Requirements

Install test dependencies:
```bash
pip install unittest-mock
```

The tests use Python's built-in `unittest` framework and `unittest.mock` for mocking external dependencies.

## 🎯 Test Philosophy

- **Isolated**: Each test is independent and uses mocks for external dependencies
- **Comprehensive**: Covers success paths, failure paths, and edge cases
- **Fast**: Tests run quickly without external API calls or file I/O where possible
- **Maintainable**: Clear test names and well-organized structure

## 📝 Adding New Tests

When adding new tests:

1. Create test file in appropriate category (chat/mapping/extraction)
2. Follow naming convention: `test_<module_name>.py`
3. Use descriptive test method names: `test_<feature>_<scenario>`
4. Include docstrings explaining what each test validates
5. Mock external dependencies (LLM, file I/O, databases)
6. Test both success and failure scenarios

Example:
```python
def test_feature_name_success_case(self):
    """Test that feature works correctly with valid input"""
    # Arrange
    test_input = {"key": "value"}
    
    # Act
    result = function_under_test(test_input)
    
    # Assert
    self.assertEqual(result["status"], "success")
```

## 🐛 Debugging Failed Tests

If tests fail:

1. Run individual test file for detailed output
2. Check mock configurations match actual API
3. Verify test data matches expected format
4. Review error messages and stack traces
5. Use `python -m pdb` for interactive debugging

## 📈 CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Unit Tests
  run: |
    python "Unit tests/run_tests.py" --module all
```

## 🔧 Configuration

Tests use mocked dependencies by default. To test against real services:

1. Set environment variables for API endpoints
2. Update mock configurations in test files
3. Be aware this will slow down test execution

## 📚 Additional Resources

- Python unittest documentation: https://docs.python.org/3/library/unittest.html
- unittest.mock guide: https://docs.python.org/3/library/unittest.mock.html
- Test-Driven Development best practices

---

**Last Updated:** January 14, 2026
**Total Test Count:** ~120 test cases
**Estimated Run Time:** < 5 seconds (all tests)
