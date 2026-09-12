@echo off
cd /d "%~dp0"
if not exist "%~dp0runtime\python\pythonw.exe" (call "%~dp0Installa-H3-Chat.bat" & exit /b)
start "" "%~dp0runtime\python\pythonw.exe" "%~dp0launcher.py"
