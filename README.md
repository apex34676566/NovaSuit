# NovaSuite-AI

Plataforma integral de gestión empresarial con IA integrada

## Módulos Integrados

### 🏢 Core Business (ERPNext/Frappe)
- **Ubicación**: `src/core/erpnext/` y `src/core/frappe/`
- **Descripción**: Sistema ERP completo para gestión empresarial
- **Funcionalidades**: Contabilidad, inventario, ventas, compras, RRHH

### 👥 CRM (EspoCRM)
- **Ubicación**: `src/crm/espocrm/`
- **Descripción**: Sistema de gestión de relaciones con clientes
- **Funcionalidades**: Gestión de leads, oportunidades, contactos

### 💰 Finanzas (Firefly III + AI Expense Analyzer)
- **Ubicación**: `src/finance/firefly-iii/` y `src/finance/ai-expense-analyzer/`
- **Descripción**: Gestión financiera personal y empresarial con IA
- **Funcionalidades**:
  - 🤖 **Análisis IA de Gastos**: Categorización automática y detección de patrones
  - 💡 **Recomendaciones de Ahorro**: Sugerencias personalizadas basadas en comportamiento
  - ⚠️ **Alertas de Riesgo**: Detección temprana de gastos anómalos
  - 📊 **Proyecciones Mensuales**: Predicciones de ahorro y gasto futuro
  - 💬 **Chatbot Financiero**: Asistente conversacional para consultas financieras
  - 🔗 **Integración**: Conectado con Firefly III para datos en tiempo real

### 🔒 Seguridad (Wazuh)
- **Ubicación**: `src/security/wazuh/`
- **Descripción**: Plataforma de monitoreo de seguridad
- **Funcionalidades**: Detección de amenazas, monitoreo de logs, compliance

## Nuevo: AI Expense Analyzer 🤖

### Características Principales

- **Análisis Inteligente**: Usa IA (OpenAI GPT) para analizar patrones de gasto
- **Recomendaciones Personalizadas**: Consejos de ahorro basados en tu comportamiento
- **Detección de Anomalías**: Identifica gastos inusuales automáticamente
- **Proyecciones Futuras**: Predice gastos y ahorros del próximo mes
- **Chatbot Financiero**: Interfaz conversacional para consultas financieras
- **Alertas Inteligentes**: Notificaciones proactivas sobre riesgos financieros

### Quick Start

```bash
# Navegar al directorio del AI Expense Analyzer
cd src/finance/ai-expense-analyzer

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus claves de API

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar con Docker Compose
docker-compose up -d

# O ejecutar directamente
python run.py
```

### API Endpoints

- **Análisis**: `POST /api/v1/analysis/expense/{transaction_id}`
- **Recomendaciones**: `GET /api/v1/analysis/savings-recommendations/{user_id}`
- **Proyecciones**: `POST /api/v1/analysis/projection/{user_id}`
- **Alertas**: `GET /api/v1/analysis/risk-alerts/{user_id}`
- **Chatbot**: `POST /api/v1/chatbot/message`
- **WebSocket Chat**: `ws://localhost:8000/api/v1/chatbot/ws/{user_id}`

### Documentación

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Ejemplos**: `src/finance/ai-expense-analyzer/examples/api_usage.py`

## Configuración General

### Requisitos del Sistema

- Docker & Docker Compose
- Python 3.8+ (para desarrollo)
- PostgreSQL 12+
- Redis 6+

### Variables de Entorno

Cada módulo tiene su propio archivo `.env`. Ver archivos `.env.example` en cada directorio.

## Arquitectura

```
NovaSuite-AI/
├── src/
│   ├── core/                 # ERPNext/Frappe
│   ├── crm/                  # EspoCRM
│   ├── finance/              # Firefly III + AI Analyzer
│   │   ├── firefly-iii/      # Gestión financiera tradicional
│   │   └── ai-expense-analyzer/  # 🆕 Análisis IA de gastos
│   └── security/             # Wazuh
└── README.md
```

## Desarrollo

### Contribuir al AI Expense Analyzer

1. Fork el repositorio
2. Crear rama feature: `git checkout -b feature/nueva-funcionalidad`
3. Desarrollar en: `src/finance/ai-expense-analyzer/`
4. Ejecutar tests: `pytest`
5. Commit y push
6. Crear Pull Request

### Tecnologías Utilizadas

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **IA**: OpenAI GPT, scikit-learn, pandas
- **Base de Datos**: PostgreSQL
- **Cache**: Redis
- **WebSockets**: Para chat en tiempo real
- **Contenedores**: Docker, Docker Compose

## Roadmap

- [x] Análisis básico de gastos con IA
- [x] Chatbot financiero conversacional
- [x] Proyecciones mensuales automáticas
- [x] Sistema de alertas inteligentes
- [ ] Integración con más bancos y servicios financieros
- [ ] Dashboard web interactivo
- [ ] Análisis predictivo avanzado
- [ ] Integración con ERPNext para empresas
- [ ] Mobile app

## Soporte

Para issues específicos del AI Expense Analyzer, crear un issue en GitHub con el tag `ai-expense-analyzer`.

## Licencia

MIT License - Ver LICENSE file para detalles.