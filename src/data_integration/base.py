"""
Base classes for data import and export functionality
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DataFormat(Enum):
    """Supported data formats"""
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    XLSX = "xlsx"


class SystemType(Enum):
    """Supported ERP/CRM systems"""
    ODOO = "odoo"
    ZOHO_CRM = "zoho_crm"
    ZOHO_BOOKS = "zoho_books"
    SAP_B1 = "sap_business_one"
    ERPNEXT = "erpnext"
    ESPOCRM = "espocrm"
    FIREFLY = "firefly_iii"


@dataclass
class ImportResult:
    """Result of an import operation"""
    success: bool
    total_records: int
    imported_records: int
    failed_records: int
    errors: List[str]
    warnings: List[str]
    execution_time: float


@dataclass
class ExportResult:
    """Result of an export operation"""
    success: bool
    total_records: int
    exported_records: int
    file_path: Optional[str]
    errors: List[str]
    execution_time: float


@dataclass
class FieldMapping:
    """Field mapping configuration"""
    source_field: str
    target_field: str
    transform_function: Optional[str] = None
    default_value: Any = None
    required: bool = False


@dataclass
class SystemConfig:
    """System configuration for import/export"""
    system_type: SystemType
    connection_params: Dict[str, Any]
    field_mappings: List[FieldMapping]
    batch_size: int = 1000


class BaseImporter(ABC):
    """Base class for all data importers"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate imported data"""
        pass
    
    @abstractmethod
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform data according to field mappings"""
        pass
    
    @abstractmethod
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import data into the target system"""
        pass
    
    def process_import(self, source_data: Any) -> ImportResult:
        """Main import process workflow"""
        try:
            # Parse source data
            parsed_data = self._parse_source_data(source_data)
            
            # Validate data
            validation_errors = self.validate_data(parsed_data)
            if validation_errors:
                return ImportResult(
                    success=False,
                    total_records=len(parsed_data),
                    imported_records=0,
                    failed_records=len(parsed_data),
                    errors=validation_errors,
                    warnings=[],
                    execution_time=0.0
                )
            
            # Transform data
            transformed_data = self.transform_data(parsed_data)
            
            # Import data
            return self.import_data(transformed_data)
            
        except Exception as e:
            self.logger.error(f"Import process failed: {str(e)}")
            return ImportResult(
                success=False,
                total_records=0,
                imported_records=0,
                failed_records=0,
                errors=[str(e)],
                warnings=[],
                execution_time=0.0
            )
    
    @abstractmethod
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse source data into standard format"""
        pass


class BaseExporter(ABC):
    """Base class for all data exporters"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from the source system"""
        pass
    
    @abstractmethod
    def format_data(self, data: List[Dict[str, Any]], format_type: DataFormat) -> Any:
        """Format data for export"""
        pass
    
    @abstractmethod
    def export_data(self, data: Any, output_path: str, format_type: DataFormat) -> ExportResult:
        """Export data to file"""
        pass
    
    def process_export(self, output_path: str, format_type: DataFormat, 
                      filters: Optional[Dict[str, Any]] = None) -> ExportResult:
        """Main export process workflow"""
        try:
            # Extract data
            raw_data = self.extract_data(filters)
            
            # Format data
            formatted_data = self.format_data(raw_data, format_type)
            
            # Export data
            return self.export_data(formatted_data, output_path, format_type)
            
        except Exception as e:
            self.logger.error(f"Export process failed: {str(e)}")
            return ExportResult(
                success=False,
                total_records=0,
                exported_records=0,
                file_path=None,
                errors=[str(e)],
                execution_time=0.0
            )


class DataTransformer:
    """Utility class for data transformations"""
    
    @staticmethod
    def apply_field_mapping(record: Dict[str, Any], mappings: List[FieldMapping]) -> Dict[str, Any]:
        """Apply field mappings to a single record"""
        transformed = {}
        
        for mapping in mappings:
            source_value = record.get(mapping.source_field)
            
            if source_value is None and mapping.default_value is not None:
                source_value = mapping.default_value
            
            if mapping.transform_function:
                # Apply transformation function if specified
                source_value = DataTransformer._apply_transform_function(
                    source_value, mapping.transform_function
                )
            
            transformed[mapping.target_field] = source_value
        
        return transformed
    
    @staticmethod
    def _apply_transform_function(value: Any, function_name: str) -> Any:
        """Apply a transformation function to a value"""
        transform_functions = {
            'upper': lambda x: str(x).upper() if x else x,
            'lower': lambda x: str(x).lower() if x else x,
            'strip': lambda x: str(x).strip() if x else x,
            'float': lambda x: float(x) if x else 0.0,
            'int': lambda x: int(float(x)) if x else 0,
            'bool': lambda x: bool(x) if x is not None else False,
        }
        
        if function_name in transform_functions:
            try:
                return transform_functions[function_name](value)
            except (ValueError, TypeError):
                return value
        
        return value