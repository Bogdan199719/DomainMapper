@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
python -m domainmapper
if errorlevel 1 (
    echo.
    echo Failed to start MyDomainMapper.
    echo Check that Python is installed and available in PATH.
)
pause
