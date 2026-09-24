@echo off
cd /d "%~dp0"
if not exist "%~dp0runtime\python\python.exe" (call "%~dp0Installa-H3-Chat.bat" & exit /b)
title H3-Chat - Log applicazione
"%~dp0runtime\python\python.exe" -X utf8 -u "%~dp0launcher.py"
