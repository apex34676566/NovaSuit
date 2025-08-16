#!/usr/bin/env python3
"""
NovaSuite-AI Data Integration - Usage Example

Este script demuestra cómo usar el módulo de integración de datos
para importar y exportar datos entre diferentes sistemas ERP/CRM.
"""

import sys
import json
from pathlib import Path

# Agregar el path del módulo
sys.path.append(str(Path(__file__).parent.parent.parent))

from data_integration import (
    DataExporter, CSVImporter, JSONImporter, DataValidator,
    SystemType, DataFormat, SystemConfig, FieldMapping,
    DataMapper, SystemMapper
)

def example_csv_validation():
    """Ejemplo: Validar datos CSV antes de importar"""
    print("🔍 Ejemplo 1: Validación de datos CSV")
    print("=" * 50)
    
    # Simular datos CSV
    sample_data = [
        {
            'company_name': 'Acme Corporation',
            'email_address': 'contact@acme.com',
            'phone_number': '(555) 123-4567',
            'street_address': '123 Main Street',
            'city': 'New York',
            'state': 'NY'
        },
        {
            'company_name': '',  # Error: nombre requerido
            'email_address': 'invalid-email',  # Error: email inválido
            'phone_number': '123',  # Error: teléfono inválido
            'street_address': '456 Oak Avenue',
            'city': 'Los Angeles',
            'state': 'CA'
        }
    ]
    
    # Validar para Odoo
    validator = DataValidator()
    result = validator.validate_for_system(sample_data, SystemType.ODOO)
    
    # Mostrar resultados
    print(f"Total de registros: {result['total_records']}")
    print(f"Registros válidos: {result['valid_records']}")
    print(f"Registros inválidos: {result['invalid_records']}")
    print(f"Estado general: {'✅ VÁLIDO' if result['valid'] else '❌ INVÁLIDO'}")
    
    if result['validation_errors']:
        print("\nErrores encontrados:")
        for record_id, errors in result['validation_errors'].items():
            print(f"  {record_id}:")
            for error in errors:
                print(f"    - {error}")
    
    print("\n" + "=" * 50 + "\n")

def example_field_mapping():
    """Ejemplo: Mapeo de campos entre sistemas"""
    print("🗺️  Ejemplo 2: Mapeo de campos")
    print("=" * 50)
    
    # Datos de ejemplo con campos del sistema origen
    source_data = [
        {
            'customer_name': 'Global Tech Solutions',
            'contact_email': 'info@globaltech.com',
            'phone_main': '555-234-5678',
            'address_line1': '456 Oak Avenue',
            'city_name': 'Los Angeles'
        }
    ]
    
    # Crear mapeos de campos
    field_mappings = [
        FieldMapping('customer_name', 'name', required=True),
        FieldMapping('contact_email', 'email', transform_function='email'),
        FieldMapping('phone_main', 'phone', transform_function='phone'),
        FieldMapping('address_line1', 'street'),
        FieldMapping('city_name', 'city'),
        FieldMapping('', 'is_company', default_value=True, transform_function='bool'),
        FieldMapping('', 'customer', default_value=True, transform_function='bool')
    ]
    
    # Aplicar mapeos
    mapper = DataMapper()
    mapped_data = []
    
    from data_integration.mappers import FieldMapper
    field_mapper = FieldMapper()
    
    for record in source_data:
        mapped_record = field_mapper.apply_mapping(record, field_mappings)
        mapped_data.append(mapped_record)
    
    print("Datos originales:")
    print(json.dumps(source_data[0], indent=2, ensure_ascii=False))
    
    print("\nDatos mapeados para Odoo:")
    print(json.dumps(mapped_data[0], indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 50 + "\n")

def example_system_export_simulation():
    """Ejemplo: Simulación de exportación de datos"""
    print("📤 Ejemplo 3: Exportación de datos (simulada)")
    print("=" * 50)
    
    # Simular configuración de ERPNext
    config = SystemConfig(
        system_type=SystemType.ERPNEXT,
        connection_params={
            'frappe_url': 'https://demo.erpnext.com',
            'api_key': 'demo_key',
            'api_secret': 'demo_secret',
            'doctype': 'Customer'
        },
        field_mappings=[],
        batch_size=1000
    )
    
    # Crear exportador
    exporter = DataExporter()
    
    print("Configuración del sistema:")
    print(f"  Sistema: {config.system_type.value}")
    print(f"  URL: {config.connection_params['frappe_url']}")
    print(f"  Tipo de documento: {config.connection_params['doctype']}")
    print(f"  Tamaño de lote: {config.batch_size}")
    
    # Nota: En un caso real, esto conectaría al sistema y exportaría datos
    print("\n⚠️  Nota: Esta es una simulación. En un entorno real,")
    print("   esto se conectaría al sistema ERPNext y exportaría los datos.")
    
    print("\n" + "=" * 50 + "\n")

def example_data_transformations():
    """Ejemplo: Transformaciones de datos"""
    print("🔄 Ejemplo 4: Transformaciones de datos")
    print("=" * 50)
    
    from data_integration.mappers import FieldMapper
    
    # Crear mapper con transformaciones
    mapper = FieldMapper()
    
    # Datos de prueba
    test_data = {
        'email_raw': '  CONTACT@COMPANY.COM  ',
        'phone_raw': '5551234567',
        'revenue_raw': '$1,250,000.50',
        'employees_raw': '150.0',
        'is_active_raw': 'yes',
        'date_raw': '01/15/2024'
    }
    
    # Mapeos con transformaciones
    mappings = [
        FieldMapping('email_raw', 'email', transform_function='email'),
        FieldMapping('phone_raw', 'phone', transform_function='phone'),
        FieldMapping('revenue_raw', 'revenue', transform_function='currency'),
        FieldMapping('employees_raw', 'employees', transform_function='int'),
        FieldMapping('is_active_raw', 'is_active', transform_function='bool'),
        FieldMapping('date_raw', 'creation_date', transform_function='date')
    ]
    
    # Aplicar transformaciones
    transformed = mapper.apply_mapping(test_data, mappings)
    
    print("Datos originales:")
    for key, value in test_data.items():
        print(f"  {key}: '{value}' ({type(value).__name__})")
    
    print("\nDatos transformados:")
    for key, value in transformed.items():
        print(f"  {key}: '{value}' ({type(value).__name__})")
    
    print("\n" + "=" * 50 + "\n")

def example_generate_mapping_template():
    """Ejemplo: Generar plantilla de mapeo automáticamente"""
    print("🤖 Ejemplo 5: Generación automática de mapeos")
    print("=" * 50)
    
    # Campos de ejemplo del sistema origen
    source_fields = [
        'company_name',
        'contact_email', 
        'primary_phone',
        'website_url',
        'billing_address',
        'billing_city',
        'billing_state',
        'billing_zip',
        'tax_id_number'
    ]
    
    # Generar mapeo automático para Odoo
    mapper = DataMapper()
    template_mappings = mapper.create_mapping_template(source_fields, SystemType.ODOO)
    
    print("Campos del sistema origen:")
    for field in source_fields:
        print(f"  - {field}")
    
    print(f"\nMapeos generados automáticamente para {SystemType.ODOO.value}:")
    for mapping in template_mappings:
        transform_info = f" (transform: {mapping.transform_function})" if mapping.transform_function else ""
        required_info = " [REQUERIDO]" if mapping.required else ""
        print(f"  {mapping.source_field} → {mapping.target_field}{transform_info}{required_info}")
    
    print("\n💡 Estos mapeos pueden guardarse en un archivo JSON y editarse según necesidades específicas.")
    
    print("\n" + "=" * 50 + "\n")

def example_validation_rules():
    """Ejemplo: Reglas de validación personalizadas"""
    print("✅ Ejemplo 6: Reglas de validación personalizadas")
    print("=" * 50)
    
    from data_integration.validators import DataValidator, ValidationRule
    
    # Crear validador
    validator = DataValidator()
    
    # Agregar validación personalizada
    def validate_business_hours(value):
        """Validar que las horas de negocio estén en formato correcto"""
        if not value:
            return True
        # Formato esperado: "09:00-17:00"
        import re
        pattern = r'^\d{2}:\d{2}-\d{2}:\d{2}$'
        return bool(re.match(pattern, str(value)))
    
    validator.schema_validator.add_custom_validator('business_hours', validate_business_hours)
    
    # Datos de prueba
    test_data = [
        {
            'name': 'Empresa Válida',
            'email': 'contacto@empresa.com',
            'business_hours': '09:00-17:00'  # Válido
        },
        {
            'name': '',  # Error: requerido
            'email': 'email-invalido',  # Error: formato email
            'business_hours': '9am-5pm'  # Error: formato incorrecto
        }
    ]
    
    # Reglas personalizadas
    custom_rules = {
        'business_hours': [
            ValidationRule('business_hours', 'custom', 'business_hours',
                         "Business hours must be in HH:MM-HH:MM format")
        ]
    }
    
    # Validar con reglas personalizadas
    result = validator.validate_for_system(test_data, SystemType.ODOO, custom_rules)
    
    # Mostrar resultados
    report = validator.create_validation_report(result)
    print(report)
    
    print("\n" + "=" * 50 + "\n")

def example_comprehensive_workflow():
    """Ejemplo: Flujo completo de trabajo"""
    print("🔄 Ejemplo 7: Flujo completo de trabajo")
    print("=" * 50)
    
    print("Simulando un flujo completo de importación:")
    print()
    
    # Paso 1: Cargar datos
    print("1️⃣  Cargando datos desde CSV...")
    sample_csv_data = [
        {
            'company_name': 'TechCorp Solutions',
            'email_address': 'hello@techcorp.com',
            'phone_number': '(555) 789-0123',
            'street_address': '789 Tech Boulevard',
            'city': 'San Francisco',
            'state': 'CA',
            'postal_code': '94107',
            'country': 'USA'
        }
    ]
    print(f"   ✅ Cargados {len(sample_csv_data)} registros")
    
    # Paso 2: Validar datos
    print("\n2️⃣  Validando datos...")
    validator = DataValidator()
    validation_result = validator.validate_for_system(sample_csv_data, SystemType.ODOO)
    
    if validation_result['valid']:
        print(f"   ✅ Todos los {validation_result['total_records']} registros son válidos")
    else:
        print(f"   ❌ {validation_result['invalid_records']} registros tienen errores")
        return
    
    # Paso 3: Mapear campos
    print("\n3️⃣  Mapeando campos para Odoo...")
    mapper = SystemMapper()
    odoo_mappings = mapper.get_odoo_customer_mapping()
    
    from data_integration.mappers import FieldMapper
    field_mapper = FieldMapper()
    
    mapped_data = []
    for record in sample_csv_data:
        mapped_record = field_mapper.apply_mapping(record, odoo_mappings)
        mapped_data.append(mapped_record)
    
    print(f"   ✅ Campos mapeados correctamente")
    print(f"   📋 Campos mapeados: {list(mapped_data[0].keys())}")
    
    # Paso 4: Simular importación
    print("\n4️⃣  Simulando importación a Odoo...")
    print("   ⚠️  En un entorno real, esto se conectaría a Odoo vía API")
    print("   🔗 URL: https://mi-instancia-odoo.com")
    print("   📊 Modelo: res.partner")
    print("   ✅ Importación simulada completada")
    
    # Paso 5: Resumen
    print("\n5️⃣  Resumen del proceso:")
    print(f"   📥 Registros procesados: {len(sample_csv_data)}")
    print(f"   ✅ Registros válidos: {validation_result['valid_records']}")
    print(f"   🗺️  Campos mapeados: {len(odoo_mappings)}")
    print(f"   📤 Listos para importar: {len(mapped_data)}")
    
    print("\n" + "=" * 50 + "\n")

def main():
    """Función principal que ejecuta todos los ejemplos"""
    print("🚀 NovaSuite-AI Data Integration - Ejemplos de Uso")
    print("=" * 60)
    print()
    
    try:
        # Ejecutar todos los ejemplos
        example_csv_validation()
        example_field_mapping()
        example_system_export_simulation()
        example_data_transformations()
        example_generate_mapping_template()
        example_validation_rules()
        example_comprehensive_workflow()
        
        print("🎉 Todos los ejemplos se ejecutaron correctamente!")
        print("\n💡 Para usar este módulo en tu aplicación:")
        print("   1. Configura las credenciales de tus sistemas")
        print("   2. Crea archivos de configuración JSON")
        print("   3. Usa la CLI o la API programática")
        print("   4. Siempre valida antes de importar")
        print("\n📚 Consulta README.md para documentación completa")
        
    except Exception as e:
        print(f"❌ Error ejecutando ejemplos: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()