"""
Script to enable all disabled tests by removing skipTest statements
"""

import re
from pathlib import Path


def remove_skip_statements(file_path):
    """Remove self.skipTest lines from test file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match skipTest lines
    pattern = r'\s*self\.skipTest\("Disabled - API mismatch"\)\s*\n\s*return\s*#\s*'
    
    # Remove skipTest statements
    content = re.sub(pattern, '', content)
    
    # Also remove standalone skipTest without return
    pattern2 = r'\s*self\.skipTest\("Disabled - API mismatch"\)\s*\n'
    content = re.sub(pattern2, '', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    """Enable all tests"""
    test_dirs = ['chat', 'mapping', 'extraction']
    modified_files = []
    
    for dir_name in test_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
        
        for test_file in dir_path.glob('test_*.py'):
            if remove_skip_statements(test_file):
                modified_files.append(str(test_file))
                print(f"✅ Enabled tests in: {test_file}")
    
    print(f"\n✅ Total files modified: {len(modified_files)}")
    for file in modified_files:
        print(f"   - {file}")


if __name__ == "__main__":
    main()
