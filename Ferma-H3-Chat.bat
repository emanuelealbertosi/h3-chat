@echo off
cd /d "%~dp0"
if exist "%~dp0runtime\python\pythonw.exe" start "" "%~dp0runtime\python\pythonw.exe" "%~dp0launcher.py" --stop
