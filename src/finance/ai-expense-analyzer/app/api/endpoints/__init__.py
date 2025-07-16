"""
Endpoints de la API del analizador de gastos IA
"""

from .analysis import router as analysis_router
from .chatbot import router as chatbot_router

__all__ = [
    "analysis_router",
    "chatbot_router"
]