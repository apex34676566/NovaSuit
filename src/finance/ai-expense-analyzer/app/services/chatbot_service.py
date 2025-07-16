"""
Servicio de Chatbot Financiero
"""
import json
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import openai
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ChatbotInteraction
from .ai_service import ai_analyzer
from .firefly_service import firefly_service

# Configurar OpenAI
openai.api_key = settings.openai_api_key


class FinancialChatbot:
    """Chatbot financiero inteligente"""
    
    def __init__(self):
        self.model = settings.ai_model
        self.conversation_history = {}
        
    async def process_message(
        self, 
        user_id: int, 
        message: str, 
        session_id: Optional[str] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Procesar mensaje del usuario y generar respuesta
        """
        try:
            # Generar session_id si no existe
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # Detectar intención del mensaje
            intent = await self._detect_intent(message)
            
            # Obtener contexto del usuario
            context = await self._get_user_context(user_id, intent)
            
            # Generar respuesta basada en intención
            response = await self._generate_response(message, intent, context, session_id)
            
            # Guardar interacción en base de datos
            if db:
                await self._save_interaction(
                    db, user_id, session_id, message, response['message'], intent, context
                )
            
            return {
                'response': response['message'],
                'intent': intent,
                'session_id': session_id,
                'context_data': context,
                'suggested_actions': response.get('actions', [])
            }
            
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            return {
                'response': "Lo siento, no pude procesar tu mensaje. ¿Podrías reformularlo?",
                'intent': 'error',
                'session_id': session_id or str(uuid.uuid4()),
                'context_data': {},
                'suggested_actions': []
            }
    
    async def generate_proactive_message(self, user_id: int, trigger_type: str) -> Optional[str]:
        """
        Generar mensajes proactivos basados en eventos
        """
        try:
            context = await self._get_user_context(user_id, f"proactive_{trigger_type}")
            
            if trigger_type == "high_spending_alert":
                return await self._generate_spending_alert(context)
            elif trigger_type == "savings_opportunity":
                return await self._generate_savings_suggestion(context)
            elif trigger_type == "monthly_summary":
                return await self._generate_monthly_summary(context)
            elif trigger_type == "budget_reminder":
                return await self._generate_budget_reminder(context)
            
            return None
            
        except Exception as e:
            print(f"Error generando mensaje proactivo: {e}")
            return None
    
    async def _detect_intent(self, message: str) -> str:
        """
        Detectar la intención del mensaje del usuario
        """
        try:
            # Lista de intenciones posibles
            intents = {
                "gastos_consulta": ["gastos", "gastado", "cuánto", "total", "resumen"],
                "categoria_consulta": ["categoría", "categoria", "tipo", "clasificación"],
                "ahorro_consulta": ["ahorro", "ahorrar", "ahorrado", "economizar"],
                "presupuesto_consulta": ["presupuesto", "límite", "meta"],
                "proyeccion_consulta": ["proyección", "proyeccion", "predicción", "futuro"],
                "consejo_ahorro": ["consejo", "recomendación", "sugerencia", "tip"],
                "alerta_riesgo": ["alerta", "riesgo", "peligro", "advertencia"],
                "comparacion": ["comparar", "diferencia", "vs", "versus"],
                "saludo": ["hola", "buenos", "buenas", "hey", "saludos"],
                "despedida": ["adios", "adiós", "hasta", "nos vemos", "bye"]
            }
            
            message_lower = message.lower()
            
            # Buscar palabras clave
            for intent, keywords in intents.items():
                if any(keyword in message_lower for keyword in keywords):
                    return intent
            
            # Si no se detecta intención específica, usar IA
            intent_prompt = f"""
            Clasifica la siguiente consulta financiera en una de estas categorías:
            - gastos_consulta: preguntas sobre gastos realizados
            - categoria_consulta: preguntas sobre categorías de gastos
            - ahorro_consulta: preguntas sobre ahorros
            - presupuesto_consulta: preguntas sobre presupuestos
            - proyeccion_consulta: preguntas sobre proyecciones futuras
            - consejo_ahorro: solicitud de consejos de ahorro
            - alerta_riesgo: preguntas sobre riesgos financieros
            - comparacion: comparaciones entre períodos o categorías
            - general: consulta general
            
            Consulta: "{message}"
            
            Responde solo con el nombre de la categoría.
            """
            
            response = await self._call_openai_simple(intent_prompt)
            return response.strip().lower() if response else "general"
            
        except Exception as e:
            print(f"Error detectando intención: {e}")
            return "general"
    
    async def _get_user_context(self, user_id: int, intent: str) -> Dict[str, Any]:
        """
        Obtener contexto del usuario para la respuesta
        """
        try:
            context = {
                "user_id": user_id,
                "intent": intent,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Obtener datos relevantes según la intención
            if intent in ["gastos_consulta", "categoria_consulta", "comparacion"]:
                context["recent_expenses"] = await firefly_service.get_recent_expenses(user_id, 30)
                context["monthly_summary"] = await firefly_service.get_monthly_summary(user_id)
            
            elif intent in ["ahorro_consulta", "consejo_ahorro"]:
                context["savings_data"] = await firefly_service.get_savings_data(user_id)
                context["spending_patterns"] = await self._get_spending_patterns(user_id)
            
            elif intent in ["presupuesto_consulta"]:
                context["budget_data"] = await firefly_service.get_budget_data(user_id)
                context["budget_usage"] = await firefly_service.get_budget_usage(user_id)
            
            elif intent in ["proyeccion_consulta"]:
                context["projection_data"] = await self._get_latest_projection(user_id)
            
            return context
            
        except Exception as e:
            print(f"Error obteniendo contexto: {e}")
            return {"user_id": user_id, "intent": intent}
    
    async def _generate_response(
        self, 
        message: str, 
        intent: str, 
        context: Dict[str, Any], 
        session_id: str
    ) -> Dict[str, Any]:
        """
        Generar respuesta usando IA
        """
        try:
            # Preparar prompt específico según intención
            prompt = self._create_response_prompt(message, intent, context)
            
            # Llamada a OpenAI
            response = await self._call_openai_simple(prompt)
            
            # Procesar respuesta
            actions = self._extract_suggested_actions(intent, context)
            
            return {
                'message': response,
                'actions': actions
            }
            
        except Exception as e:
            print(f"Error generando respuesta: {e}")
            return {
                'message': "Lo siento, tengo problemas técnicos. ¿Puedes intentar más tarde?",
                'actions': []
            }
    
    def _create_response_prompt(self, message: str, intent: str, context: Dict[str, Any]) -> str:
        """
        Crear prompt para generar respuesta
        """
        base_prompt = f"""
        Eres un asistente financiero personal experto y amigable. Tu objetivo es ayudar al usuario con sus finanzas de manera clara y práctica.
        
        Mensaje del usuario: "{message}"
        Intención detectada: {intent}
        
        Contexto del usuario:
        {json.dumps(context, indent=2, default=str)}
        
        Instrucciones:
        1. Responde de manera conversacional y amigable
        2. Proporciona información específica basada en los datos del usuario
        3. Da consejos prácticos y actionables
        4. Mantén las respuestas concisas pero informativas
        5. Usa emojis ocasionalmente para hacer la conversación más amigable
        6. Si no tienes datos suficientes, sugiere cómo obtenerlos
        
        Respuesta:
        """
        
        # Añadir instrucciones específicas según intención
        if intent == "gastos_consulta":
            base_prompt += "\nCentrate en analizar los gastos del usuario y proporcionar insights útiles."
        elif intent == "consejo_ahorro":
            base_prompt += "\nProporciona consejos específicos de ahorro basados en los patrones de gasto del usuario."
        elif intent == "proyeccion_consulta":
            base_prompt += "\nExplica las proyecciones futuras de manera clara y menciona factores importantes."
        
        return base_prompt
    
    async def _call_openai_simple(self, prompt: str) -> str:
        """
        Llamada simple a OpenAI para respuestas del chatbot
        """
        try:
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un asistente financiero personal experto y amigable."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error en llamada OpenAI: {e}")
            return "Lo siento, no puedo procesar tu solicitud en este momento."
    
    def _extract_suggested_actions(self, intent: str, context: Dict[str, Any]) -> List[str]:
        """
        Extraer acciones sugeridas basadas en intención y contexto
        """
        actions = []
        
        if intent == "gastos_consulta":
            actions = [
                "Ver desglose por categorías",
                "Comparar con mes anterior",
                "Establecer límites de gasto"
            ]
        elif intent == "consejo_ahorro":
            actions = [
                "Ver recomendaciones personalizadas",
                "Configurar metas de ahorro",
                "Analizar gastos innecesarios"
            ]
        elif intent == "presupuesto_consulta":
            actions = [
                "Crear nuevo presupuesto",
                "Ajustar límites actuales",
                "Ver progreso del presupuesto"
            ]
        
        return actions
    
    async def _generate_spending_alert(self, context: Dict[str, Any]) -> str:
        """
        Generar alerta de gasto alto
        """
        return "🚨 ¡Atención! Has superado tu promedio de gasto mensual en un 25%. Te recomiendo revisar tus gastos recientes y considerar reducir gastos no esenciales."
    
    async def _generate_savings_suggestion(self, context: Dict[str, Any]) -> str:
        """
        Generar sugerencia de ahorro
        """
        return "💡 Oportunidad de ahorro: He notado que gastas frecuentemente en delivery. Podrías ahorrar aproximadamente $200 al mes cocinando en casa 3 días más por semana."
    
    async def _generate_monthly_summary(self, context: Dict[str, Any]) -> str:
        """
        Generar resumen mensual
        """
        return "📊 Resumen del mes: Gastaste $1,450 este mes. Tus principales categorías fueron Alimentación ($400) y Transporte ($250). ¡Lograste ahorrar $300! 🎉"
    
    async def _generate_budget_reminder(self, context: Dict[str, Any]) -> str:
        """
        Generar recordatorio de presupuesto
        """
        return "📋 Recordatorio: Te quedan $150 disponibles en tu presupuesto de entretenimiento para este mes. ¡Vas muy bien! 👍"
    
    async def _save_interaction(
        self, 
        db: Session, 
        user_id: int, 
        session_id: str, 
        user_message: str, 
        bot_response: str, 
        intent: str, 
        context: Dict[str, Any]
    ):
        """
        Guardar interacción en base de datos
        """
        try:
            interaction = ChatbotInteraction(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                bot_response=bot_response,
                intent=intent,
                context_data=context
            )
            
            db.add(interaction)
            db.commit()
            
        except Exception as e:
            print(f"Error guardando interacción: {e}")
            db.rollback()
    
    async def _get_spending_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener patrones de gasto del usuario
        """
        try:
            # Simular obtención de patrones (integrar con AI service)
            return {
                "top_categories": {"Alimentación": 400, "Transporte": 200},
                "monthly_trend": "increasing",
                "average_transaction": 45.50
            }
        except Exception as e:
            print(f"Error obteniendo patrones: {e}")
            return {}
    
    async def _get_latest_projection(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener última proyección del usuario
        """
        try:
            # Simular obtención de proyección
            return {
                "projected_savings": 300,
                "projected_expenses": 1500,
                "confidence": 0.85
            }
        except Exception as e:
            print(f"Error obteniendo proyección: {e}")
            return {}


# Instancia global del chatbot
financial_chatbot = FinancialChatbot()