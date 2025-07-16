"""
NovaSuite-AI Data Integration Module

This module provides data import and export capabilities for various ERP systems
including Odoo, Zoho, SAP, and internal NovaSuite modules.

Supported formats:
- CSV files
- JSON files
- Direct database connections

Supported systems:
- Odoo
- Zoho CRM/Books
- SAP Business One
- ERPNext/Frappe
- EspoCRM
- Firefly III
"""

from .importers import (
    CSVImporter,
    JSONImporter,
    OdooImporter,
    ZohoImporter,
    SAPImporter
)

from .exporters import (
    JSONExporter,
    CSVExporter,
    DataExporter
)

from .mappers import (
    FieldMapper,
    DataMapper,
    SystemMapper
)

from .validators import (
    DataValidator,
    SchemaValidator
)

__version__ = "1.0.0"
__all__ = [
    "CSVImporter",
    "JSONImporter", 
    "OdooImporter",
    "ZohoImporter",
    "SAPImporter",
    "JSONExporter",
    "CSVExporter",
    "DataExporter",
    "FieldMapper",
    "DataMapper",
    "SystemMapper",
    "DataValidator",
    "SchemaValidator"
]