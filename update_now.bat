@echo off
REM Double-click this (or a shortcut to it) to push a dashboard update now.
REM Pin a shortcut to the taskbar or the desktop for one-click access.

cd /d "%~dp0"
python update_now.py

REM Keep the window open if something went wrong so the error is readable.
if errorlevel 1 pause
