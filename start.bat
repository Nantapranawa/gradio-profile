@echo off
cls
echo ============================================
echo CV SUMMARY GENERATOR - STARTING...
echo ============================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup first: python -m venv venv
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Creating from .env.example...
    copy .env.example .env
    echo.
    echo [ACTION REQUIRED] Please edit .env file and add your Gemini API key!
    echo Press any key to open .env file...
    pause
    notepad .env
    echo.
    echo After saving .env, press any key to continue...
    pause
)

REM Check if dependencies are installed
echo [INFO] Checking dependencies...
python -c "import gradio" 2>nul
if errorlevel 1 (
    echo [WARNING] Dependencies not installed!
    echo Installing from requirements.txt...
    pip install -r requirements.txt
)

REM Create output directories
if not exist "output\" mkdir output
if not exist "output\temp\" mkdir output\temp

REM Clear screen and show info
cls
echo ============================================
echo CV SUMMARY GENERATOR
echo ============================================
echo.
echo [INFO] Application starting...
echo.
echo Web Interface will open automatically in your browser
echo URL: http://localhost:7860
echo.
echo To stop the application: Press Ctrl+C
echo.
echo ============================================
echo.

REM Run application
python app_local.py

REM If app exits, wait for user
echo.
echo ============================================
echo Application stopped.
echo ============================================
pause
