#!/bin/bash

# Development startup script for Wound Classifier LINE Bot
set -e

echo "🚀 Starting Wound Classifier LINE Bot Development Environment"
echo "============================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d "wound-classifier-env" ]; then
    print_header "📦 Creating virtual environment..."
    python3 -m venv wound-classifier-env
    print_status "Virtual environment created: wound-classifier-env"
fi

# Activate virtual environment
print_header "🔄 Activating virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    print_status "Virtual environment activated: venv"
elif [ -d "wound-classifier-env" ]; then
    source wound-classifier-env/bin/activate
    print_status "Virtual environment activated: wound-classifier-env"
else
    print_error "No virtual environment found!"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_header "📋 Creating .env file from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your API keys and tokens"
        print_warning "Required variables:"
        echo "  - LINE_CHANNEL_SECRET"
        echo "  - LINE_CHANNEL_ACCESS_TOKEN" 
        echo "  - TYPHOON_API_KEY"
        echo "  - NGROK_AUTH_TOKEN"
        echo ""
        read -p "Press Enter after updating .env file..."
    else
        print_error ".env file not found and no .env.example template available"
        exit 1
    fi
fi

# Load environment variables
print_header "⚙️  Loading environment variables..."
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    print_status "Environment variables loaded"
else
    print_error ".env file not found"
    exit 1
fi

# Check required environment variables
print_header "🔍 Checking required environment variables..."
missing_vars=()

if [ -z "$LINE_CHANNEL_SECRET" ]; then
    missing_vars+=("LINE_CHANNEL_SECRET")
fi

if [ -z "$LINE_CHANNEL_ACCESS_TOKEN" ]; then
    missing_vars+=("LINE_CHANNEL_ACCESS_TOKEN")
fi

if [ -z "$TYPHOON_API_KEY" ]; then
    missing_vars+=("TYPHOON_API_KEY")
fi

if [ -z "$NGROK_AUTH_TOKEN" ]; then
    missing_vars+=("NGROK_AUTH_TOKEN")
fi

if [ ${#missing_vars[@]} -ne 0 ]; then
    print_error "Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

print_status "All required environment variables are set"

# Install/upgrade pip
print_header "📦 Updating pip..."
python -m pip install --upgrade pip

# Install requirements
print_header "📦 Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Requirements installed successfully"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Create necessary directories
print_header "📁 Creating necessary directories..."
mkdir -p logs temp uploads models cache
print_status "Directories created"

# Check if models need to be downloaded
print_header "🤖 Checking model availability..."
print_status "Models will be downloaded automatically when first needed"

# Start the development server
print_header "🌟 Starting development servers..."

# Function to cleanup background processes
cleanup() {
    print_header "🛑 Shutting down servers..."
    if [ ! -z "$FLASK_PID" ]; then
        kill $FLASK_PID 2>/dev/null || true
    fi
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
    fi
    print_status "Servers stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Start Flask app in background
print_status "Starting Flask application..."
python app.py &
FLASK_PID=$!

# Wait a moment for Flask to start
sleep 3

# Check if Flask started successfully
if ! kill -0 $FLASK_PID 2>/dev/null; then
    print_error "Flask application failed to start"
    exit 1
fi

print_status "Flask application started (PID: $FLASK_PID)"
print_status "Flask server: http://localhost:${PORT:-5000}"

# Start ngrok tunnel
print_status "Starting ngrok tunnel..."
python run_ngrok.py &
NGROK_PID=$!

# Wait a moment for ngrok to start
sleep 5

# Check if ngrok started successfully
if ! kill -0 $NGROK_PID 2>/dev/null; then
    print_error "Ngrok failed to start"
    kill $FLASK_PID 2>/dev/null || true
    exit 1
fi

print_status "Ngrok tunnel started (PID: $NGROK_PID)"

# Show useful information
print_header "🎉 Development environment is ready!"
echo ""
echo "📱 LINE Bot Endpoints:"
echo "  - Webhook: (will be set by ngrok automatically)"
echo "  - Health Check: (public_url)/health"
echo ""
echo "🔧 Development Tools:"
echo "  - Flask Dev Server: http://localhost:${PORT:-5000}"
echo "  - Ngrok Web Interface: http://localhost:4040"
echo ""
echo "📊 Monitoring:"
echo "  - Logs: Check terminal output"
echo "  - Analytics: ${ANALYTICS_DB_URL:-sqlite:///analytics.db}"
echo ""
echo "🔄 To restart:"
echo "  - Press Ctrl+C to stop all services"
echo "  - Run './scripts/start_dev.sh' again"
echo ""
print_warning "Keep this terminal open to maintain the development environment"
print_status "Press Ctrl+C to stop all services"

# Wait for user interruption
wait