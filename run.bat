@echo off
setlocal EnableExtensions
title ChgNet Studio

rem ===========================================================================
rem  ChgNet Studio - Windows launcher
rem
rem  Finds a Python interpreter that has chgnet + torch installed and starts
rem  the GUI with it.  Nothing is installed and no environment is modified.
rem
rem  Interpreter resolution order:
rem    1. %CHGNET_PYTHON%   - set this to force an exact python.exe path
rem    2. %CONDA_PREFIX%    - the conda environment currently activated
rem    3. conda base "envs\%CHGNET_ENV%" (from `conda info --base`)
rem    4. "envs\%CHGNET_ENV%" under the common conda/anaconda install roots
rem    5. py -3 / python found on PATH
rem
rem  %CHGNET_ENV% defaults to chem_env; override it if your environment has a
rem  different name, e.g.   set CHGNET_ENV=my_chgnet_env
rem ===========================================================================

cd /d "%~dp0"

set "ENV_NAME=chem_env"
if defined CHGNET_ENV set "ENV_NAME=%CHGNET_ENV%"

set "PY="
set "PY_SOURCE="

rem --- 1) explicit override ------------------------------------------------
if defined CHGNET_PYTHON (
    if exist "%CHGNET_PYTHON%" (
        set "PY="%CHGNET_PYTHON%""
        set "PY_SOURCE=CHGNET_PYTHON"
    ) else (
        echo [WARN] CHGNET_PYTHON is set but does not exist: %CHGNET_PYTHON%
    )
)

rem --- 2) currently activated conda env ------------------------------------
if not defined PY if defined CONDA_PREFIX (
    if exist "%CONDA_PREFIX%\python.exe" (
        set "PY="%CONDA_PREFIX%\python.exe""
        set "PY_SOURCE=CONDA_PREFIX"
    )
)

rem --- 3) conda base discovered from PATH ----------------------------------
if not defined PY (
    for /f "delims=" %%B in ('conda info --base 2^>nul') do (
        if not defined PY if exist "%%B\envs\%ENV_NAME%\python.exe" (
            set "PY="%%B\envs\%ENV_NAME%\python.exe""
            set "PY_SOURCE=conda base %%B"
        )
    )
)

rem --- 4) common conda / anaconda install roots ----------------------------
if not defined PY (
    for %%R in (
        "%USERPROFILE%\miniconda3"
        "%USERPROFILE%\Miniconda3"
        "%USERPROFILE%\anaconda3"
        "%USERPROFILE%\Anaconda3"
        "%LOCALAPPDATA%\miniconda3"
        "%LOCALAPPDATA%\Miniconda3"
        "%LOCALAPPDATA%\anaconda3"
        "%LOCALAPPDATA%\Anaconda3"
        "%LOCALAPPDATA%\Continuum\anaconda3"
        "%ProgramData%\miniconda3"
        "%ProgramData%\Miniconda3"
        "%ProgramData%\Anaconda3"
        "%ProgramFiles%\miniconda3"
        "%ProgramFiles%\Anaconda3"
        "C:\miniconda3"
        "C:\anaconda3"
        "D:\miniconda3"
        "D:\anaconda3"
    ) do (
        if not defined PY if exist "%%~R\envs\%ENV_NAME%\python.exe" (
            set "PY="%%~R\envs\%ENV_NAME%\python.exe""
            set "PY_SOURCE=%%~R"
        )
    )
)

rem --- 5) plain Python on PATH ---------------------------------------------
if not defined PY (
    where py >nul 2>nul && (
        set "PY=py -3"
        set "PY_SOURCE=PATH (py -3)"
    )
)
if not defined PY (
    where python >nul 2>nul && (
        set "PY=python"
        set "PY_SOURCE=PATH (python)"
    )
)

if not defined PY (
    echo.
    echo [ERROR] No Python interpreter could be found.
    echo.
    echo   Install the compute environment first, then either
    echo     * put it on PATH, or
    echo     * set CHGNET_PYTHON to its python.exe, e.g.
    echo         set CHGNET_PYTHON=C:\Users\you\miniconda3\envs\chem_env\python.exe
    echo     * or set CHGNET_ENV if your environment is not called chem_env.
    echo.
    echo   See the "Installation" section of README.md.
    echo.
    pause
    exit /b 1
)

echo [OK] Python  : %PY%
echo [..] Source  : %PY_SOURCE%
echo [..] Starting ChgNet Studio ...

%PY% main.py %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [ERROR] ChgNet Studio exited with code %RC%.
    echo         If this mentions "No module named", install the GUI
    echo         dependencies with:  pip install -r requirements.txt
    echo.
    pause
)

endlocal & exit /b %RC%
