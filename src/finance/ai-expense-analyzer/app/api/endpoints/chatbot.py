"""
Endpoints para el chatbot financiero
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import json

from ...database import get_db
from ...models import ChatbotMessage, ChatbotResponse, ChatbotInteraction
from ...services import financial_chatbot

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class ConnectionManager:
    """Manejador de conexiones WebSocket"""
    
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_text(message)
            except:
                self.disconnect(user_id)
    
    async def send_proactive_message(self, user_id: int, trigger_type: str):
        """Enviar mensaje proactivo del chatbot"""
        if user_id in self.active_connections:
            message = await financial_chatbot.generate_proactive_message(user_id, trigger_type)
            if message:
                await self.send_personal_message(
                    json.dumps({
                        "type": "proactive_message",
                        "message": message,
                        "trigger": trigger_type
                    }),
                    user_id
                )


manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    """
    WebSocket para chat en tiempo real
    """
    await manager.connect(websocket, user_id)
    
    try:
        # Enviar mensaje de bienvenida
        welcome_message = {
            "type": "welcome",
            "message": f"¡Hola! 👋 Soy tu asistente financiero personal. ¿En qué puedo ayudarte hoy?",
            "suggested_questions": [
                "¿Cuánto he gastado este mes?",
                "Dame consejos para ahorrar",
                "¿Cómo van mis presupuestos?",
                "Muéstrame mi proyección de gastos"
            ]
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_message = message_data.get("message", "")
            session_id = message_data.get("session_id")
            
            if user_message:
                # Procesar mensaje con el chatbot
                response = await financial_chatbot.process_message(
                    user_id=user_id,
                    message=user_message,
                    session_id=session_id,
                    db=db
                )
                
                # Enviar respuesta
                await websocket.send_text(json.dumps({
                    "type": "response",
                    "message": response["response"],
                    "intent": response["intent"],
                    "session_id": response["session_id"],
                    "suggested_actions": response["suggested_actions"]
                }))
    
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        manager.disconnect(user_id)


@router.post("/message", response_model=ChatbotResponse)
async def send_message(
    user_id: int,
    message: ChatbotMessage,
    db: Session = Depends(get_db)
):
    """
    Enviar mensaje al chatbot (API REST)
    """
    try:
        response = await financial_chatbot.process_message(
            user_id=user_id,
            message=message.message,
            session_id=message.session_id,
            db=db
        )
        
        return ChatbotResponse(
            response=response["response"],
            intent=response["intent"],
            session_id=response["session_id"],
            context_data=response.get("context_data")
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando mensaje: {str(e)}")


@router.get("/history/{user_id}")
async def get_chat_history(
    user_id: int,
    session_id: str = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Obtener historial de conversaciones
    """
    query = db.query(ChatbotInteraction).filter(ChatbotInteraction.user_id == user_id)
    
    if session_id:
        query = query.filter(ChatbotInteraction.session_id == session_id)
    
    interactions = (
        query.order_by(ChatbotInteraction.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": interaction.id,
            "user_message": interaction.user_message,
            "bot_response": interaction.bot_response,
            "intent": interaction.intent,
            "session_id": interaction.session_id,
            "created_at": interaction.created_at.isoformat()
        }
        for interaction in interactions
    ]


@router.get("/sessions/{user_id}")
async def get_chat_sessions(
    user_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Obtener sesiones de chat del usuario
    """
    sessions = (
        db.query(ChatbotInteraction.session_id, 
                 db.func.max(ChatbotInteraction.created_at).label('last_activity'),
                 db.func.count(ChatbotInteraction.id).label('message_count'))
        .filter(ChatbotInteraction.user_id == user_id)
        .group_by(ChatbotInteraction.session_id)
        .order_by(db.func.max(ChatbotInteraction.created_at).desc())
        .limit(limit)
        .all()
    )
    
    return [
        {
            "session_id": session[0],
            "last_activity": session[1].isoformat(),
            "message_count": session[2]
        }
        for session in sessions
    ]


@router.post("/proactive-message/{user_id}")
async def send_proactive_message(
    user_id: int,
    trigger_type: str,
    background: bool = True
):
    """
    Enviar mensaje proactivo del chatbot
    """
    try:
        if background and user_id in manager.active_connections:
            # Enviar via WebSocket si está conectado
            await manager.send_proactive_message(user_id, trigger_type)
            return {"message": "Mensaje proactivo enviado via WebSocket", "type": trigger_type}
        else:
            # Generar mensaje proactivo
            message = await financial_chatbot.generate_proactive_message(user_id, trigger_type)
            return {
                "message": message,
                "type": trigger_type,
                "delivery": "api_response"
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enviando mensaje proactivo: {str(e)}")


@router.post("/trigger-alert/{user_id}")
async def trigger_spending_alert(
    user_id: int,
    alert_type: str = "high_spending_alert"
):
    """
    Disparar alerta de gasto específica
    """
    try:
        # Tipos de alerta válidos
        valid_alerts = [
            "high_spending_alert",
            "savings_opportunity", 
            "monthly_summary",
            "budget_reminder"
        ]
        
        if alert_type not in valid_alerts:
            raise HTTPException(status_code=400, detail=f"Tipo de alerta inválido. Válidos: {valid_alerts}")
        
        # Enviar mensaje proactivo
        await manager.send_proactive_message(user_id, alert_type)
        
        return {
            "message": f"Alerta {alert_type} enviada al usuario {user_id}",
            "alert_type": alert_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disparando alerta: {str(e)}")


@router.get("/analytics/{user_id}")
async def get_chatbot_analytics(
    user_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Obtener analíticas del uso del chatbot
    """
    try:
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Estadísticas básicas
        total_interactions = (
            db.query(ChatbotInteraction)
            .filter(
                ChatbotInteraction.user_id == user_id,
                ChatbotInteraction.created_at >= start_date
            )
            .count()
        )
        
        # Intenciones más comunes
        intent_stats = (
            db.query(ChatbotInteraction.intent, db.func.count(ChatbotInteraction.id))
            .filter(
                ChatbotInteraction.user_id == user_id,
                ChatbotInteraction.created_at >= start_date
            )
            .group_by(ChatbotInteraction.intent)
            .all()
        )
        
        # Sesiones únicas
        unique_sessions = (
            db.query(db.func.count(db.func.distinct(ChatbotInteraction.session_id)))
            .filter(
                ChatbotInteraction.user_id == user_id,
                ChatbotInteraction.created_at >= start_date
            )
            .scalar()
        )
        
        return {
            "total_interactions": total_interactions,
            "unique_sessions": unique_sessions,
            "intent_distribution": dict(intent_stats),
            "period_days": days,
            "average_interactions_per_session": round(total_interactions / max(unique_sessions, 1), 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo analíticas: {str(e)}")


@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Eliminar una sesión de chat completa
    """
    try:
        deleted_count = (
            db.query(ChatbotInteraction)
            .filter(
                ChatbotInteraction.session_id == session_id,
                ChatbotInteraction.user_id == user_id
            )
            .delete()
        )
        
        db.commit()
        
        return {
            "message": f"Sesión {session_id} eliminada",
            "deleted_interactions": deleted_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error eliminando sesión: {str(e)}")


# Función helper para enviar notificaciones automáticas
async def send_automatic_notification(user_id: int, notification_type: str, data: Dict[str, Any] = None):
    """
    Función helper para enviar notificaciones automáticas
    """
    try:
        if user_id in manager.active_connections:
            message = await financial_chatbot.generate_proactive_message(user_id, notification_type)
            
            notification = {
                "type": "automatic_notification",
                "notification_type": notification_type,
                "message": message,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await manager.send_personal_message(json.dumps(notification), user_id)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error enviando notificación automática: {e}")
        return False