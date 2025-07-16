"""
Aplicación principal del Analizador de Gastos IA
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .config import settings
from .database import init_db
from .api import analysis_router, chatbot_router
from .tasks.scheduler import start_background_tasks

# Contexto de la aplicación para manejo de startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    
    # Startup
    print("🚀 Iniciando AI Expense Analyzer...")
    
    # Inicializar base de datos
    await init_db()
    
    # Iniciar tareas en background
    await start_background_tasks()
    
    print("✅ AI Expense Analyzer iniciado correctamente")
    
    yield
    
    # Shutdown
    print("🛑 Cerrando AI Expense Analyzer...")
    print("✅ AI Expense Analyzer cerrado correctamente")


# Crear aplicación FastAPI
app = FastAPI(
    title="AI Expense Analyzer",
    description="Analizador inteligente de gastos con IA, recomendaciones de ahorro y chatbot financiero",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(chatbot_router, prefix="/api/v1")

# Servir archivos estáticos
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    # Crear directorio static si no existe
    import os
    os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Endpoints básicos
@app.get("/", response_class=HTMLResponse)
async def root():
    """Página principal con interfaz web básica"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Expense Analyzer</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh; color: white;
            }
            .container { max-width: 800px; margin: 0 auto; text-align: center; }
            .card { 
                background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
                border-radius: 20px; padding: 2rem; margin: 1rem 0;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }
            .feature { 
                background: rgba(255,255,255,0.05); padding: 1.5rem; border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .btn { 
                display: inline-block; padding: 12px 24px; background: rgba(255,255,255,0.2);
                color: white; text-decoration: none; border-radius: 25px; margin: 0.5rem;
                border: 1px solid rgba(255,255,255,0.3); transition: all 0.3s ease;
            }
            .btn:hover { background: rgba(255,255,255,0.3); transform: translateY(-2px); }
            .status { font-size: 0.9rem; opacity: 0.8; margin-top: 1rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>🤖 AI Expense Analyzer</h1>
                <p>Analizador inteligente de gastos con IA, recomendaciones personalizadas y chatbot financiero</p>
                
                <div class="features">
                    <div class="feature">
                        <h3>🧠 Análisis IA</h3>
                        <p>Categorización automática y detección de patrones en tus gastos</p>
                    </div>
                    <div class="feature">
                        <h3>💰 Recomendaciones</h3>
                        <p>Consejos personalizados para optimizar tus finanzas</p>
                    </div>
                    <div class="feature">
                        <h3>⚠️ Alertas</h3>
                        <p>Detección temprana de riesgos financieros</p>
                    </div>
                    <div class="feature">
                        <h3>📊 Proyecciones</h3>
                        <p>Predicciones de gastos y ahorros futuros</p>
                    </div>
                    <div class="feature">
                        <h3>💬 Chatbot</h3>
                        <p>Asistente conversacional para consultas financieras</p>
                    </div>
                    <div class="feature">
                        <h3>🔗 Integración</h3>
                        <p>Conectado con Firefly III para datos en tiempo real</p>
                    </div>
                </div>
                
                <div style="margin-top: 2rem;">
                    <a href="/docs" class="btn">📚 Documentación API</a>
                    <a href="/redoc" class="btn">📖 API Reference</a>
                </div>
                
                <div class="status">
                    ✅ Servicio activo y funcionando
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "service": "AI Expense Analyzer",
        "version": "1.0.0",
        "environment": "development" if settings.debug else "production"
    }


@app.get("/status")
async def system_status():
    """Estado del sistema y servicios conectados"""
    try:
        # Verificar conexión a Firefly III
        from .services import firefly_service
        firefly_status = "connected"
        try:
            await firefly_service.get_recent_expenses(1, 1)
        except:
            firefly_status = "disconnected"
        
        # Verificar IA
        ai_status = "available" if settings.openai_api_key else "not_configured"
        
        return {
            "system": "operational",
            "services": {
                "firefly_iii": firefly_status,
                "openai": ai_status,
                "database": "connected",
                "chatbot": "active"
            },
            "features": {
                "expense_analysis": True,
                "savings_recommendations": True,
                "risk_detection": True,
                "monthly_projections": True,
                "chatbot": True,
                "real_time_chat": True
            }
        }
        
    except Exception as e:
        return {
            "system": "degraded",
            "error": str(e),
            "services": {
                "firefly_iii": "unknown",
                "openai": "unknown", 
                "database": "unknown",
                "chatbot": "unknown"
            }
        }


# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para loggear requests"""
    import time
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    if settings.debug:
        print(f"🌐 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response


# Función principal para ejecutar el servidor
def main():
    """Función principal para ejecutar el servidor"""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()