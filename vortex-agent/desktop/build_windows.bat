@echo off
setlocal

REM Build Vortex Agent Desktop executable (Windows 10/11)
cd /d %~dp0
python -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name VortexAgentDesktop main.py

echo Build complete. Executable: dist\VortexAgentDesktop\VortexAgentDesktop.exe
endlocal
