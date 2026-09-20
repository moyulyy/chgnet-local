@echo off
chcp 65001 >nul
set "PYTHON_EXE=D:\miniconda3\envs\chem_env\python.exe"
set "SCRIPT_PATH=%~dp0main.py"
set "WORKDIR=%CD%"
if not exist "%PYTHON_EXE%" (
    echo Python was not found: %PYTHON_EXE%
    pause
    exit /b 1
)
if not exist "%SCRIPT_PATH%" (
    echo Script was not found: %SCRIPT_PATH%
    pause
    exit /b 1
)
"%PYTHON_EXE%" "%SCRIPT_PATH%" --type relax --input "%WORKDIR%\POSCAR" --max-steps 2000 --fmax 0.02

pause
