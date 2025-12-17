@echo off
REM Augustus Development Launcher
REM This batch file launches the PowerShell development script

echo.
echo   Starting Augustus Development Server...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0dev.ps1"

pause

