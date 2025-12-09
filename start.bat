# ============================================
# WINDOWS STARTUP SCRIPT (start.bat)
# ============================================
# Save this as: start.bat

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

# ============================================
# LINUX/MAC STARTUP SCRIPT (start.sh)
# ============================================
# Save this as: start.sh
# Make executable: chmod +x start.sh

#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}CV SUMMARY GENERATOR - STARTING...${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR] Virtual environment not found!${NC}"
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${GREEN}[INFO] Activating virtual environment...${NC}"
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[WARNING] .env file not found!${NC}"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}[ACTION REQUIRED] Please edit .env file and add your Gemini API key!${NC}"
    echo "Opening .env file in nano editor..."
    sleep 2
    nano .env
fi

# Check if dependencies are installed
echo -e "${GREEN}[INFO] Checking dependencies...${NC}"
python -c "import gradio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[WARNING] Dependencies not installed!${NC}"
    echo "Installing from requirements.txt..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install dependencies${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Dependencies installed${NC}"
fi

# Check Tesseract installation
if ! command -v tesseract &> /dev/null; then
    echo -e "${YELLOW}[WARNING] Tesseract OCR not found!${NC}"
    echo "Please install Tesseract:"
    echo "  Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-ind"
    echo "  Mac: brew install tesseract tesseract-lang"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create output directories
mkdir -p output/temp

# Clear screen and show info
clear
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}CV SUMMARY GENERATOR${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}[INFO] Application starting...${NC}"
echo ""
echo -e "${YELLOW}Web Interface will open automatically in your browser${NC}"
echo -e "${YELLOW}URL: http://localhost:7860${NC}"
echo ""
echo -e "${RED}To stop the application: Press Ctrl+C${NC}"
echo ""
echo -e "${BLUE}============================================${NC}"
echo ""

# Run application
python app_local.py

# If app exits
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Application stopped.${NC}"
echo -e "${BLUE}============================================${NC}"

# ============================================
# QUICK START SCRIPT (quickstart.bat for Windows)
# ============================================
# Save as: quickstart.bat

@echo off
cls
echo ============================================
echo CV SUMMARY GENERATOR - QUICK START
echo ============================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10 or higher from https://www.python.org/
    pause
    exit /b 1
)

REM Check if setup is needed
if not exist "venv\" (
    echo [INFO] First time setup...
    echo.
    
    echo [1/4] Creating virtual environment...
    python -m venv venv
    
    echo [2/4] Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo [3/4] Installing dependencies...
    pip install -r requirements.txt
    
    echo [4/4] Creating .env file...
    copy .env.example .env
    
    echo.
    echo ============================================
    echo SETUP COMPLETE!
    echo ============================================
    echo.
    echo NEXT STEPS:
    echo 1. Edit .env file and add your Gemini API key
    echo 2. Install Tesseract OCR from:
    echo    https://github.com/UB-Mannheim/tesseract/wiki
    echo 3. Run this script again to start the application
    echo.
    pause
    exit /b 0
)

REM Start application
call start.bat

# ============================================
# QUICK START SCRIPT (quickstart.sh for Linux/Mac)
# ============================================
# Save as: quickstart.sh
# Make executable: chmod +x quickstart.sh

#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}CV SUMMARY GENERATOR - QUICK START${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found!${NC}"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

# Check if setup is needed
if [ ! -d "venv" ]; then
    echo -e "${GREEN}[INFO] First time setup...${NC}"
    echo ""
    
    echo -e "${YELLOW}[1/5] Creating virtual environment...${NC}"
    python3 -m venv venv
    
    echo -e "${YELLOW}[2/5] Activating virtual environment...${NC}"
    source venv/bin/activate
    
    echo -e "${YELLOW}[3/5] Upgrading pip...${NC}"
    pip install --upgrade pip
    
    echo -e "${YELLOW}[4/5] Installing dependencies...${NC}"
    pip install -r requirements.txt
    
    echo -e "${YELLOW}[5/5] Creating .env file...${NC}"
    cp .env.example .env
    
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}SETUP COMPLETE!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "${YELLOW}NEXT STEPS:${NC}"
    echo "1. Edit .env file and add your Gemini API key:"
    echo "   nano .env"
    echo ""
    echo "2. Install Tesseract OCR:"
    echo "   Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-ind"
    echo "   Mac: brew install tesseract tesseract-lang"
    echo ""
    echo "3. Run this script again to start the application"
    echo ""
    exit 0
fi

# Start application
./start.sh