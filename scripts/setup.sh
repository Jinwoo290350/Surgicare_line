#!/bin/bash

# Setup script for Wound Classifier LINE Bot
set -e

echo "🔧 Setting up Wound Classifier LINE Bot"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Check Python version
print_header "🐍 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_version="3.8"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    print_status "Python $python_version is supported"
else
    print_error "Python 3.8+ is required, found $python_version"
    exit 1
fi

# Create virtual environment
print_header "📦 Creating virtual environment..."
if [ ! -d "wound-classifier-env" ]; then
    python3 -m venv wound-classifier-env
    print_status "Virtual environment created: wound-classifier-env"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_header "🔄 Activating virtual environment..."
source wound-classifier-env/bin/activate
print_status "Virtual environment activated"

# Upgrade pip
print_header "⬆️ Upgrading pip..."
python -m pip install --upgrade pip
print_status "Pip upgraded"

# Install requirements
print_header "📦 Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Requirements installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Create .env file if it doesn't exist
print_header "⚙️ Setting up environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status ".env file created from template"
        print_warning "Please edit .env file with your API keys:"
        echo "  - LINE_CHANNEL_SECRET"
        echo "  - LINE_CHANNEL_ACCESS_TOKEN"
        echo "  - TYPHOON_API_KEY"
        echo "  - NGROK_AUTH_TOKEN"
    else
        print_error ".env.example template not found"
        exit 1
    fi
else
    print_status ".env file already exists"
fi

# Create necessary directories
print_header "📁 Creating project directories..."
directories=("logs" "temp" "uploads" "models" "cache" "tests" "docs")

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_status "Created directory: $dir"
    fi
done

# Create __init__.py files
print_header "📄 Creating __init__.py files..."
init_files=("utils/__init__.py" "services/__init__.py" "templates/__init__.py" "tests/__init__.py")

for init_file in "${init_files[@]}"; do
    if [ ! -f "$init_file" ]; then
        touch "$init_file"
        print_status "Created: $init_file"
    fi
done

# Make scripts executable
print_header "🔐 Setting script permissions..."
if [ -f "scripts/start_dev.sh" ]; then
    chmod +x scripts/start_dev.sh
    print_status "Made start_dev.sh executable"
fi

if [ -f "scripts/deploy.sh" ]; then
    chmod +x scripts/deploy.sh
    print_status "Made deploy.sh executable"
fi

# Check GPU availability
print_header "🎮 Checking GPU availability..."
if python -c "import torch; print('CUDA available:', torch.cuda.is_available())" 2>/dev/null; then
    print_status "PyTorch installed and GPU check completed"
else
    print_warning "Unable to check GPU availability"
fi

# Test imports
print_header "🧪 Testing key imports..."
test_imports() {
    python -c "
import sys
try:
    import flask
    print('✓ Flask')
    import torch
    print('✓ PyTorch')
    import transformers
    print('✓ Transformers')
    import onnxruntime
    print('✓ ONNX Runtime')
    import pydantic
    print('✓ Pydantic')
    import requests
    print('✓ Requests')
    import PIL
    print('✓ Pillow')
    import cv2
    print('✓ OpenCV')
    import pyngrok
    print('✓ PyNgrok')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
print('All key imports successful!')
"
}

if test_imports; then
    print_status "All required packages imported successfully"
else
    print_error "Some packages failed to import"
    exit 1
fi

# Download models (optional)
print_header "🤖 Model setup..."
print_status "Models will be downloaded automatically when first needed"
print_status "To pre-download models, run the application once"

# Setup git hooks (optional)
print_header "📝 Git setup..."
if [ -d ".git" ]; then
    # Add .env to gitignore if not already there
    if [ -f ".gitignore" ] && ! grep -q "^\.env$" .gitignore; then
        echo ".env" >> .gitignore
        print_status "Added .env to .gitignore"
    fi
    print_status "Git repository detected"
else
    print_warning "Not a git repository - consider initializing git"
fi

# Final setup summary
print_header "✅ Setup Summary"
echo ""
echo "📋 Project Structure:"
echo "  ✓ Virtual environment: wound-classifier-env"
echo "  ✓ Dependencies installed"
echo "  ✓ Directories created"
echo "  ✓ Configuration template ready"
echo ""
echo "📝 Next Steps:"
echo "  1. Edit .env file with your API credentials"
echo "  2. Run: source wound-classifier-env/bin/activate"
echo "  3. Run: ./scripts/start_dev.sh"
echo ""
echo "🔑 Required API Keys:"
echo "  - LINE Developer Console: channel secret & access token"
echo "  - Typhoon API: API key"
echo "  - Ngrok: auth token"
echo ""
echo "📚 Documentation:"
echo "  - README.md: Complete setup guide"
echo "  - .env.example: Environment variable reference"
echo ""

print_status "Setup completed successfully! 🎉"
print_warning "Remember to configure your .env file before starting the application"