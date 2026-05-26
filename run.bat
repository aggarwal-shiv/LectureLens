@echo off
:: ─────────────────────────────────────────────────────────────────
:: LectureLens — Windows launcher
:: Author : Shivam Aggarwal  |  github.com/aggarwal-shiv
:: ─────────────────────────────────────────────────────────────────

title LectureLens

:: Find python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found.
    echo  Install Python 3.9+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo  LectureLens -- checking dependencies...
python -c "import cv2, PIL, numpy" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  First run: installing dependencies...
    python "%~dp0LectureLens.py" --install
    echo.
)

echo  Launching LectureLens...
python "%~dp0LectureLens.py"
if %errorlevel% neq 0 (
    echo.
    echo  Something went wrong. Try running:
    echo    python LectureLens.py --install
    echo.
    pause
)
