@echo off
rem Removes the "friday" command (not your files). Run:  uninstall.bat
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b %EXITCODE%
