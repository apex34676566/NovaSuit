# NovaSuite-AI Data Integration Module

Módulo completo de integración de datos para NovaSuite-AI que permite importar y exportar datos entre diversos sistemas ERP/CRM incluyendo Odoo, Zoho, SAP, ERPNext, EspoCRM y Firefly III.

## Características Principales

### 🔄 Importación de Datos
- **Formatos soportados**: CSV, JSON
- **Sistemas soportados**: Odoo, Zoho CRM/Books, SAP Business One, ERPNext, EspoCRM
- **Validación automática** de datos antes de la importación
- **Mapeo de campos** configurable entre sistemas
- **Transformaciones** automáticas (email, teléfono, fechas, etc.)
- **Procesamiento por lotes** para grandes volúmenes de datos

### 📤 Exportación de Datos
- **Exportación completa** en formato JSON con metadata
- **Exportación a CSV** para análisis en Excel
- **Exportación consolidada** de múltiples sistemas en un solo archivo
- **Filtros avanzados** para exportación selectiva
- **Soporte para paginación** en sistemas con límites de API

### ✅ Validación y Calidad de Datos
- **Validación por esquemas** específicos de cada sistema
- **Reglas de validación** configurables
- **Reportes detallados** de errores y advertencias
- **Verificación de integridad** de datos

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Configurar el módulo en tu aplicación:
```python
from src.data_integration import DataExporter, CSVImporter, DataValidator
```

## Uso Rápido

### CLI (Interfaz de Línea de Comandos)

#### Validar datos antes de importar
```bash
python -m src.data_integration.cli validate \
  -i datos.csv \
  -s odoo \
  -o reporte_validacion.txt
```

#### Importar datos desde CSV a Odoo
```bash
python -m src.data_integration.cli import-data \
  -i datos.csv \
  -c config_odoo.json \
  --dry-run  # Solo validar, no importar
```

#### Exportar datos desde ERPNext
```bash
python -m src.data_integration.cli export-data \
  -c config_erpnext.json \
  -o export_clientes.json \
  -f json
```

#### Exportar datos de todos los sistemas
```bash
python -m src.data_integration.cli export-all \
  -c /config/sistemas/ \
  -o /exports/ \
  --consolidated  # Crear un solo archivo consolidado
```

#### Generar plantilla de mapeo de campos
```bash
python -m src.data_integration.cli generate-mapping \
  -i sample_data.csv \
  -t odoo \
  -o mapping_template.json
```

### Uso Programático

#### Importar datos desde CSV a Odoo

```python
from src.data_integration import *

# Configurar sistema
config = SystemConfig(
    system_type=SystemType.ODOO,
    connection_params={
        'odoo_url': 'https://mi-odoo.com',
        'database': 'mi_db',
        'username': 'admin',
        'password': 'mi_password',
        'model': 'res.partner'
    },
    field_mappings=[
        FieldMapping('company_name', 'name', required=True),
        FieldMapping('email_address', 'email', transform_function='email'),
        FieldMapping('phone_number', 'phone', transform_function='phone'),
    ],
    batch_size=100
)

# Crear importador
importer = OdooImporter(config, **config.connection_params)

# Importar datos
result = importer.process_import('datos_clientes.csv')

if result.success:
    print(f"✅ Importados {result.imported_records} registros")
else:
    print(f"❌ Errores: {result.errors}")
```

#### Exportar datos desde ERPNext

```python
from src.data_integration import *

# Configurar sistema
config = SystemConfig(
    system_type=SystemType.ERPNEXT,
    connection_params={
        'frappe_url': 'https://mi-erpnext.com',
        'api_key': 'mi_api_key',
        'api_secret': 'mi_api_secret',
        'doctype': 'Customer'
    },
    field_mappings=[],
    batch_size=1000
)

# Exportar datos
exporter = DataExporter()
result = exporter.export_system_data(
    config, 
    'clientes_export.json', 
    DataFormat.JSON,
    filters={'disabled': 0}  # Solo clientes activos
)

print(f"Exportados {result.exported_records} registros a {result.file_path}")
```

#### Validar datos antes de importar

```python
from src.data_integration import DataValidator, SystemType
import pandas as pd

# Cargar datos
df = pd.read_csv('datos.csv')
data = df.to_dict('records')

# Validar
validator = DataValidator()
result = validator.validate_for_system(data, SystemType.ZOHO_CRM)

if result['valid']:
    print("✅ Datos válidos para importar")
else:
    print(f"❌ {result['invalid_records']} registros con errores")
    # Ver reporte detallado
    report = validator.create_validation_report(result)
    print(report)
```

## Configuración de Sistemas

### Odoo

```json
{
  "system_type": "odoo",
  "connection_params": {
    "odoo_url": "https://tu-instancia-odoo.com",
    "database": "tu_base_datos",
    "username": "tu_usuario",
    "password": "tu_contraseña",
    "model": "res.partner"
  },
  "field_mappings": [
    {
      "source_field": "company_name",
      "target_field": "name",
      "required": true
    },
    {
      "source_field": "email_address",
      "target_field": "email",
      "transform_function": "email"
    }
  ],
  "batch_size": 100
}
```

### Zoho CRM

```json
{
  "system_type": "zoho_crm",
  "connection_params": {
    "access_token": "tu_access_token",
    "refresh_token": "tu_refresh_token",
    "client_id": "tu_client_id",
    "client_secret": "tu_client_secret",
    "module": "Leads"
  },
  "field_mappings": [
    {
      "source_field": "last_name",
      "target_field": "Last_Name",
      "required": true
    },
    {
      "source_field": "company",
      "target_field": "Company",
      "required": true
    }
  ]
}
```

### SAP Business One

```json
{
  "system_type": "sap_b1",
  "connection_params": {
    "server_url": "https://tu-servidor-sap:50000/b1s/v1",
    "company_db": "TU_EMPRESA",
    "username": "tu_usuario",
    "password": "tu_contraseña",
    "object_type": "BusinessPartners"
  },
  "field_mappings": [
    {
      "source_field": "card_code",
      "target_field": "CardCode",
      "required": true
    },
    {
      "source_field": "card_name",
      "target_field": "CardName",
      "required": true
    }
  ]
}
```

## Transformaciones de Datos

El módulo incluye transformaciones automáticas para normalizar datos:

- **`email`**: Valida y normaliza direcciones de email
- **`phone`**: Formatea números de teléfono
- **`currency`**: Convierte valores monetarios
- **`date`**: Normaliza fechas a formato ISO
- **`bool`**: Convierte valores a booleanos
- **`upper/lower`**: Cambia mayúsculas/minúsculas
- **`int/float`**: Convierte tipos numéricos

### Transformaciones Personalizadas

```python
from src.data_integration import FieldMapper

mapper = FieldMapper()

# Agregar transformación personalizada
def normalize_country(value):
    country_map = {
        'US': 'United States',
        'MX': 'Mexico',
        'CA': 'Canada'
    }
    return country_map.get(value, value)

mapper.add_custom_transform('normalize_country', normalize_country)
```

## Validaciones

### Reglas de Validación Soportadas

- **`required`**: Campo obligatorio
- **`email`**: Formato de email válido
- **`phone`**: Formato de teléfono válido
- **`url`**: URL válida
- **`date/datetime`**: Formatos de fecha válidos
- **`currency`**: Formato monetario válido
- **`min_length/max_length`**: Longitud de texto
- **`min_value/max_value`**: Rangos numéricos
- **`pattern`**: Expresiones regulares
- **`in_list`**: Valores permitidos
- **`unique`**: Valores únicos

### Validaciones Personalizadas

```python
from src.data_integration import DataValidator, ValidationRule

validator = DataValidator()

# Agregar validación personalizada
def validate_tax_id(value):
    return len(str(value)) >= 9 and str(value).isdigit()

validator.schema_validator.add_custom_validator('tax_id_format', validate_tax_id)

# Usar en reglas
custom_rules = {
    'tax_id': [
        ValidationRule('tax_id', 'custom', 'tax_id_format', 
                      "Tax ID must be at least 9 digits")
    ]
}
```

## Formato de Exportación JSON

Las exportaciones en JSON incluyen metadata detallada:

```json
{
  "metadata": {
    "export_date": "2024-01-15T10:30:00",
    "total_records": 1250,
    "source_system": "erpnext",
    "version": "1.0"
  },
  "data": [
    {
      "name": "CUST-001",
      "customer_name": "Acme Corporation",
      "email_id": "contact@acme.com",
      "creation": "2024-01-10T09:15:00"
    }
  ]
}
```

## Exportación Consolidada

Combina datos de múltiples sistemas en un solo archivo:

```json
{
  "metadata": {
    "export_date": "2024-01-15T10:30:00",
    "systems": ["erpnext", "espocrm", "firefly"],
    "total_records": 3500,
    "version": "1.0"
  },
  "data": {
    "erpnext": [...],
    "espocrm": [...],
    "firefly": [...]
  }
}
```

## Manejo de Errores

### Importación con Errores

```python
result = importer.process_import('datos.csv')

if not result.success:
    print(f"Total: {result.total_records}")
    print(f"Importados: {result.imported_records}")
    print(f"Fallidos: {result.failed_records}")
    
    print("Errores:")
    for error in result.errors:
        print(f"  - {error}")
    
    print("Advertencias:")
    for warning in result.warnings:
        print(f"  - {warning}")
```

### Validación con Errores

```python
validation_result = validator.validate_for_system(data, SystemType.ODOO)

if validation_result['validation_errors']:
    for record_id, errors in validation_result['validation_errors'].items():
        print(f"{record_id}:")
        for error in errors:
            print(f"  - {error}")
```

## Mejores Prácticas

### 1. Validación Previa
Siempre valida los datos antes de importar:
```bash
# Validar primero
python -m src.data_integration.cli validate -i datos.csv -s odoo

# Luego importar
python -m src.data_integration.cli import-data -i datos.csv -c config.json
```

### 2. Pruebas con Dry Run
Usa el modo dry-run para pruebas:
```bash
python -m src.data_integration.cli import-data -i datos.csv -c config.json --dry-run
```

### 3. Manejo de Lotes
Ajusta el tamaño de lote según tu sistema:
```json
{
  "batch_size": 50   // Para sistemas lentos
  "batch_size": 500  // Para sistemas rápidos
}
```

### 4. Campos Únicos
Asegúrate de mapear campos únicos correctamente:
```json
{
  "source_field": "customer_code",
  "target_field": "name",
  "required": true
}
```

### 5. Respaldos
Siempre exporta datos antes de importaciones masivas:
```bash
# Exportar datos actuales
python -m src.data_integration.cli export-data -c config.json -o backup.json

# Importar nuevos datos
python -m src.data_integration.cli import-data -i nuevos_datos.csv -c config.json
```

## Solución de Problemas

### Error de Autenticación
- Verifica credenciales en el archivo de configuración
- Para Zoho: regenera tokens de acceso
- Para SAP: verifica la URL del servidor y certificados

### Error de Formato de Datos
- Usa el comando `validate` para identificar problemas
- Revisa los mapeos de campos
- Verifica transformaciones de datos

### Límites de API
- Reduce el tamaño de lote (`batch_size`)
- Implementa delays entre requests
- Verifica límites de rate limiting del sistema

### Memoria Insuficiente
- Procesa archivos en chunks más pequeños
- Usa streaming para archivos grandes
- Aumenta memoria disponible

## Contribuir

### Agregar Nuevo Sistema

1. Crear nuevo importador/exportador:
```python
class MiSistemaImporter(BaseImporter):
    def __init__(self, config, ...):
        super().__init__(config)
        # Inicialización específica
    
    def _parse_source_data(self, source_data):
        # Implementar parsing
        pass
    
    def validate_data(self, data):
        # Implementar validación
        pass
    
    def import_data(self, data):
        # Implementar importación
        pass
```

2. Agregar al enum SystemType:
```python
class SystemType(Enum):
    MI_SISTEMA = "mi_sistema"
```

3. Agregar validaciones específicas del sistema
4. Actualizar CLI y documentación

### Agregar Nueva Transformación

```python
def mi_transformacion(value):
    # Implementar lógica
    return transformed_value

# Registrar transformación
field_mapper.add_custom_transform('mi_transformacion', mi_transformacion)
```

## Licencia

Este módulo es parte de NovaSuite-AI y está sujeto a los términos de licencia del proyecto principal.

## Soporte

Para soporte y documentación adicional, consulta:
- Issues en GitHub
- Documentación del proyecto NovaSuite-AI
- Ejemplos en el directorio `examples/`