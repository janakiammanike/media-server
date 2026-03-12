@echo off
setlocal
cd /d "%~dp0"

echo ======================================
echo MediaVault Pro Desktop EXE Build
echo ======================================

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

if errorlevel 1 (
  echo Failed to activate virtual environment.
  pause
  exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing project requirements...
pip install -r requirements.txt
if errorlevel 1 goto :fail

echo Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 goto :fail

if exist "app.ico" (
  echo Building desktop EXE with icon...
  pyinstaller --noconfirm --clean --windowed --name MediaVaultProDesktop --icon app.ico desktop_app.py
) else (
  echo No app.ico found. Building without icon...
  pyinstaller --noconfirm --clean --windowed --name MediaVaultProDesktop desktop_app.py
)
if errorlevel 1 goto :fail

echo.
echo Build completed successfully.
echo EXE location:
echo %cd%\dist\MediaVaultProDesktop\MediaVaultProDesktop.exe
pause
exit /b 0

:fail
echo.
echo Build failed. Please check the output above.
pause
exit /b 1
