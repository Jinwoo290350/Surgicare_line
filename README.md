# 🏥 Wound Classifier LINE Bot

An AI-powered LINE Bot for wound classification and care recommendations using advanced machine learning models.

## 🌟 Features

- **🔍 AI Wound Classification**: Uses ONNX optimized model for accurate wound type detection
- **🧠 Smart Feature Extraction**: BiomedVLP-BioViL-T model for detailed wound analysis
- **💬 Thai Language Support**: Full support for Thai language interactions
- **🚀 Real-time Analysis**: Fast inference with GPU acceleration
- **📱 LINE Integration**: Seamless LINE Bot experience
- **🎯 Medical Recommendations**: AI-generated care advice via Typhoon API

## 🎯 Supported Wound Types

- **แผลถลอก (Abrasions)**: Superficial skin wounds
- **รอยช้ำ (Bruises)**: Contusions and hematomas  
- **แผลไฟไหม้ (Burns)**: Thermal injuries
- **แผลบาด (Cuts)**: Lacerations and incisions
- **ผิวหนังปกติ (Normal)**: Healthy skin

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- LINE Developer Account
- Typhoon API Key
- Ngrok Account (for local development)

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd wound-classifier-linebot
```

### 2. Setup Environment

```bash
# Create virtual environment
python -m venv wound-classifier-env
source wound-classifier-env/bin/activate  # On Windows: wound-classifier-env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required Environment Variables:**
```bash
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_access_token
TYPHOON_API_KEY=your_typhoon_api_key
NGROK_AUTH_TOKEN=your_ngrok_auth_token
```

### 4. Start Development Server

```bash
# Make script executable
chmod +x scripts/start_dev.sh

# Start development environment
./scripts/start_dev.sh
```

This will automatically:
- Start Flask application
- Create ngrok tunnel
- Update LINE Bot webhook URL
- Display connection information

## 📋 API Endpoints

- `POST /callback` - LINE Bot webhook
- `GET /health` - Health check endpoint

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LINE App      │───▶│   Flask App      │───▶│   AI Models     │
│                 │    │                  │    │                 │
│ - User Messages │    │ - Image Process  │    │ - ONNX Model    │
│ - Image Upload  │    │ - Wound Analysis │    │ - BiomedVLP     │
│ - Responses     │    │ - Recommendations│    │ - Typhoon API   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🔧 Configuration

### Model Settings
```bash
# GPU/CPU configuration
USE_CUDA=True
USE_FP16_QUANTIZATION=True

# Model cache
MODEL_CACHE_DIR=./models
MODEL_DOWNLOAD_TIMEOUT=300
```

### Image Processing
```bash
# Image constraints
MAX_IMAGE_SIZE=10485760  # 10MB
IMAGE_RESIZE_MAX_WIDTH=1024
IMAGE_RESIZE_MAX_HEIGHT=1024
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png,bmp,webp
```

### Feature Extraction
```bash
# Language and similarity
FEATURE_EXTRACTION_LANG=th
SIMILARITY_THRESHOLD=0.3
MAX_FEATURES=10
```

## 🧪 Testing

```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=.

# Test specific component
python -m pytest tests/test_wound_classifier.py
```

## 📊 Monitoring

### Logs
- Application logs: `./logs/wound_classifier.log`
- Console output for development

### Analytics
- User interactions stored in SQLite
- Prediction statistics and performance metrics

### Ngrok Dashboard
- Traffic monitoring: http://localhost:4040

## 🛠️ Development

### Project Structure
```
wound-classifier-linebot/
├── app.py                    # Main Flask application
├── models.py                 # Pydantic data models
├── typhoon_client.py         # AI recommendations
├── config.py                 # Configuration management
├── utils/                    # Core utilities
│   ├── extract_wound_class.py   # ONNX classification
│   ├── extract_wound_features.py # Feature extraction
│   └── image_utils.py           # Image processing
├── services/                 # Business logic
├── templates/                # Message templates
└── tests/                    # Test suite
```

### Adding New Features

1. **New Wound Types**: Update `CLASS_LABELS` in model files
2. **Language Support**: Add translations in feature extraction
3. **Custom Models**: Modify model loading in utils

### Code Quality
```bash
# Format code
black .

# Lint code  
flake8 .

# Type checking
mypy .
```

## 🚀 Deployment

### Local Development
```bash
./scripts/start_dev.sh
```

### Production Deployment
1. Set `FLASK_ENV=production`
2. Configure production database
3. Set up proper SSL certificates
4. Use production WSGI server (gunicorn)

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

## 🔒 Security

- Input validation with Pydantic
- Image file validation and sanitization
- Rate limiting per user
- CORS configuration
- Secure environment variable handling

## 📈 Performance

- **ONNX Runtime**: Optimized model inference
- **GPU Acceleration**: CUDA support with FP16 quantization
- **Caching**: Model and feature caching
- **Image Optimization**: Smart resizing and preprocessing

## 🐛 Troubleshooting

### Common Issues

1. **Model Download Fails**
   ```bash
   # Check internet connection and increase timeout
   MODEL_DOWNLOAD_TIMEOUT=600
   ```

2. **GPU Not Detected**
   ```bash
   # Install CUDA version of PyTorch
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

3. **Ngrok Connection Issues**
   ```bash
   # Check auth token and region
   NGROK_REGION=ap  # For Asia Pacific
   ```

4. **LINE Webhook Errors**
   - Verify channel secret and access token
   - Check webhook URL is accessible
   - Ensure HTTPS is enabled

### Debug Mode
```bash
FLASK_DEBUG=True
LOG_LEVEL=DEBUG
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

- Create an issue for bug reports
- Join our Discord for community support
- Check documentation in `/docs` folder

## ⚠️ Medical Disclaimer

This tool is for educational and informational purposes only. It should not be used as a substitute for professional medical advice, diagnosis, or treatment. Always consult with qualified healthcare providers for medical concerns.

---

Made with ❤️ for healthcare innovation