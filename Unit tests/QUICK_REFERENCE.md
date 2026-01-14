# Unit Tests Quick Reference

## 🚀 Quick Commands

### Run All Tests
```bash
# Windows (recommended - use py launcher)
py run_tests.py --module all

# Alternative if python is in PATH
python run_tests.py --module all

# Linux/Mac
python3 run_tests.py --module all
```

### Run by Category
```bash
# Chat tests only
py run_tests.py --module chat

# Mapping tests only
py run_tests.py --module mapping
Windows - from Unit tests directory
cd "Unit tests"

# Chat tests
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
py -m unittest mapping.test_mapping_models
python -m unittest Unit tests.mapping.test_mapping_prompts

# Extraction
python -m unittest Unit tests.extraction.test_atomic_extractor
python -m unittest Unit tests.extraction.test_extract_flow
python -m unittest Unit tests.extraction.test_file_extractors
python -m unittest Unit tests.extraction.test_easyocr_extractor
```

## 📊 Test Count by Category

| Category   | Test Files | Test Cases |
|------------|------------|------------|
| Chat       | 3          | ~40        |
| Mapping    | 3          | ~35        |
| Extraction | 4          | ~45        |
| **Total**  | **10**     | **~120**   |

## 📁 File Structure
```
Unit tests/
├── chat/              (3 test files)
├── mapping/           (3 test files)
├── extraction/        (4 test files)
├── run_tests.py       (Master runner)
└── README.md          (Full docs)
```

## ✅ What's Tested

### Chat Engine
- Query processing & operation detection
- JSON filtering & manipulation
- Hash value protection
- Edge cases & error handling

### Mapping Engine
- Auto/manual/hybrid field mapping
- Type detection & conversion
- Fuzzy matching & confidence scoring
- Complex schema handling

### Extraction
- Multi-format file extraction (CSV, XLSX, DOCX, TXT)
- OCR extraction (images, PDFs)
- Atomic record extraction
- Pipeline routing & orchestration

## 🛠️ Setup (One-time)
```bash
# Windows
cd "Unit tests"
setup_tests.bat

# Linux/Mac
cd "Unit tests"
chmod +x setup_tests.sh
./setup_tests.sh
```

## 🐛 Debugging Failed Tests

### Verbose Mode
```bash
python -m unittest Unit tests.chat.test_chat_handler -v
```

### Single Test Method
```bash
python -m unittest Unit tests.chat.test_chat_handler.TestChatHandler.test_initialization
```

### With Debugger
```bash
python -m pdb -m unittest Unit tests.chat.test_chat_handler
```

## 📈 Success Indicators

After running tests, you should see:
```
✅ ALL TESTS PASSED
```

If tests fail:
- Check error messages
- Review stack traces
- Verify mock configurations
- Ensure dependencies installed

## 🔗 Related Files

- `README.md` - Comprehensive documentation
- `IMPLEMENTATION_SUMMARY.md` - Detailed overview
- `requirements.txt` - Test dependencies
- `run_tests.py` - Test execution script

## ⚡ Tips

1. Run tests frequently during development
2. Add new tests for new features
3. Mock external dependencies
4. Keep tests fast and isolated
5. Use descriptive test names

---

**Last Updated**: January 14, 2026
