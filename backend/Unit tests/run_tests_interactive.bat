@echo off
REM Quick Test Execution Script
REM Run this to execute all unit tests

REM Set UTF-8 encoding to display emoji characters correctly
chcp 65001 > nul

echo.
echo ========================================
echo    AI Engine - Unit Test Execution
echo ========================================
echo.

REM Check if in correct directory
if not exist "run_tests.py" (
    echo ERROR: run_tests.py not found!
    echo Please run this script from the "Unit tests" directory
    echo.
    pause
    exit /b 1
)

echo Select test module to run:
echo.
echo [1] All Tests (~120 tests)
echo [2] Chat Tests (~40 tests)
echo [3] Mapping Tests (~35 tests)
echo [4] Extraction Tests (~45 tests)
echo [5] Exit
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Running ALL tests...
    py run_tests.py --module all || python run_tests.py --module all || python3 run_tests.py --module all
) else if "%choice%"=="2" (
    echo.
    echo Running CHAT tests...
    py run_tests.py --module chat || python run_tests.py --module chat || python3 run_tests.py --module chat
) else if "%choice%"=="3" (
    echo.
    echo Running MAPPING tests...
    py run_tests.py --module mapping || python run_tests.py --module mapping || python3 run_tests.py --module mapping
) else if "%choice%"=="4" (
    echo.
    echo Running EXTRACTION tests...
    py run_tests.py --module extraction || python run_tests.py --module extraction || python3 run_tests.py --module extraction
) else if "%choice%"=="5" (
    echo.
    echo Exiting...
    exit /b 0
) else (
    echo.
    echo Invalid choice! Please run again.
)

echo.
pause
