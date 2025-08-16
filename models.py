from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime
import json

class WoundClassificationResult(BaseModel):
    """Pydantic model for wound classification results"""
    predicted_class: str = Field(..., description="Predicted wound class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    probabilities: Dict[str, float] = Field(..., description="Probabilities for all classes")
    features: List[str] = Field(default_factory=list, description="Extracted features")
    
    @validator('predicted_class')
    def validate_class(cls, v):
        valid_classes = ['Abrasions', 'Bruises', 'Burns', 'Cut', 'Normal']
        if v not in valid_classes:
            raise ValueError(f'predicted_class must be one of {valid_classes}')
        return v
    
    @validator('probabilities')
    def validate_probabilities(cls, v):
        valid_classes = ['Abrasions', 'Bruises', 'Burns', 'Cut', 'Normal']
        for class_name in valid_classes:
            if class_name not in v:
                raise ValueError(f'Missing probability for class {class_name}')
            if not 0.0 <= v[class_name] <= 1.0:
                raise ValueError(f'Probability for {class_name} must be between 0 and 1')
        return v

class WoundAnalysisRequest(BaseModel):
    """Pydantic model for wound analysis request"""
    user_id: str = Field(..., description="LINE user ID")
    image_path: str = Field(..., description="Path to the image file")
    timestamp: datetime = Field(default_factory=datetime.now, description="Request timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('user_id cannot be empty')
        return v.strip()
    
    @validator('image_path')
    def validate_image_path(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('image_path cannot be empty')
        return v.strip()

class WoundAnalysisResponse(BaseModel):
    """Pydantic model for wound analysis response"""
    request: WoundAnalysisRequest = Field(..., description="Original request")
    classification: Optional[WoundClassificationResult] = Field(None, description="Classification results")
    recommendations: str = Field(..., description="Treatment recommendations")
    success: bool = Field(..., description="Whether analysis was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    
    @validator('recommendations')
    def validate_recommendations(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('recommendations cannot be empty')
        return v.strip()

class TyphoonAPIRequest(BaseModel):
    """Pydantic model for Typhoon API requests"""
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    model: str = Field(default="typhoon-v1.5x-70b-instruct", description="Model to use")
    max_tokens: int = Field(default=512, ge=1, le=4096, description="Maximum tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    top_p: float = Field(default=0.95, ge=0.0, le=1.0, description="Top-p sampling")
    stream: bool = Field(default=False, description="Stream response")
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError('messages cannot be empty')
        
        for msg in v:
            if 'role' not in msg or 'content' not in msg:
                raise ValueError('Each message must have role and content')
            if msg['role'] not in ['system', 'user', 'assistant']:
                raise ValueError('Role must be system, user, or assistant')
        
        return v

class TyphoonAPIResponse(BaseModel):
    """Pydantic model for Typhoon API responses"""
    id: str = Field(..., description="Response ID")
    object: str = Field(..., description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Dict[str, int] = Field(..., description="Token usage")
    
    @validator('choices')
    def validate_choices(cls, v):
        if not v:
            raise ValueError('choices cannot be empty')
        return v

class WoundFeature(BaseModel):
    """Pydantic model for individual wound features"""
    description: str = Field(..., description="Feature description")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Feature confidence")
    language: str = Field(default="en", description="Language of description")
    
    @validator('description')
    def validate_description(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('description cannot be empty')
        return v.strip()
    
    @validator('language')
    def validate_language(cls, v):
        valid_languages = ['en', 'th']
        if v not in valid_languages:
            raise ValueError(f'language must be one of {valid_languages}')
        return v

class UserSession(BaseModel):
    """Pydantic model for user session data"""
    user_id: str = Field(..., description="LINE user ID")
    session_start: datetime = Field(default_factory=datetime.now, description="Session start time")
    last_activity: datetime = Field(default_factory=datetime.now, description="Last activity time")
    analysis_count: int = Field(default=0, ge=0, description="Number of analyses in session")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('user_id cannot be empty')
        return v.strip()
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    def increment_analysis_count(self):
        """Increment analysis count"""
        self.analysis_count += 1
        self.update_activity()

class AnalyticsEvent(BaseModel):
    """Pydantic model for analytics events"""
    event_type: str = Field(..., description="Type of event")
    user_id: str = Field(..., description="LINE user ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    session_id: Optional[str] = Field(None, description="Session ID")
    
    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = [
            'user_message', 'image_received', 'analysis_started', 
            'analysis_completed', 'analysis_failed', 'session_started',
            'session_ended', 'error_occurred'
        ]
        if v not in valid_types:
            raise ValueError(f'event_type must be one of {valid_types}')
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('user_id cannot be empty')
        return v.strip()

class SystemHealth(BaseModel):
    """Pydantic model for system health status"""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")
    components: Dict[str, str] = Field(default_factory=dict, description="Component statuses")
    uptime: Optional[float] = Field(None, description="System uptime in seconds")
    memory_usage: Optional[float] = Field(None, description="Memory usage percentage")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ['healthy', 'degraded', 'unhealthy']
        if v not in valid_statuses:
            raise ValueError(f'status must be one of {valid_statuses}')
        return v

# Export all models
__all__ = [
    'WoundClassificationResult',
    'WoundAnalysisRequest', 
    'WoundAnalysisResponse',
    'TyphoonAPIRequest',
    'TyphoonAPIResponse',
    'WoundFeature',
    'UserSession',
    'AnalyticsEvent',
    'SystemHealth'
]