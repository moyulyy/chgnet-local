@echo off
setlocal EnableExtensions
title ChgNet Studio

rem ===========================================================================
rem  ChgNet Studio - Windows launcher
rem
rem  Uses the conda environment that already ships chgnet + torch + CUDA
rem  (D:\miniconda3\envs\chem_env).  Falls back to py/python when the env is
rem  missing.  The environment is never modified and nothing is installed.
rem ===========================================================================

cd /d "%~dp0"

set "ENV_PY=D:\miniconda3\envs\chem_env\python.exe"

if exist "%ENV_PY%" (
    echo [OK] Using %ENV_PY%
    "%ENV_PY%" main.py
    goto :done
)

echo [WARN] chem_env interpreter not found: %ENV_PY%
echo [..] Falling back to a Python on PATH ...

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python was not found. Install Python or fix the chem_env path.
    pause
    exit /b 1
)

%PY% main.py

:done
endlocal & exit /b %ERRORLEVEL%
