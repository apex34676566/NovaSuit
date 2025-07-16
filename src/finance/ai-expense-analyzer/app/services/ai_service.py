"""
Servicio de IA para análisis de gastos
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import openai
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ..config import settings
from ..models import ExpenseAnalysis, SavingsProjection, RiskAlert

# Configurar OpenAI
openai.api_key = settings.openai_api_key


class AIExpenseAnalyzer:
    """Analizador de gastos usando IA"""
    
    def __init__(self):
        self.model = settings.ai_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
        
    async def analyze_expense(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analizar un gasto individual usando IA
        """
        try:
            # Preparar prompt para análisis
            prompt = self._create_analysis_prompt(transaction_data)
            
            # Llamada a OpenAI
            response = await self._call_openai(prompt)
            
            # Procesar respuesta
            analysis = self._parse_ai_response(response)
            
            # Añadir análisis de anomalías
            anomaly_score = await self._detect_anomaly(transaction_data)
            analysis['anomaly_detected'] = anomaly_score > settings.risk_threshold
            analysis['risk_score'] = anomaly_score
            
            return analysis
            
        except Exception as e:
            print(f"Error en análisis IA: {e}")
            return self._get_fallback_analysis(transaction_data)
    
    async def generate_savings_recommendations(self, user_expenses: List[Dict]) -> List[str]:
        """
        Generar recomendaciones de ahorro personalizadas
        """
        try:
            # Análisis de patrones de gasto
            expense_df = pd.DataFrame(user_expenses)
            spending_patterns = self._analyze_spending_patterns(expense_df)
            
            # Prompt para recomendaciones
            prompt = self._create_savings_prompt(spending_patterns)
            
            # Llamada a OpenAI
            response = await self._call_openai(prompt)
            
            # Procesar recomendaciones
            recommendations = self._parse_recommendations(response)
            
            return recommendations
            
        except Exception as e:
            print(f"Error generando recomendaciones: {e}")
            return self._get_fallback_recommendations()
    
    async def create_monthly_projection(self, user_id: int, historical_data: List[Dict]) -> Dict[str, Any]:
        """
        Crear proyección de gastos y ahorros para el próximo mes
        """
        try:
            df = pd.DataFrame(historical_data)
            
            # Análisis temporal
            monthly_trends = self._analyze_monthly_trends(df)
            
            # Proyecciones usando IA
            projection_prompt = self._create_projection_prompt(monthly_trends)
            response = await self._call_openai(projection_prompt)
            
            projection_data = self._parse_projection_response(response)
            
            # Añadir análisis estadístico
            statistical_projection = self._calculate_statistical_projection(df)
            
            # Combinar IA y estadísticas
            final_projection = self._combine_projections(projection_data, statistical_projection)
            
            return final_projection
            
        except Exception as e:
            print(f"Error en proyección mensual: {e}")
            return self._get_fallback_projection()
    
    async def detect_financial_risks(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detectar riesgos financieros usando IA
        """
        risks = []
        
        try:
            # Análisis de tendencias de gasto
            spending_trend = self._analyze_spending_trend(user_data['expenses'])
            
            # Detección de gastos inusuales
            unusual_expenses = await self._detect_unusual_expenses(user_data['expenses'])
            
            # Análisis de presupuesto
            budget_risks = self._analyze_budget_risks(user_data)
            
            # Crear alertas
            if spending_trend['increasing_rapidly']:
                risks.append({
                    'type': 'spending_increase',
                    'severity': 'medium',
                    'title': 'Incremento Acelerado en Gastos',
                    'description': f"Tus gastos han aumentado {spending_trend['increase_percentage']:.1f}% este mes",
                    'suggestions': ['Revisar gastos no esenciales', 'Establecer límites diarios']
                })
            
            for expense in unusual_expenses:
                risks.append({
                    'type': 'unusual_pattern',
                    'severity': 'high' if expense['amount'] > 1000 else 'medium',
                    'title': 'Gasto Inusual Detectado',
                    'description': f"Gasto de ${expense['amount']:.2f} en {expense['category']} es inusual para ti",
                    'suggestions': ['Verificar si el gasto era necesario', 'Considerar alternativas más económicas']
                })
            
            return risks
            
        except Exception as e:
            print(f"Error detectando riesgos: {e}")
            return []
    
    def _create_analysis_prompt(self, transaction_data: Dict[str, Any]) -> str:
        """Crear prompt para análisis de transacción"""
        return f"""
        Analiza la siguiente transacción financiera:
        
        Descripción: {transaction_data.get('description', 'N/A')}
        Cantidad: ${transaction_data.get('amount', 0):.2f}
        Categoría: {transaction_data.get('category', 'N/A')}
        Fecha: {transaction_data.get('date', 'N/A')}
        Comerciante: {transaction_data.get('merchant', 'N/A')}
        
        Proporciona un análisis en formato JSON con:
        1. "ai_category": categoría más específica
        2. "confidence_score": confianza del análisis (0-1)
        3. "insights": lista de insights sobre el gasto
        4. "recommendations": lista de recomendaciones específicas
        5. "essential": si es un gasto esencial (true/false)
        
        Responde solo con JSON válido.
        """
    
    def _create_savings_prompt(self, spending_patterns: Dict[str, Any]) -> str:
        """Crear prompt para recomendaciones de ahorro"""
        return f"""
        Basándote en estos patrones de gasto:
        
        {json.dumps(spending_patterns, indent=2)}
        
        Genera 5 recomendaciones específicas y actionables para ahorrar dinero.
        Cada recomendación debe incluir:
        - Acción específica
        - Ahorro estimado mensual
        - Dificultad de implementación (fácil/medio/difícil)
        
        Responde en formato JSON con una lista de recomendaciones.
        """
    
    def _create_projection_prompt(self, monthly_trends: Dict[str, Any]) -> str:
        """Crear prompt para proyección mensual"""
        return f"""
        Basándote en estas tendencias mensuales:
        
        {json.dumps(monthly_trends, indent=2)}
        
        Crea una proyección para el próximo mes incluyendo:
        1. "projected_expenses": gastos totales estimados
        2. "projected_savings": ahorros estimados
        3. "category_projections": gastos por categoría
        4. "confidence_score": confianza de la proyección (0-1)
        5. "key_factors": factores que influyen en la proyección
        
        Responde solo con JSON válido.
        """
    
    async def _call_openai(self, prompt: str) -> str:
        """Llamada asíncrona a OpenAI"""
        try:
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un experto analista financiero que proporciona insights precisos y recomendaciones prácticas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error en llamada OpenAI: {e}")
            raise
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parsear respuesta de IA"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Intentar extraer JSON de la respuesta
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                try:
                    return json.loads(response[start:end])
                except:
                    pass
            
            # Fallback
            return {
                "ai_category": "Otros",
                "confidence_score": 0.5,
                "insights": ["Análisis no disponible"],
                "recommendations": ["Revisar categorización manual"],
                "essential": False
            }
    
    async def _detect_anomaly(self, transaction_data: Dict[str, Any]) -> float:
        """Detectar anomalías usando machine learning"""
        try:
            # Simular detección de anomalías (en producción usar datos históricos)
            amount = float(transaction_data.get('amount', 0))
            
            # Reglas simples para detección de anomalías
            if amount > 1000:  # Gasto alto
                return 0.8
            elif amount > 500:  # Gasto medio-alto
                return 0.6
            else:
                return 0.2
                
        except Exception as e:
            print(f"Error en detección de anomalías: {e}")
            return 0.0
    
    def _analyze_spending_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizar patrones de gasto"""
        try:
            patterns = {
                "total_monthly": df['amount'].sum(),
                "category_breakdown": df.groupby('category')['amount'].sum().to_dict(),
                "average_transaction": df['amount'].mean(),
                "transaction_count": len(df),
                "top_categories": df.groupby('category')['amount'].sum().nlargest(5).to_dict()
            }
            return patterns
        except Exception as e:
            print(f"Error analizando patrones: {e}")
            return {}
    
    def _analyze_monthly_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizar tendencias mensuales"""
        try:
            # Convertir fecha si es necesario
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['month'] = df['date'].dt.month
                df['year'] = df['date'].dt.year
            
            trends = {
                "monthly_totals": df.groupby(['year', 'month'])['amount'].sum().to_dict(),
                "category_trends": df.groupby(['category'])['amount'].mean().to_dict(),
                "growth_rate": 0.05  # Simulated growth rate
            }
            return trends
        except Exception as e:
            print(f"Error analizando tendencias: {e}")
            return {}
    
    def _get_fallback_analysis(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis de respaldo cuando falla la IA"""
        return {
            "ai_category": transaction_data.get('category', 'Otros'),
            "confidence_score": 0.5,
            "insights": ["Análisis automático no disponible"],
            "recommendations": ["Revisar categorización"],
            "anomaly_detected": False,
            "risk_score": 0.0,
            "essential": False
        }
    
    def _get_fallback_recommendations(self) -> List[str]:
        """Recomendaciones de respaldo"""
        return [
            "Revisa tus gastos mensuales y identifica áreas de mejora",
            "Establece un presupuesto mensual para cada categoría",
            "Considera usar la regla 50/30/20 para tus finanzas",
            "Busca ofertas y descuentos antes de comprar",
            "Evalúa suscripciones que no uses frecuentemente"
        ]
    
    def _get_fallback_projection(self) -> Dict[str, Any]:
        """Proyección de respaldo"""
        return {
            "projected_expenses": 1500.0,
            "projected_savings": 300.0,
            "category_projections": {"Alimentación": 400, "Transporte": 200, "Entretenimiento": 150},
            "confidence_score": 0.3,
            "key_factors": ["Datos insuficientes para proyección precisa"]
        }
    
    def _parse_recommendations(self, response: str) -> List[str]:
        """Parsear recomendaciones de la respuesta de IA"""
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "recommendations" in data:
                return data["recommendations"]
            else:
                return ["Revisar gastos mensuales", "Establecer presupuesto", "Buscar ofertas"]
        except:
            return self._get_fallback_recommendations()
    
    def _parse_projection_response(self, response: str) -> Dict[str, Any]:
        """Parsear respuesta de proyección"""
        try:
            data = json.loads(response)
            return data
        except:
            return self._get_fallback_projection()
    
    def _calculate_statistical_projection(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcular proyección estadística"""
        try:
            monthly_avg = df['amount'].mean() * 30  # Promedio diario * 30 días
            return {
                "projected_expenses": monthly_avg,
                "projected_savings": max(0, 2000 - monthly_avg),  # Asumiendo ingreso de 2000
                "confidence": 0.7
            }
        except:
            return self._get_fallback_projection()
    
    def _combine_projections(self, ai_projection: Dict[str, Any], stat_projection: Dict[str, Any]) -> Dict[str, Any]:
        """Combinar proyecciones de IA y estadísticas"""
        try:
            return {
                "projected_expenses": (ai_projection.get("projected_expenses", 0) + stat_projection.get("projected_expenses", 0)) / 2,
                "projected_savings": (ai_projection.get("projected_savings", 0) + stat_projection.get("projected_savings", 0)) / 2,
                "category_projections": ai_projection.get("category_projections", {}),
                "confidence_score": (ai_projection.get("confidence_score", 0.5) + stat_projection.get("confidence", 0.5)) / 2,
                "key_factors": ai_projection.get("key_factors", ["Análisis combinado de IA y estadísticas"])
            }
        except:
            return self._get_fallback_projection()
    
    def _analyze_spending_trend(self, expenses: List[Dict]) -> Dict[str, Any]:
        """Analizar tendencias de gasto"""
        try:
            if len(expenses) < 2:
                return {"increasing_rapidly": False, "increase_percentage": 0}
            
            # Dividir en dos períodos
            mid_point = len(expenses) // 2
            recent_total = sum(exp["amount"] for exp in expenses[:mid_point])
            older_total = sum(exp["amount"] for exp in expenses[mid_point:])
            
            if older_total == 0:
                return {"increasing_rapidly": False, "increase_percentage": 0}
            
            increase_percentage = ((recent_total - older_total) / older_total) * 100
            return {
                "increasing_rapidly": increase_percentage > 20,
                "increase_percentage": increase_percentage
            }
        except:
            return {"increasing_rapidly": False, "increase_percentage": 0}
    
    async def _detect_unusual_expenses(self, expenses: List[Dict]) -> List[Dict]:
        """Detectar gastos inusuales"""
        try:
            if not expenses:
                return []
            
            amounts = [exp["amount"] for exp in expenses]
            avg_amount = sum(amounts) / len(amounts)
            threshold = avg_amount * 2  # 2x el promedio
            
            unusual = []
            for exp in expenses:
                if exp["amount"] > threshold:
                    unusual.append(exp)
            
            return unusual
        except:
            return []
    
    def _analyze_budget_risks(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analizar riesgos del presupuesto"""
        try:
            budget = user_data.get("budget", {})
            if not budget:
                return {}
            
            categories = budget.get("categories", {})
            risks = {}
            
            for category, data in categories.items():
                allocated = data.get("allocated", 0)
                spent = data.get("spent", 0)
                
                if allocated > 0:
                    percentage = (spent / allocated) * 100
                    if percentage > 90:
                        risks[category] = {
                            "risk_level": "high" if percentage > 100 else "medium",
                            "percentage": percentage
                        }
            
            return risks
        except:
            return {}


# Instancia global del analizador
ai_analyzer = AIExpenseAnalyzer()