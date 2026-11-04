@echo off
rem ScanAtlas - lanceur Windows. Double-clic : installe ce qu'il faut la premiere fois, puis ouvre l'application.
cd /d "%~dp0"

set "PYTHON="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if not defined PYTHON (
 python --version >nul 2>&1
 if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
 echo Python 3.10 ou plus recent est introuvable.
 echo Installe-le depuis https://www.python.org/downloads/ ^(coche "Add python.exe to PATH"^), puis relance ce fichier.
 pause
 exit /b 1
)

if not exist .venv\Scripts\python.exe (
 echo Premiere utilisation : creation de l'environnement Python...
 %PYTHON% -m venv .venv
 if errorlevel 1 goto erreur
)
.venv\Scripts\python.exe -c "import numpy, scipy, serial" >nul 2>&1
if errorlevel 1 (
 echo Installation des dependances ^(une seule fois, connexion Internet necessaire^)...
 .venv\Scripts\python.exe -m pip install -r requirements.txt
 if errorlevel 1 goto erreur
)

echo Demarrage de ScanAtlas : le navigateur va s'ouvrir. Fermer cette fenetre quitte l'application.
.venv\Scripts\python.exe scanatlas.py
if errorlevel 1 pause
exit /b 0

:erreur
echo.
echo Installation interrompue : lis le message ci-dessus.
pause
exit /b 1
