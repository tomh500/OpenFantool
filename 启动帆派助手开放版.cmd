@echo off
setlocal
"%~dp0python\python.exe" -I -S -B -X utf8 "%~dp0launch.py" %*
set "launch_status=%errorlevel%"
if not "%launch_status%"=="0" pause
exit /b %launch_status%
