"""
Configuración de la aplicación
"""
import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # OpenAI Configuration
    openai_api_key: str
    ai_model: str = "gpt-3.5-turbo"
    max_tokens: int = 1000
    temperature: float = 0.7
    
    # Database Configuration
    database_url: str
    
    # Firefly III Integration
    firefly_iii_url: str
    firefly_iii_token: str
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # Application Settings
    secret_key: str
    debug: bool = True
    log_level: str = "INFO"
    
    # Analysis Settings
    analysis_schedule_hours: int = 24
    risk_threshold: float = 0.8
    savings_target_percentage: int = 20
    
    # CORS Settings
    allowed_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instancia global de configuración
settings = Settings()