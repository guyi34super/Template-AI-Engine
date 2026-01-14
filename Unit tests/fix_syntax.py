"""
Script to properly fix test files after removing skipTest statements
"""

import re
from pathlib import Path


def fix_merged_lines(file_path):
    """Fix cases where method definition got merged with docstring"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Fix pattern: def test_name(self):"""docstring"""
    # Should be: def test_name(self):\n        """docstring"""
    pattern = r'(def test_\w+\(self\):)("""[^"]+""")'
    replacement = r'\1\n        \2'
    
    content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    """Fix all test files"""
    test_dirs = ['chat', 'mapping', 'extraction']
    fixed_files = []
    
    for dir_name in test_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
        
        for test_file in dir_path.glob('test_*.py'):
            if fix_merged_lines(test_file):
                fixed_files.append(str(test_file))
                print(f"✅ Fixed: {test_file}")
    
    print(f"\n✅ Total files fixed: {len(fixed_files)}")


if __name__ == "__main__":
    main()
