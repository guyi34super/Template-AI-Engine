# AI Engine Unit Tests - PowerShell Runner
# This script properly handles UTF-8 encoding for emoji characters
# Usage: .\run_tests.ps1 [-Module <all|chat|mapping|extraction>]

param(
    [string]$Module = "all"
)

# Set console encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# Get Python path
$pythonPath = "C:\Users\P12B91B\AppData\Local\Programs\Python\Python313\python.exe"

# Set working directory
Set-Location "c:\Users\P12B91B\OneDrive - Ceridian HCM Inc\Desktop\AI-Rag Engine\ai-engine\Unit tests"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Running AI Engine Unit Tests - Module: $($Module.ToUpper())" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Run tests
& $pythonPath run_tests.py --module $Module

# Show results
Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Tests completed successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Some tests failed. Review output above." -ForegroundColor Red
}
Write-Host ""
