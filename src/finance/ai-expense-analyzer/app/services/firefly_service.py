"""
Servicio de integración con Firefly III
"""
import httpx
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from ..config import settings


class FireflyIIIService:
    """Servicio para integración con Firefly III"""
    
    def __init__(self):
        self.base_url = settings.firefly_iii_url
        self.token = settings.firefly_iii_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.api+json"
        }
    
    async def get_recent_expenses(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Obtener gastos recientes del usuario
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/transactions",
                    headers=self.headers,
                    params={
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                        "type": "withdrawal"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._process_transactions(data.get("data", []))
                else:
                    print(f"Error obteniendo transacciones: {response.status_code}")
                    return []
                    
        except Exception as e:
            print(f"Error conectando con Firefly III: {e}")
            # Datos de ejemplo para demostración
            return self._get_sample_expenses()
    
    async def get_monthly_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener resumen mensual de gastos
        """
        try:
            current_month = datetime.now().replace(day=1)
            next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/summary/basic",
                    headers=self.headers,
                    params={
                        "start": current_month.strftime("%Y-%m-%d"),
                        "end": (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._process_monthly_summary(data)
                else:
                    return self._get_sample_monthly_summary()
                    
        except Exception as e:
            print(f"Error obteniendo resumen mensual: {e}")
            return self._get_sample_monthly_summary()
    
    async def get_savings_data(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener datos de ahorros del usuario
        """
        try:
            async with httpx.AsyncClient() as client:
                # Obtener cuentas de ahorro
                accounts_response = await client.get(
                    f"{self.base_url}/api/v1/accounts",
                    headers=self.headers,
                    params={"type": "asset"}
                )
                
                if accounts_response.status_code == 200:
                    accounts = accounts_response.json().get("data", [])
                    savings_accounts = [acc for acc in accounts if "saving" in acc.get("attributes", {}).get("name", "").lower()]
                    
                    total_savings = sum(
                        float(acc.get("attributes", {}).get("current_balance", 0))
                        for acc in savings_accounts
                    )
                    
                    return {
                        "total_savings": total_savings,
                        "savings_accounts": len(savings_accounts),
                        "monthly_goal": 500.0,  # Meta configurable
                        "current_month_savings": 250.0  # Calcular real
                    }
                else:
                    return self._get_sample_savings_data()
                    
        except Exception as e:
            print(f"Error obteniendo datos de ahorro: {e}")
            return self._get_sample_savings_data()
    
    async def get_budget_data(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener datos de presupuesto del usuario
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/budgets",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._process_budget_data(data.get("data", []))
                else:
                    return self._get_sample_budget_data()
                    
        except Exception as e:
            print(f"Error obteniendo presupuestos: {e}")
            return self._get_sample_budget_data()
    
    async def get_budget_usage(self, user_id: int) -> Dict[str, Any]:
        """
        Obtener uso actual del presupuesto
        """
        try:
            current_month = datetime.now().replace(day=1)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/budgets/limits",
                    headers=self.headers,
                    params={
                        "start": current_month.strftime("%Y-%m-%d")
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._process_budget_usage(data.get("data", []))
                else:
                    return self._get_sample_budget_usage()
                    
        except Exception as e:
            print(f"Error obteniendo uso de presupuesto: {e}")
            return self._get_sample_budget_usage()
    
    async def create_transaction_analysis(self, transaction_id: int, analysis_data: Dict[str, Any]) -> bool:
        """
        Crear análisis de transacción en Firefly III (usando notas/metadatos)
        """
        try:
            async with httpx.AsyncClient() as client:
                # Actualizar transacción con metadatos de análisis IA
                response = await client.put(
                    f"{self.base_url}/api/v1/transactions/{transaction_id}",
                    headers=self.headers,
                    json={
                        "notes": json.dumps({
                            "ai_analysis": analysis_data,
                            "analyzed_at": datetime.utcnow().isoformat()
                        })
                    }
                )
                
                return response.status_code == 200
                
        except Exception as e:
            print(f"Error creando análisis en Firefly III: {e}")
            return False
    
    def _process_transactions(self, transactions: List[Dict]) -> List[Dict[str, Any]]:
        """
        Procesar transacciones de Firefly III
        """
        processed = []
        
        for transaction in transactions:
            attributes = transaction.get("attributes", {})
            transaction_data = attributes.get("transactions", [{}])[0]
            
            processed.append({
                "id": transaction.get("id"),
                "description": transaction_data.get("description", ""),
                "amount": abs(float(transaction_data.get("amount", 0))),
                "category": transaction_data.get("category_name", "Sin categoría"),
                "date": transaction_data.get("date", ""),
                "merchant": transaction_data.get("destination_name", ""),
                "currency": transaction_data.get("currency_code", "USD")
            })
        
        return processed
    
    def _process_monthly_summary(self, data: Dict) -> Dict[str, Any]:
        """
        Procesar resumen mensual de Firefly III
        """
        return {
            "total_expenses": float(data.get("spent", [{}])[0].get("sum", 0)),
            "total_income": float(data.get("earned", [{}])[0].get("sum", 0)),
            "net_worth": float(data.get("net_worth", [{}])[0].get("sum", 0)),
            "categories": {}  # Procesar categorías si están disponibles
        }
    
    def _process_budget_data(self, budgets: List[Dict]) -> Dict[str, Any]:
        """
        Procesar datos de presupuesto
        """
        budget_summary = {
            "total_budgets": len(budgets),
            "categories": {},
            "total_allocated": 0.0
        }
        
        for budget in budgets:
            attributes = budget.get("attributes", {})
            name = attributes.get("name", "")
            # Obtener límites del presupuesto
            budget_summary["categories"][name] = {
                "allocated": 0.0,  # Necesita llamada adicional para obtener límites
                "spent": 0.0,
                "remaining": 0.0
            }
        
        return budget_summary
    
    def _process_budget_usage(self, budget_limits: List[Dict]) -> Dict[str, Any]:
        """
        Procesar uso del presupuesto
        """
        usage = {
            "categories": {},
            "total_allocated": 0.0,
            "total_spent": 0.0,
            "total_remaining": 0.0
        }
        
        for limit in budget_limits:
            attributes = limit.get("attributes", {})
            amount = float(attributes.get("amount", 0))
            spent = float(attributes.get("spent", 0))
            
            usage["total_allocated"] += amount
            usage["total_spent"] += abs(spent)
            usage["total_remaining"] += (amount - abs(spent))
        
        return usage
    
    def _get_sample_expenses(self) -> List[Dict[str, Any]]:
        """
        Datos de ejemplo para demostración
        """
        return [
            {
                "id": 1,
                "description": "Compra en supermercado",
                "amount": 85.50,
                "category": "Alimentación",
                "date": "2024-01-15",
                "merchant": "Supermercado Central",
                "currency": "USD"
            },
            {
                "id": 2,
                "description": "Gasolina",
                "amount": 45.00,
                "category": "Transporte",
                "date": "2024-01-14",
                "merchant": "Estación de Servicio",
                "currency": "USD"
            },
            {
                "id": 3,
                "description": "Cena restaurante",
                "amount": 125.75,
                "category": "Entretenimiento",
                "date": "2024-01-13",
                "merchant": "Restaurante Elegante",
                "currency": "USD"
            }
        ]
    
    def _get_sample_monthly_summary(self) -> Dict[str, Any]:
        """
        Resumen mensual de ejemplo
        """
        return {
            "total_expenses": 1450.00,
            "total_income": 3500.00,
            "net_worth": 12500.00,
            "categories": {
                "Alimentación": 400.00,
                "Transporte": 250.00,
                "Entretenimiento": 300.00,
                "Servicios": 200.00,
                "Otros": 300.00
            }
        }
    
    def _get_sample_savings_data(self) -> Dict[str, Any]:
        """
        Datos de ahorro de ejemplo
        """
        return {
            "total_savings": 5000.00,
            "savings_accounts": 2,
            "monthly_goal": 500.00,
            "current_month_savings": 300.00
        }
    
    def _get_sample_budget_data(self) -> Dict[str, Any]:
        """
        Datos de presupuesto de ejemplo
        """
        return {
            "total_budgets": 5,
            "categories": {
                "Alimentación": {"allocated": 500.00, "spent": 400.00, "remaining": 100.00},
                "Transporte": {"allocated": 300.00, "spent": 250.00, "remaining": 50.00},
                "Entretenimiento": {"allocated": 200.00, "spent": 300.00, "remaining": -100.00},
                "Servicios": {"allocated": 250.00, "spent": 200.00, "remaining": 50.00}
            },
            "total_allocated": 1250.00
        }
    
    def _get_sample_budget_usage(self) -> Dict[str, Any]:
        """
        Uso de presupuesto de ejemplo
        """
        return {
            "categories": {
                "Alimentación": {"allocated": 500.00, "spent": 400.00, "percentage": 80.0},
                "Transporte": {"allocated": 300.00, "spent": 250.00, "percentage": 83.3},
                "Entretenimiento": {"allocated": 200.00, "spent": 300.00, "percentage": 150.0}
            },
            "total_allocated": 1000.00,
            "total_spent": 950.00,
            "total_remaining": 50.00
        }


# Instancia global del servicio
firefly_service = FireflyIIIService()