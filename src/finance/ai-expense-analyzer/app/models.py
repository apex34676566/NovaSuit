"""
Modelos de base de datos para el analizador de gastos IA
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()


class ExpenseAnalysis(Base):
    """Análisis de gastos generado por IA"""
    __tablename__ = "expense_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    firefly_transaction_id = Column(Integer, index=True)
    category = Column(String(100))
    amount = Column(Float)
    analysis_date = Column(DateTime, default=datetime.utcnow)
    
    # Análisis IA
    ai_category = Column(String(100))
    risk_score = Column(Float)  # 0-1
    anomaly_detected = Column(Boolean, default=False)
    confidence_score = Column(Float)  # 0-1
    
    # Insights y recomendaciones
    insights = Column(JSON)  # Lista de insights
    recommendations = Column(JSON)  # Lista de recomendaciones
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SavingsProjection(Base):
    """Proyecciones de ahorro mensuales"""
    __tablename__ = "savings_projections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    month = Column(Integer)  # 1-12
    year = Column(Integer)
    
    # Proyecciones
    projected_savings = Column(Float)
    actual_savings = Column(Float, nullable=True)
    projected_expenses = Column(Float)
    actual_expenses = Column(Float, nullable=True)
    
    # Categorías de gastos proyectadas
    category_projections = Column(JSON)
    
    # Estado
    is_current_month = Column(Boolean, default=False)
    confidence_score = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChatbotInteraction(Base):
    """Interacciones del chatbot financiero"""
    __tablename__ = "chatbot_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    session_id = Column(String(100), index=True)
    
    # Mensaje
    user_message = Column(Text)
    bot_response = Column(Text)
    intent = Column(String(100))  # query_expenses, savings_advice, etc.
    
    # Contexto
    context_data = Column(JSON)  # Datos relevantes para la respuesta
    
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAlert(Base):
    """Alertas de riesgo financiero"""
    __tablename__ = "risk_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    
    # Alerta
    alert_type = Column(String(50))  # overspending, unusual_pattern, budget_risk
    severity = Column(String(20))  # low, medium, high, critical
    title = Column(String(200))
    description = Column(Text)
    
    # Datos relacionados
    related_transactions = Column(JSON)
    suggested_actions = Column(JSON)
    
    # Estado
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# Modelos Pydantic para API

class ExpenseAnalysisResponse(BaseModel):
    """Respuesta del análisis de gastos"""
    id: int
    category: str
    amount: float
    ai_category: str
    risk_score: float
    anomaly_detected: bool
    confidence_score: float
    insights: list
    recommendations: list
    analysis_date: datetime
    
    class Config:
        from_attributes = True


class SavingsProjectionResponse(BaseModel):
    """Respuesta de proyección de ahorros"""
    id: int
    month: int
    year: int
    projected_savings: float
    actual_savings: Optional[float]
    projected_expenses: float
    actual_expenses: Optional[float]
    category_projections: dict
    confidence_score: float
    
    class Config:
        from_attributes = True


class ChatbotMessage(BaseModel):
    """Mensaje del chatbot"""
    message: str
    session_id: Optional[str] = None


class ChatbotResponse(BaseModel):
    """Respuesta del chatbot"""
    response: str
    intent: str
    session_id: str
    context_data: Optional[dict] = None


class RiskAlertResponse(BaseModel):
    """Respuesta de alerta de riesgo"""
    id: int
    alert_type: str
    severity: str
    title: str
    description: str
    suggested_actions: list
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True