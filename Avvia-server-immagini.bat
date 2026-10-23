@echo off
cd /d "%~dp0"
runtime\python\python.exe -X utf8 scripts\start-image-server.py
if errorlevel 1 pause
