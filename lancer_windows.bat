@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Lance d'abord installer_windows.bat
 pause
 exit /b 1
)
.venv\Scripts\python.exe -c "import scipy" >nul 2>&1
if errorlevel 1 (
 echo Dependances a mettre a jour : relance installer_windows.bat puis ce lanceur.
 pause
 exit /b 1
)
.venv\Scripts\python.exe scanatlas.py
if errorlevel 1 pause
