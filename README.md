# NovaSuite-AI - Sistema de Autenticación con 2FA y Cumplimiento GDPR

Sistema completo de autenticación con doble factor (2FA), rotación automática de claves API cada 30 días, logs de auditoría y cumplimiento GDPR.

## 🚀 Características Principales

### 🔐 Autenticación Segura
- **Autenticación de doble factor (2FA)** con TOTP y códigos por email
- **Códigos de respaldo** para recuperación de cuentas
- **Bloqueo de cuentas** después de intentos fallidos
- **Tokens JWT** con expiración configurable

### 🔑 Gestión de Claves API
- **Rotación automática** cada 30 días
- **Cifrado de claves** con Fernet
- **Control de permisos** por scopes
- **Whitelist de IPs** para mayor seguridad
- **Límites de uso** configurables

### 📊 Auditoría Completa
- **Logs estructurados** en JSON
- **Categorización** de eventos (auth, security, gdpr, api)
- **Retención automática** de logs (7 años para datos financieros)
- **Reportes de cumplimiento** automatizados

### 🇪🇺 Cumplimiento GDPR
- **Gestión de consentimiento** granular
- **Derechos del sujeto de datos** (Artículos 15-20)
- **Portabilidad de datos** en JSON/CSV
- **Derecho al olvido** con eliminación programada
- **Registro de cambios legales** con versionado

## 🛠️ Instalación y Configuración

### 1. Requisitos del Sistema
```bash
# Python 3.8+
python --version

# PostgreSQL (recomendado para producción)
sudo apt-get install postgresql postgresql-contrib

# Redis (opcional, para cache)
sudo apt-get install redis-server
```

### 2. Instalación de Dependencias
```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd novasuite-ai

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno
```bash
# Copiar archivo de configuración
cp .env.example .env

# Editar configuración (IMPORTANTE: cambiar claves secretas)
nano .env
```

### 4. Configuración de Base de Datos
```bash
# Para PostgreSQL
sudo -u postgres psql
CREATE DATABASE novasuite_db;
CREATE USER novasuite_user WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE novasuite_db TO novasuite_user;
\q

# Actualizar DATABASE_URL en .env
DATABASE_URL=postgresql://novasuite_user:tu_password@localhost/novasuite_db
```

### 5. Ejecutar la Aplicación
```bash
# Inicializar base de datos (automático al arrancar)
python src/app.py

# La aplicación estará disponible en http://localhost:5000
```

## 📚 API Endpoints

### 🔐 Autenticación

#### Registro de Usuario
```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "usuario",
  "email": "usuario@example.com",
  "password": "password_segura",
  "gdpr_consent": true
}
```

#### Inicio de Sesión
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "usuario",
  "password": "password_segura",
  "totp_token": "123456"  # Opcional si 2FA está habilitado
}
```

### 🔒 Gestión de 2FA

#### Configurar 2FA
```bash
POST /api/auth/2fa/setup
Authorization: Bearer <jwt_token>
```

#### Verificar y Habilitar 2FA
```bash
POST /api/auth/2fa/verify
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "token": "123456"
}
```

#### Deshabilitar 2FA
```bash
POST /api/auth/2fa/disable
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "token": "123456"
}
```

### 🔑 Gestión de Claves API

#### Crear Clave API
```bash
POST /api/keys
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "Mi API Key",
  "scopes": ["read", "write"],
  "expires_days": 30,
  "rate_limit": 1000,
  "ip_whitelist": ["192.168.1.100"]
}
```

#### Listar Claves API
```bash
GET /api/keys
Authorization: Bearer <jwt_token>
```

#### Rotar Clave API
```bash
POST /api/keys/<key_id>/rotate
Authorization: Bearer <jwt_token>
```

### 🇪🇺 GDPR Compliance

#### Solicitar Acceso a Datos (Artículo 15)
```bash
POST /api/gdpr/data-access
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "categories": ["personal_identifiers", "audit_data"],
  "format": "json"
}
```

#### Portabilidad de Datos (Artículo 20)
```bash
POST /api/gdpr/data-portability
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "format": "json"
}
```

#### Solicitar Eliminación (Artículo 17)
```bash
POST /api/gdpr/erasure
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "reason": "Ya no deseo usar el servicio",
  "immediate": false
}
```

### 👨‍💼 Endpoints de Administración

#### Buscar Logs de Auditoría
```bash
GET /api/admin/audit/logs?event_category=auth&start_date=2024-01-01
X-API-Key: <admin_api_key>
```

#### Generar Reporte de Cumplimiento
```bash
GET /api/admin/compliance/report?start_date=2024-01-01&end_date=2024-12-31
X-API-Key: <admin_api_key>
```

#### Registrar Cambio Legal
```bash
POST /api/admin/legal/changes
X-API-Key: <admin_api_key>
Content-Type: application/json

{
  "change_type": "privacy_policy",
  "title": "Actualización de Política de Privacidad",
  "description": "Cambios por nueva regulación",
  "jurisdiction": "EU",
  "regulation": "GDPR",
  "compliance_deadline": "2024-12-31T23:59:59"
}
```

## 🔧 Configuración Avanzada

### Seguridad
- **Claves secretas**: Cambiar `SECRET_KEY` y `JWT_SECRET_KEY` en producción
- **Base de datos**: Usar PostgreSQL en producción
- **HTTPS**: Configurar certificados SSL/TLS
- **Firewall**: Restringir acceso a puertos necesarios

### Email
```bash
# Gmail
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password

# Outlook
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
```

### Redis (Producción)
```bash
# Instalar Redis
sudo apt-get install redis-server

# Configurar en .env
REDIS_URL=redis://localhost:6379/0
```

## 📈 Monitoreo y Logs

### Estructura de Logs
```
logs/
├── auth.log          # Eventos de autenticación
├── security.log      # Eventos de seguridad
├── api.log           # Accesos API
├── gdpr.log          # Eventos GDPR
├── compliance.log    # Cumplimiento legal
└── emergency.log     # Logs de emergencia
```

### Análisis de Logs
```bash
# Ver logs de autenticación en tiempo real
tail -f logs/auth.log | jq '.'

# Buscar intentos de login fallidos
grep "login_failed" logs/auth.log | jq '.'

# Reportes de uso de API
grep "api_request" logs/api.log | jq '.metadata.endpoint' | sort | uniq -c
```

## 🚀 Producción

### Docker (Recomendado)
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY .env .

EXPOSE 5000
CMD ["python", "src/app.py"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/novasuite
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: novasuite
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    
volumes:
  postgres_data:
```

### Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 🧪 Testing

### Ejecutar Tests
```bash
# Instalar dependencias de test
pip install pytest pytest-cov

# Ejecutar tests
pytest tests/ -v --cov=src/

# Test de cobertura
pytest --cov=src/ --cov-report=html
```

### Test Manual con curl
```bash
# Registro de usuario
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123","gdpr_consent":true}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'
```

## 📋 Cumplimiento Legal

### GDPR
- ✅ **Consentimiento explícito** con registro de mecanismo
- ✅ **Derecho de acceso** (Artículo 15)
- ✅ **Derecho de rectificación** (Artículo 16)  
- ✅ **Derecho al olvido** (Artículo 17)
- ✅ **Portabilidad de datos** (Artículo 20)
- ✅ **Notificación de cambios** legales
- ✅ **Retención de datos** configurable

### Auditoría
- ✅ **Logs inmutables** con timestamps
- ✅ **Trazabilidad completa** de acciones
- ✅ **Retención** según normativas
- ✅ **Exportación** para auditorías

## 🤝 Contribución

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🆘 Soporte

- **Documentación**: [Wiki del proyecto]
- **Issues**: [GitHub Issues]
- **Email**: support@novasuite.ai
- **Discord**: [Servidor de la comunidad]

## 🔄 Actualizaciones

### v1.0.0 (Actual)
- ✅ Sistema de autenticación 2FA
- ✅ Rotación automática de API keys
- ✅ Logs de auditoría completos
- ✅ Cumplimiento GDPR
- ✅ Dashboard de administración

### Próximas Versiones
- 🔄 Integración con Active Directory
- 🔄 SSO con OAuth2/SAML
- 🔄 Análisis de comportamiento con ML
- 🔄 API GraphQL
- 🔄 Dashboard web interactivo