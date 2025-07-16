"""
Programador de tareas en background
"""
import asyncio
import schedule
import time
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services import ai_analyzer, firefly_service, financial_chatbot
from ..models import ExpenseAnalysis, RiskAlert, SavingsProjection
from ..api.endpoints.chatbot import send_automatic_notification


class BackgroundTaskScheduler:
    """Programador de tareas automáticas"""
    
    def __init__(self):
        self.running = False
    
    async def start(self):
        """Iniciar programador de tareas"""
        if self.running:
            return
        
        self.running = True
        print("📅 Iniciando programador de tareas en background...")
        
        # Programar tareas
        self._schedule_tasks()
        
        # Ejecutar loop en background
        asyncio.create_task(self._run_scheduler())
        
        print("✅ Programador de tareas iniciado")
    
    def _schedule_tasks(self):
        """Configurar horarios de las tareas"""
        
        # Análisis diario de gastos (cada día a las 08:00)
        schedule.every().day.at("08:00").do(
            lambda: asyncio.create_task(self.daily_expense_analysis())
        )
        
        # Detección de riesgos (cada 6 horas)
        schedule.every(6).hours.do(
            lambda: asyncio.create_task(self.risk_detection_task())
        )
        
        # Proyecciones mensuales (primer día del mes a las 09:00)
        schedule.every().day.at("09:00").do(
            lambda: asyncio.create_task(self.monthly_projection_task())
        )
        
        # Resumen semanal (lunes a las 10:00)
        schedule.every().monday.at("10:00").do(
            lambda: asyncio.create_task(self.weekly_summary_task())
        )
        
        # Notificaciones de presupuesto (diario a las 18:00)
        schedule.every().day.at("18:00").do(
            lambda: asyncio.create_task(self.budget_notifications_task())
        )
        
        # Limpieza de datos antiguos (cada domingo a las 02:00)
        schedule.every().sunday.at("02:00").do(
            lambda: asyncio.create_task(self.cleanup_old_data())
        )
    
    async def _run_scheduler(self):
        """Ejecutar el programador en loop"""
        while self.running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Verificar cada minuto
    
    async def daily_expense_analysis(self):
        """Análisis diario automático de gastos"""
        print("🔍 Ejecutando análisis diario de gastos...")
        
        try:
            db = SessionLocal()
            
            # Obtener usuarios con gastos recientes (simulado)
            active_users = [1, 2, 3]  # En producción, obtener de base de datos
            
            for user_id in active_users:
                try:
                    # Obtener gastos del día anterior
                    yesterday_expenses = await firefly_service.get_recent_expenses(user_id, 1)
                    
                    if not yesterday_expenses:
                        continue
                    
                    # Analizar cada gasto no analizado
                    for expense in yesterday_expenses:
                        existing_analysis = (
                            db.query(ExpenseAnalysis)
                            .filter(
                                ExpenseAnalysis.user_id == user_id,
                                ExpenseAnalysis.firefly_transaction_id == expense["id"]
                            )
                            .first()
                        )
                        
                        if existing_analysis:
                            continue
                        
                        # Realizar análisis IA
                        analysis_result = await ai_analyzer.analyze_expense(expense)
                        
                        # Guardar análisis
                        analysis = ExpenseAnalysis(
                            user_id=user_id,
                            firefly_transaction_id=expense["id"],
                            category=expense["category"],
                            amount=expense["amount"],
                            ai_category=analysis_result["ai_category"],
                            risk_score=analysis_result["risk_score"],
                            anomaly_detected=analysis_result["anomaly_detected"],
                            confidence_score=analysis_result["confidence_score"],
                            insights=analysis_result["insights"],
                            recommendations=analysis_result["recommendations"]
                        )
                        
                        db.add(analysis)
                        
                        # Enviar notificación si hay anomalía
                        if analysis_result["anomaly_detected"]:
                            await send_automatic_notification(
                                user_id,
                                "high_spending_alert",
                                {"expense": expense, "analysis": analysis_result}
                            )
                    
                    db.commit()
                    print(f"✅ Análisis diario completado para usuario {user_id}")
                
                except Exception as e:
                    print(f"❌ Error analizando usuario {user_id}: {e}")
                    db.rollback()
            
            db.close()
            print("✅ Análisis diario de gastos completado")
            
        except Exception as e:
            print(f"❌ Error en análisis diario: {e}")
    
    async def risk_detection_task(self):
        """Tarea de detección de riesgos financieros"""
        print("⚠️ Ejecutando detección de riesgos...")
        
        try:
            db = SessionLocal()
            active_users = [1, 2, 3]  # En producción, obtener de base de datos
            
            for user_id in active_users:
                try:
                    # Obtener datos del usuario
                    expenses = await firefly_service.get_recent_expenses(user_id, 30)
                    budget_data = await firefly_service.get_budget_data(user_id)
                    
                    user_data = {
                        "expenses": expenses,
                        "budget": budget_data
                    }
                    
                    # Detectar riesgos
                    risks = await ai_analyzer.detect_financial_risks(user_data)
                    
                    # Crear alertas
                    for risk in risks:
                        # Verificar si ya existe alerta similar reciente
                        recent_alert = (
                            db.query(RiskAlert)
                            .filter(
                                RiskAlert.user_id == user_id,
                                RiskAlert.alert_type == risk["type"],
                                RiskAlert.created_at >= datetime.utcnow() - timedelta(hours=24)
                            )
                            .first()
                        )
                        
                        if recent_alert:
                            continue
                        
                        # Crear nueva alerta
                        alert = RiskAlert(
                            user_id=user_id,
                            alert_type=risk["type"],
                            severity=risk["severity"],
                            title=risk["title"],
                            description=risk["description"],
                            suggested_actions=risk["suggestions"]
                        )
                        
                        db.add(alert)
                        
                        # Enviar notificación
                        if risk["severity"] in ["high", "critical"]:
                            await send_automatic_notification(
                                user_id,
                                "risk_alert",
                                {"alert": risk}
                            )
                    
                    db.commit()
                
                except Exception as e:
                    print(f"❌ Error detectando riesgos para usuario {user_id}: {e}")
                    db.rollback()
            
            db.close()
            print("✅ Detección de riesgos completada")
            
        except Exception as e:
            print(f"❌ Error en detección de riesgos: {e}")
    
    async def monthly_projection_task(self):
        """Tarea de proyecciones mensuales"""
        # Solo ejecutar el primer día del mes
        if datetime.now().day != 1:
            return
        
        print("📊 Generando proyecciones mensuales...")
        
        try:
            db = SessionLocal()
            active_users = [1, 2, 3]
            
            for user_id in active_users:
                try:
                    # Obtener datos históricos
                    historical_data = await firefly_service.get_recent_expenses(user_id, 90)
                    
                    if not historical_data:
                        continue
                    
                    # Crear proyección
                    projection_data = await ai_analyzer.create_monthly_projection(user_id, historical_data)
                    
                    # Marcar proyecciones anteriores como no actuales
                    db.query(SavingsProjection).filter(
                        SavingsProjection.user_id == user_id,
                        SavingsProjection.is_current_month == True
                    ).update({"is_current_month": False})
                    
                    # Crear nueva proyección
                    current_date = datetime.utcnow()
                    projection = SavingsProjection(
                        user_id=user_id,
                        month=current_date.month,
                        year=current_date.year,
                        projected_savings=projection_data["projected_savings"],
                        projected_expenses=projection_data["projected_expenses"],
                        category_projections=projection_data["category_projections"],
                        confidence_score=projection_data["confidence_score"],
                        is_current_month=True
                    )
                    
                    db.add(projection)
                    db.commit()
                    
                    # Enviar notificación
                    await send_automatic_notification(
                        user_id,
                        "monthly_summary",
                        {"projection": projection_data}
                    )
                
                except Exception as e:
                    print(f"❌ Error generando proyección para usuario {user_id}: {e}")
                    db.rollback()
            
            db.close()
            print("✅ Proyecciones mensuales generadas")
            
        except Exception as e:
            print(f"❌ Error en proyecciones mensuales: {e}")
    
    async def weekly_summary_task(self):
        """Resumen semanal para usuarios"""
        print("📋 Generando resúmenes semanales...")
        
        try:
            active_users = [1, 2, 3]
            
            for user_id in active_users:
                try:
                    # Obtener gastos de la semana
                    weekly_expenses = await firefly_service.get_recent_expenses(user_id, 7)
                    
                    if weekly_expenses:
                        total_spent = sum(expense["amount"] for expense in weekly_expenses)
                        
                        # Generar recomendaciones semanales
                        recommendations = await ai_analyzer.generate_savings_recommendations(weekly_expenses)
                        
                        # Enviar resumen
                        await send_automatic_notification(
                            user_id,
                            "weekly_summary",
                            {
                                "total_spent": total_spent,
                                "transactions": len(weekly_expenses),
                                "recommendations": recommendations[:3]  # Top 3
                            }
                        )
                
                except Exception as e:
                    print(f"❌ Error generando resumen para usuario {user_id}: {e}")
            
            print("✅ Resúmenes semanales enviados")
            
        except Exception as e:
            print(f"❌ Error en resúmenes semanales: {e}")
    
    async def budget_notifications_task(self):
        """Notificaciones de estado del presupuesto"""
        print("💰 Verificando estados de presupuesto...")
        
        try:
            active_users = [1, 2, 3]
            
            for user_id in active_users:
                try:
                    # Obtener uso del presupuesto
                    budget_usage = await firefly_service.get_budget_usage(user_id)
                    
                    if not budget_usage or not budget_usage.get("categories"):
                        continue
                    
                    # Verificar categorías con sobregasto o cerca del límite
                    for category, usage in budget_usage["categories"].items():
                        percentage = usage.get("percentage", 0)
                        
                        if percentage >= 90:
                            # Alerta de presupuesto agotado
                            await send_automatic_notification(
                                user_id,
                                "budget_alert",
                                {
                                    "category": category,
                                    "percentage": percentage,
                                    "type": "overspent" if percentage > 100 else "near_limit"
                                }
                            )
                
                except Exception as e:
                    print(f"❌ Error verificando presupuesto para usuario {user_id}: {e}")
            
            print("✅ Notificaciones de presupuesto enviadas")
            
        except Exception as e:
            print(f"❌ Error en notificaciones de presupuesto: {e}")
    
    async def cleanup_old_data(self):
        """Limpiar datos antiguos"""
        print("🧹 Ejecutando limpieza de datos antiguos...")
        
        try:
            db = SessionLocal()
            
            # Eliminar interacciones del chatbot más antiguas de 6 meses
            cutoff_date = datetime.utcnow() - timedelta(days=180)
            
            from ..models import ChatbotInteraction
            deleted_interactions = (
                db.query(ChatbotInteraction)
                .filter(ChatbotInteraction.created_at < cutoff_date)
                .delete()
            )
            
            # Marcar alertas antiguas como leídas
            old_alerts_updated = (
                db.query(RiskAlert)
                .filter(
                    RiskAlert.created_at < cutoff_date,
                    RiskAlert.is_read == False
                )
                .update({"is_read": True})
            )
            
            db.commit()
            db.close()
            
            print(f"✅ Limpieza completada: {deleted_interactions} interacciones eliminadas, {old_alerts_updated} alertas marcadas como leídas")
            
        except Exception as e:
            print(f"❌ Error en limpieza de datos: {e}")
    
    def stop(self):
        """Detener programador de tareas"""
        self.running = False
        schedule.clear()
        print("🛑 Programador de tareas detenido")


# Instancia global del programador
task_scheduler = BackgroundTaskScheduler()


async def start_background_tasks():
    """Iniciar todas las tareas en background"""
    await task_scheduler.start()


def stop_background_tasks():
    """Detener todas las tareas en background"""
    task_scheduler.stop()