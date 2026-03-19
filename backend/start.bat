@echo off
REM AI-RAG Engine Startup Script for Windows

echo ============================================
echo AI-RAG Document Processing Engine
echo ============================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and configure it.
    echo.
    pause
    exit /b 1
)

REM Load environment variables from .env (Windows doesn't auto-load)
echo Loading environment variables...
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    set "line=%%a"
    if not "!line:~0,1!"=="#" (
        if not "%%a"=="" (
            set "%%a=%%b"
        )
    )
)

echo.
echo Starting server...
echo Host: %HOST% (default: 0.0.0.0)
echo Port: %PORT% (default: 8000)
echo.
echo API Documentation: http://localhost:%PORT%/docs
echo.

python api_server.py

if errorlevel 1 (
    echo.
    echo ERROR: Server failed to start
    pause
)
