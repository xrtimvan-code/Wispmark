@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw floating_notepad.py
) else (
    start "" python floating_notepad.py
)
