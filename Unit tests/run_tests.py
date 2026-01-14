"""
Main Unit Test Runner
Run all tests across chat, mapping, and extraction modules

Usage:
    py run_tests.py --module all
    py run_tests.py --module chat
    py run_tests.py --module mapping
    py run_tests.py --module extraction
"""

import unittest
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def run_all_tests():
    """Discover and run all unit tests"""
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_chat_tests():
    """Run only chat engine tests"""
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'chat')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_mapping_tests():
    """Run only mapping engine tests"""
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'mapping')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_extraction_tests():
    """Run only extraction tests"""
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'extraction')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import argparse
    
    # Reset audit logger for new session
    reset_audit_logger()
    audit_logger = get_audit_logger()
    
    # Log environment info
    audit_logger.log_environment_info({
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    parser = argparse.ArgumentParser(description='Run AI Engine Unit Tests')
    parser.add_argument(
        '--module',
        choices=['all', 'chat', 'mapping', 'extraction'],
        default='all',
        help='Which test module to run (default: all)'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print(f"Running AI Engine Unit Tests - Module: {args.module.upper()}")
    print(f"{'='*70}\n")
    
    success = False
    
    try:
        if args.module == 'all':
            success = run_all_tests()
        elif args.module == 'chat':
            success = run_chat_tests()
        elif args.module == 'mapping':
            success = run_mapping_tests()
        elif args.module == 'extraction':
            success = run_extraction_tests()
    except Exception as e:
        audit_logger.log_error_details("CRITICAL", str(e), traceback_str=None)
        raise
    finally:
        # Finalize audit log
        audit_logger.finalize()
    
    parser = argparse.ArgumentParser(description='Run AI Engine Unit Tests')
    parser.add_argument(
        '--module',
        choices=['all', 'chat', 'mapping', 'extraction'],
        default='all',
        help='Which test module to run (default: all)'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print(f"Running AI Engine Unit Tests - Module: {args.module.upper()}")
    print(f"{'='*70}\n")
    
    success = False
    
    if args.module == 'all':
        success = run_all_tests()
    elif args.module == 'chat':
        success = run_chat_tests()
    elif args.module == 'mapping':
        success = run_mapping_tests()
    elif args.module == 'extraction':
        success = run_extraction_tests()
    
    print(f"\n{'='*70}")
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print(f"{'='*70}