"""
Configuration management for wound classifier LINE bot
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import BaseSettings, Field, validator
from pathlib import Path

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # LINE Bot Configuration
    line_channel_secret: str = Field(..., env='LINE_CHANNEL_SECRET')
    line_channel_access_token: str = Field(..., env='LINE_CHANNEL_ACCESS_TOKEN')
    
    # Typhoon API Configuration
    typhoon_api_key: str = Field(..., env='TYPHOON_API_KEY')
    typhoon_base_url: str = Field('https://api.opentyphoon.ai/v1', env='TYPHOON_BASE_URL')
    
    # Flask Configuration
    flask_env: str = Field('development', env='FLASK_ENV')
    flask_debug: bool = Field(True, env='FLASK_DEBUG')
    secret_key: str = Field('your-secret-key-change-in-production', env='SECRET_KEY')
    
    # Server Configuration
    host: str = Field('0.0.0.0', env='HOST')
    port: int = Field(5000, env='PORT')
    
    # Ngrok Configuration
    ngrok_auth_token: Optional[str] = Field(None, env='NGROK_AUTH_TOKEN')
    ngrok_region: str = Field('ap', env='NGROK_REGION')
    ngrok_subdomain: Optional[str] = Field(None, env='NGROK_SUBDOMAIN')
    
    # Model Configuration
    model_cache_dir: str = Field('/tmp/wound_classifier_models', env='MODEL_CACHE_DIR')
    use_cuda: bool = Field(True, env='USE_CUDA')
    use_fp16_quantization: bool = Field(True, env='USE_FP16_QUANTIZATION')
    model_download_timeout: int = Field(300, env='MODEL_DOWNLOAD_TIMEOUT')
    
    # Feature Extraction Configuration
    biomedvlp_model_name: str = Field('microsoft/BiomedVLP-BioViL-T', env='BIOMEDVLP_MODEL_NAME')
    feature_extraction_lang: str = Field('th', env='FEATURE_EXTRACTION_LANG')
    similarity_threshold: float = Field(0.3, env='SIMILARITY_THRESHOLD')
    max_features: int = Field(10, env='MAX_FEATURES')
    
    # Caching Configuration
    redis_url: Optional[str] = Field(None, env='REDIS_URL')
    cache_ttl: int = Field(3600, env='CACHE_TTL')
    use_disk_cache: bool = Field(True, env='USE_DISK_CACHE')
    disk_cache_dir: str = Field('/tmp/wound_classifier_cache', env='DISK_CACHE_DIR')
    
    # Logging Configuration
    log_level: str = Field('INFO', env='LOG_LEVEL')
    log_format: str = Field('%(asctime)s - %(name)s - %(levelname)s - %(message)s', env='LOG_FORMAT')
    log_file: Optional[str] = Field('/tmp/wound_classifier.log', env='LOG_FILE')
    enable_file_logging: bool = Field(True, env='ENABLE_FILE_LOGGING')
    
    # Analytics Configuration
    enable_analytics: bool = Field(True, env='ENABLE_ANALYTICS')
    analytics_db_url: str = Field('sqlite:///analytics.db', env='ANALYTICS_DB_URL')
    
    # Rate Limiting
    rate_limit_per_user: int = Field(10, env='RATE_LIMIT_PER_USER')
    rate_limit_window: int = Field(60, env='RATE_LIMIT_WINDOW')
    
    # Image Processing Configuration
    max_image_size: int = Field(10485760, env='MAX_IMAGE_SIZE')  # 10MB
    allowed_image_formats: str = Field('jpg,jpeg,png,bmp,webp', env='ALLOWED_IMAGE_FORMATS')
    image_resize_max_width: int = Field(1024, env='IMAGE_RESIZE_MAX_WIDTH')
    image_resize_max_height: int = Field(1024, env='IMAGE_RESIZE_MAX_HEIGHT')
    
    # Development Configuration
    development_mode: bool = Field(True, env='DEVELOPMENT_MODE')
    mock_typhoon_api: bool = Field(False, env='MOCK_TYPHOON_API')
    mock_model_inference: bool = Field(False, env='MOCK_MODEL_INFERENCE')
    
    # Security Configuration
    allowed_origins: str = Field('*', env='ALLOWED_ORIGINS')
    cors_enabled: bool = Field(True, env='CORS_ENABLED')
    
    # Monitoring Configuration
    enable_metrics: bool = Field(False, env='ENABLE_METRICS')
    metrics_port: int = Field(9090, env='METRICS_PORT')
    
    # Optional: Sentry Configuration
    sentry_dsn: Optional[str] = Field(None, env='SENTRY_DSN')
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()
    
    @validator('feature_extraction_lang')
    def validate_language(cls, v):
        valid_langs = ['en', 'th']
        if v not in valid_langs:
            raise ValueError(f'feature_extraction_lang must be one of {valid_langs}')
        return v
    
    @validator('similarity_threshold')
    def validate_similarity_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('similarity_threshold must be between 0.0 and 1.0')
        return v
    
    @validator('allowed_image_formats')
    def validate_image_formats(cls, v):
        formats = [f.strip().lower() for f in v.split(',')]
        valid_formats = {'jpg', 'jpeg', 'png', 'bmp', 'webp', 'tiff', 'tif'}
        for fmt in formats:
            if fmt not in valid_formats:
                raise ValueError(f'Invalid image format: {fmt}')
        return v
    
    @property
    def allowed_image_formats_list(self) -> List[str]:
        """Get allowed image formats as a list"""
        return [f.strip().lower() for f in self.allowed_image_formats.split(',')]
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list"""
        if self.allowed_origins == '*':
            return ['*']
        return [origin.strip() for origin in self.allowed_origins.split(',')]
    
    def create_directories(self):
        """Create necessary directories"""
        directories = [
            self.model_cache_dir,
            self.disk_cache_dir,
            Path(self.log_file).parent if self.log_file else None
        ]
        
        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False


class DevelopmentSettings(Settings):
    """Development-specific settings"""
    flask_env: str = 'development'
    flask_debug: bool = True
    development_mode: bool = True
    log_level: str = 'DEBUG'
    enable_analytics: bool = False
    enable_metrics: bool = False


class ProductionSettings(Settings):
    """Production-specific settings"""
    flask_env: str = 'production'
    flask_debug: bool = False
    development_mode: bool = False
    log_level: str = 'INFO'
    enable_analytics: bool = True
    enable_metrics: bool = True
    
    @validator('secret_key')
    def validate_secret_key_in_production(cls, v):
        if v == 'your-secret-key-change-in-production':
            raise ValueError('SECRET_KEY must be changed in production')
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        return v


class TestSettings(Settings):
    """Test-specific settings"""
    flask_env: str = 'testing'
    flask_debug: bool = False
    development_mode: bool = True
    log_level: str = 'ERROR'
    enable_analytics: bool = False
    enable_metrics: bool = False
    mock_typhoon_api: bool = True
    mock_model_inference: bool = True


def get_settings(env: Optional[str] = None) -> Settings:
    """
    Get settings based on environment
    
    Args:
        env: Environment name ('development', 'production', 'testing')
        
    Returns:
        Settings instance
    """
    env = env or os.getenv('FLASK_ENV', 'development')
    
    if env == 'production':
        return ProductionSettings()
    elif env == 'testing':
        return TestSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()

# Create necessary directories
settings.create_directories()


# Configuration for different components
class ModelConfig:
    """Model-specific configuration"""
    
    @staticmethod
    def get_wound_classifier_config() -> Dict[str, Any]:
        """Get wound classifier configuration"""
        return {
            'cache_dir': settings.model_cache_dir,
            'use_fp16': settings.use_fp16_quantization,
            'device': 'cuda' if settings.use_cuda else 'cpu',
            'enable_optimization': True
        }
    
    @staticmethod
    def get_feature_extractor_config() -> Dict[str, Any]:
        """Get feature extractor configuration"""
        return {
            'device': 'cuda' if settings.use_cuda else 'cpu',
            'cache_dir': settings.disk_cache_dir,
            'enable_caching': settings.use_disk_cache
        }


class APIConfig:
    """API-specific configuration"""
    
    @staticmethod
    def get_typhoon_config() -> Dict[str, Any]:
        """Get Typhoon API configuration"""
        return {
            'api_key': settings.typhoon_api_key,
            'base_url': settings.typhoon_base_url
        }
    
    @staticmethod
    def get_line_config() -> Dict[str, str]:
        """Get LINE Bot configuration"""
        return {
            'channel_secret': settings.line_channel_secret,
            'channel_access_token': settings.line_channel_access_token
        }


class CacheConfig:
    """Cache-specific configuration"""
    
    @staticmethod
    def get_redis_config() -> Optional[Dict[str, Any]]:
        """Get Redis configuration"""
        if not settings.redis_url:
            return None
        
        return {
            'url': settings.redis_url,
            'ttl': settings.cache_ttl
        }
    
    @staticmethod
    def get_disk_cache_config() -> Dict[str, Any]:
        """Get disk cache configuration"""
        return {
            'directory': settings.disk_cache_dir,
            'size_limit': 1024 * 1024 * 1024,  # 1GB
            'ttl': settings.cache_ttl
        }


# Export commonly used configurations
__all__ = [
    'settings',
    'get_settings',
    'ModelConfig',
    'APIConfig', 
    'CacheConfig',
    'DevelopmentSettings',
    'ProductionSettings',
    'TestSettings'
]