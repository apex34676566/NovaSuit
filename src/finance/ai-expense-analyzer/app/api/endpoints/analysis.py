"""
Endpoints para análisis de gastos
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from ...database import get_db
from ...models import (
    ExpenseAnalysis, SavingsProjection, RiskAlert,
    ExpenseAnalysisResponse, SavingsProjectionResponse, RiskAlertResponse
)
from ...services import ai_analyzer, firefly_service

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("/expense/{transaction_id}", response_model=ExpenseAnalysisResponse)
async def analyze_expense(
    transaction_id: int,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analizar un gasto específico usando IA
    """
    try:
        # Obtener datos de la transacción desde Firefly III
        expenses = await firefly_service.get_recent_expenses(user_id, 1)
        if not expenses:
            raise HTTPException(status_code=404, detail="Transacción no encontrada")
        
        transaction_data = expenses[0]  # En producción, filtrar por transaction_id
        
        # Realizar análisis IA
        analysis_result = await ai_analyzer.analyze_expense(transaction_data)
        
        # Guardar análisis en base de datos
        analysis = ExpenseAnalysis(
            user_id=user_id,
            firefly_transaction_id=transaction_id,
            category=transaction_data["category"],
            amount=transaction_data["amount"],
            ai_category=analysis_result["ai_category"],
            risk_score=analysis_result["risk_score"],
            anomaly_detected=analysis_result["anomaly_detected"],
            confidence_score=analysis_result["confidence_score"],
            insights=analysis_result["insights"],
            recommendations=analysis_result["recommendations"]
        )
        
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        # Crear análisis en Firefly III (background)
        background_tasks.add_task(
            firefly_service.create_transaction_analysis,
            transaction_id,
            analysis_result
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analizando gasto: {str(e)}")


@router.get("/expenses/{user_id}", response_model=List[ExpenseAnalysisResponse])
async def get_expense_analyses(
    user_id: int,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """
    Obtener análisis de gastos del usuario
    """
    analyses = (
        db.query(ExpenseAnalysis)
        .filter(ExpenseAnalysis.user_id == user_id)
        .order_by(ExpenseAnalysis.analysis_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return analyses


@router.post("/batch-analyze/{user_id}")
async def batch_analyze_expenses(
    user_id: int,
    days: int = 30,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analizar gastos en lote para un usuario
    """
    try:
        # Obtener gastos recientes
        expenses = await firefly_service.get_recent_expenses(user_id, days)
        
        if not expenses:
            raise HTTPException(status_code=404, detail="No se encontraron gastos para analizar")
        
        # Procesar en background
        background_tasks.add_task(
            _process_batch_analysis,
            user_id,
            expenses,
            db
        )
        
        return {
            "message": f"Iniciando análisis de {len(expenses)} gastos",
            "total_expenses": len(expenses),
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en análisis por lote: {str(e)}")


@router.get("/savings-recommendations/{user_id}")
async def get_savings_recommendations(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtener recomendaciones de ahorro personalizadas
    """
    try:
        # Obtener gastos del usuario
        expenses = await firefly_service.get_recent_expenses(user_id, 60)
        
        if not expenses:
            return {"recommendations": [], "message": "No hay datos suficientes para generar recomendaciones"}
        
        # Generar recomendaciones usando IA
        recommendations = await ai_analyzer.generate_savings_recommendations(expenses)
        
        return {
            "recommendations": recommendations,
            "based_on_days": 60,
            "total_expenses": len(expenses),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando recomendaciones: {str(e)}")


@router.post("/projection/{user_id}", response_model=SavingsProjectionResponse)
async def create_monthly_projection(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Crear proyección de ahorro mensual
    """
    try:
        # Obtener datos históricos
        historical_expenses = await firefly_service.get_recent_expenses(user_id, 90)
        
        if not historical_expenses:
            raise HTTPException(status_code=404, detail="No hay datos históricos suficientes")
        
        # Crear proyección usando IA
        projection_data = await ai_analyzer.create_monthly_projection(user_id, historical_expenses)
        
        # Guardar proyección
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
        
        # Marcar proyecciones anteriores como no actuales
        db.query(SavingsProjection).filter(
            SavingsProjection.user_id == user_id,
            SavingsProjection.is_current_month == True
        ).update({"is_current_month": False})
        
        db.add(projection)
        db.commit()
        db.refresh(projection)
        
        return projection
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando proyección: {str(e)}")


@router.get("/projections/{user_id}", response_model=List[SavingsProjectionResponse])
async def get_savings_projections(
    user_id: int,
    months: int = 12,
    db: Session = Depends(get_db)
):
    """
    Obtener proyecciones de ahorro del usuario
    """
    projections = (
        db.query(SavingsProjection)
        .filter(SavingsProjection.user_id == user_id)
        .order_by(SavingsProjection.year.desc(), SavingsProjection.month.desc())
        .limit(months)
        .all()
    )
    
    return projections


@router.get("/risk-alerts/{user_id}", response_model=List[RiskAlertResponse])
async def get_risk_alerts(
    user_id: int,
    unread_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Obtener alertas de riesgo del usuario
    """
    query = db.query(RiskAlert).filter(RiskAlert.user_id == user_id)
    
    if unread_only:
        query = query.filter(RiskAlert.is_read == False)
    
    alerts = query.order_by(RiskAlert.created_at.desc()).all()
    
    return alerts


@router.post("/detect-risks/{user_id}")
async def detect_financial_risks(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Detectar riesgos financieros y crear alertas
    """
    try:
        # Obtener datos del usuario
        expenses = await firefly_service.get_recent_expenses(user_id, 30)
        budget_data = await firefly_service.get_budget_data(user_id)
        
        user_data = {
            "expenses": expenses,
            "budget": budget_data
        }
        
        # Detectar riesgos usando IA
        risks = await ai_analyzer.detect_financial_risks(user_data)
        
        # Crear alertas en la base de datos
        for risk in risks:
            alert = RiskAlert(
                user_id=user_id,
                alert_type=risk["type"],
                severity=risk["severity"],
                title=risk["title"],
                description=risk["description"],
                suggested_actions=risk["suggestions"]
            )
            db.add(alert)
        
        db.commit()
        
        return {
            "risks_detected": len(risks),
            "alerts_created": len(risks),
            "message": "Análisis de riesgos completado"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detectando riesgos: {str(e)}")


@router.put("/risk-alert/{alert_id}/mark-read")
async def mark_alert_as_read(
    alert_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Marcar alerta como leída
    """
    alert = (
        db.query(RiskAlert)
        .filter(RiskAlert.id == alert_id, RiskAlert.user_id == user_id)
        .first()
    )
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    
    alert.is_read = True
    db.commit()
    
    return {"message": "Alerta marcada como leída"}


async def _process_batch_analysis(user_id: int, expenses: List[dict], db: Session):
    """
    Procesar análisis por lote en background
    """
    try:
        for expense in expenses:
            # Verificar si ya existe análisis
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
        
        db.commit()
        print(f"✅ Análisis por lote completado para usuario {user_id}")
        
    except Exception as e:
        print(f"❌ Error en análisis por lote: {e}")
        db.rollback()