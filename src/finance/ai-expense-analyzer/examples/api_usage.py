#!/usr/bin/env python3
"""
Ejemplos de uso de la API del AI Expense Analyzer
"""
import asyncio
import httpx
import json
import websockets
from datetime import datetime


class AIExpenseAnalyzerClient:
    """Cliente para interactuar con la API del AI Expense Analyzer"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        
    async def analyze_expense(self, user_id: int, transaction_id: int):
        """Analizar un gasto específico"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/analysis/expense/{transaction_id}",
                params={"user_id": user_id}
            )
            return response.json()
    
    async def get_savings_recommendations(self, user_id: int):
        """Obtener recomendaciones de ahorro"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/analysis/savings-recommendations/{user_id}"
            )
            return response.json()
    
    async def create_monthly_projection(self, user_id: int):
        """Crear proyección mensual"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/analysis/projection/{user_id}"
            )
            return response.json()
    
    async def get_risk_alerts(self, user_id: int, unread_only: bool = False):
        """Obtener alertas de riesgo"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/analysis/risk-alerts/{user_id}",
                params={"unread_only": unread_only}
            )
            return response.json()
    
    async def send_chat_message(self, user_id: int, message: str, session_id: str = None):
        """Enviar mensaje al chatbot"""
        async with httpx.AsyncClient() as client:
            payload = {
                "message": message,
                "session_id": session_id
            }
            response = await client.post(
                f"{self.api_url}/chatbot/message",
                params={"user_id": user_id},
                json=payload
            )
            return response.json()
    
    async def batch_analyze_expenses(self, user_id: int, days: int = 30):
        """Analizar gastos en lote"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/analysis/batch-analyze/{user_id}",
                params={"days": days}
            )
            return response.json()
    
    async def chat_websocket_example(self, user_id: int):
        """Ejemplo de chat en tiempo real con WebSocket"""
        uri = f"ws://localhost:8000/api/v1/chatbot/ws/{user_id}"
        
        async with websockets.connect(uri) as websocket:
            # Recibir mensaje de bienvenida
            welcome = await websocket.recv()
            print(f"Bienvenida: {welcome}")
            
            # Enviar algunos mensajes de ejemplo
            messages = [
                "¿Cuánto he gastado este mes?",
                "Dame consejos para ahorrar",
                "¿Cómo van mis presupuestos?",
                "Muéstrame mi proyección de gastos"
            ]
            
            for message in messages:
                # Enviar mensaje
                await websocket.send(json.dumps({
                    "message": message,
                    "session_id": "example_session"
                }))
                
                # Recibir respuesta
                response = await websocket.recv()
                response_data = json.loads(response)
                print(f"\nUsuario: {message}")
                print(f"Bot: {response_data.get('message')}")
                print(f"Intención: {response_data.get('intent')}")
                
                # Esperar un poco entre mensajes
                await asyncio.sleep(2)


async def main():
    """Ejemplos principales de uso"""
    client = AIExpenseAnalyzerClient()
    user_id = 1
    
    print("🤖 AI Expense Analyzer - Ejemplos de Uso\n")
    
    try:
        # 1. Análisis de gasto individual
        print("1. 📊 Analizando gasto individual...")
        analysis = await client.analyze_expense(user_id, transaction_id=123)
        print(f"Análisis: {json.dumps(analysis, indent=2, default=str)}\n")
        
        # 2. Recomendaciones de ahorro
        print("2. 💰 Obteniendo recomendaciones de ahorro...")
        recommendations = await client.get_savings_recommendations(user_id)
        print(f"Recomendaciones: {json.dumps(recommendations, indent=2)}\n")
        
        # 3. Proyección mensual
        print("3. 📈 Creando proyección mensual...")
        projection = await client.create_monthly_projection(user_id)
        print(f"Proyección: {json.dumps(projection, indent=2, default=str)}\n")
        
        # 4. Alertas de riesgo
        print("4. ⚠️ Verificando alertas de riesgo...")
        alerts = await client.get_risk_alerts(user_id, unread_only=True)
        print(f"Alertas: {json.dumps(alerts, indent=2, default=str)}\n")
        
        # 5. Chat con el bot
        print("5. 💬 Enviando mensaje al chatbot...")
        chat_response = await client.send_chat_message(
            user_id, 
            "¿Cuánto he gastado en restaurantes este mes?"
        )
        print(f"Respuesta del chat: {json.dumps(chat_response, indent=2)}\n")
        
        # 6. Análisis en lote
        print("6. 🔄 Iniciando análisis en lote...")
        batch_result = await client.batch_analyze_expenses(user_id, days=30)
        print(f"Resultado del lote: {json.dumps(batch_result, indent=2)}\n")
        
        # 7. Chat en tiempo real (WebSocket)
        print("7. 🌐 Ejemplo de chat en tiempo real...")
        await client.chat_websocket_example(user_id)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Asegúrate de que el servidor esté ejecutándose en http://localhost:8000")


def demo_curl_commands():
    """Mostrar ejemplos de comandos curl"""
    print("\n📝 Ejemplos de comandos curl:\n")
    
    commands = [
        {
            "name": "Health Check",
            "command": "curl -X GET http://localhost:8000/health"
        },
        {
            "name": "Analizar Gasto",
            "command": """curl -X POST "http://localhost:8000/api/v1/analysis/expense/123?user_id=1" \\
  -H "Content-Type: application/json" """
        },
        {
            "name": "Recomendaciones de Ahorro",
            "command": "curl -X GET http://localhost:8000/api/v1/analysis/savings-recommendations/1"
        },
        {
            "name": "Enviar Mensaje al Chatbot",
            "command": """curl -X POST "http://localhost:8000/api/v1/chatbot/message?user_id=1" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "¿Cuánto he gastado este mes?"}'"""
        },
        {
            "name": "Obtener Alertas de Riesgo",
            "command": "curl -X GET http://localhost:8000/api/v1/analysis/risk-alerts/1?unread_only=true"
        },
        {
            "name": "Crear Proyección Mensual",
            "command": "curl -X POST http://localhost:8000/api/v1/analysis/projection/1"
        }
    ]
    
    for cmd in commands:
        print(f"## {cmd['name']}")
        print(f"```bash")
        print(f"{cmd['command']}")
        print(f"```\n")


if __name__ == "__main__":
    # Mostrar ejemplos de curl
    demo_curl_commands()
    
    # Ejecutar ejemplos con Python
    print("🚀 Ejecutando ejemplos con Python...\n")
    asyncio.run(main())