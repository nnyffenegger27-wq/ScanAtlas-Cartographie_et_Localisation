@echo off
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
 echo Python 3 introuvable. Installe Python 3.10 ou plus recent, puis relance ce fichier.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto erreur
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto erreur
echo Installation terminee. Lance maintenant lancer_windows.bat
pause
exit /b 0
:erreur
echo Installation interrompue. Lis le message ci-dessus.
pause
exit /b 1
