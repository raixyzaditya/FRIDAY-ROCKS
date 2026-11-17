@echo off
rem Installs the "friday" command. Double-click it, or run:  install.bat
rem Extra options are passed on, e.g.  install.bat -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set EXITCODE=%ERRORLEVEL%
rem Keep the window open when it was started by double-clicking
echo %cmdcmdline% | find /i "%~nx0" >nul && pause
exit /b %EXITCODE%
