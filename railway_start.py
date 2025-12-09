import os
import subprocess
import sys

def install_system_dependencies():
    """Install system dependencies needed for OCR"""
    try:
        # Install Tesseract OCR and Poppler
        subprocess.run([
            "apt-get", "update"
        ], check=False)
        
        subprocess.run([
            "apt-get", "install", "-y", 
            "tesseract-ocr",
            "poppler-utils",
            "libsm6",
            "libxext6",
            "libxrender-dev",
            "libgl1-mesa-glx"
        ], check=False)
        print("✅ System dependencies installed")
    except Exception as e:
        print(f"⚠️ Could not install system dependencies: {e}")
        print("ℹ️ Continuing without them...")

def main():
    # Install system dependencies if not already installed
    install_system_dependencies()
    
    # Install Python packages
    print("📦 Installing Python packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Start the app
    print("🚀 Starting application...")
    from server_app import create_simple_interface
    
    app = create_simple_interface()
    
    port = int(os.environ.get("PORT", 7860))
    
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False
    )

if __name__ == "__main__":
    main()