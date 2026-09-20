@echo off
chcp 65001 >nul
rem %CHGNET_PYTHON% overrides the default; otherwise use the original path
set "PYTHON_EXE=%CHGNET_PYTHON%"
if not defined PYTHON_EXE set "PYTHON_EXE=D:\miniconda3\envs\chem_env\python.exe"
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
"%PYTHON_EXE%" "%SCRIPT_PATH%" --input "%WORKDIR%\POSCAR" --output CONTCAR --temperature 300 --timestep 1.0 --steps 1000 --loginterval 1 --ensemble nvt --thermostat Nose-Hoover

pause
