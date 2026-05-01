@echo off
cd /d C:\Users\danfl\OneDrive\Stuff\gspro-dashboard-project

:: Add all changed files
git add .

:: Commit with a timestamp
git commit -m "Auto-update: %date% %time%"

:: Push to the repo
git push -f origin main