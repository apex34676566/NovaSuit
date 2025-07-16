"""
Data validators for ensuring data quality and compliance
"""

import re
from typing import Any, Dict, List, Optional, Set, Callable
from datetime import datetime, date
import logging

from .base import SystemType

logger = logging.getLogger(__name__)


class ValidationRule:
    """Represents a single validation rule"""
    
    def __init__(self, field: str, rule_type: str, rule_value: Any = None, 
                 message: str = None, required: bool = False):
        self.field = field
        self.rule_type = rule_type
        self.rule_value = rule_value
        self.message = message or f"Validation failed for field '{field}'"
        self.required = required


class SchemaValidator:
    """Validates data against predefined schemas"""
    
    def __init__(self):
        self.validators = {
            'required': self._validate_required,
            'type': self._validate_type,
            'length': self._validate_length,
            'min_length': self._validate_min_length,
            'max_length': self._validate_max_length,
            'pattern': self._validate_pattern,
            'email': self._validate_email,
            'phone': self._validate_phone,
            'url': self._validate_url,
            'date': self._validate_date,
            'datetime': self._validate_datetime,
            'range': self._validate_range,
            'min_value': self._validate_min_value,
            'max_value': self._validate_max_value,
            'in_list': self._validate_in_list,
            'unique': self._validate_unique,
            'currency': self._validate_currency,
            'tax_id': self._validate_tax_id,
            'custom': self._validate_custom,
        }
        self.custom_validators = {}
    
    def _validate_required(self, value: Any, rule_value: Any) -> bool:
        """Check if required field has a value"""
        return value is not None and value != ''
    
    def _validate_type(self, value: Any, rule_value: str) -> bool:
        """Check if value is of correct type"""
        if value is None:
            return True  # Type validation passes for None values
        
        type_map = {
            'str': str,
            'string': str,
            'int': int,
            'integer': int,
            'float': float,
            'number': (int, float),
            'bool': bool,
            'boolean': bool,
            'list': list,
            'dict': dict,
        }
        
        expected_type = type_map.get(rule_value.lower())
        if expected_type:
            return isinstance(value, expected_type)
        return True
    
    def _validate_length(self, value: Any, rule_value: int) -> bool:
        """Check if value has exact length"""
        if value is None:
            return True
        return len(str(value)) == rule_value
    
    def _validate_min_length(self, value: Any, rule_value: int) -> bool:
        """Check if value meets minimum length"""
        if value is None:
            return True
        return len(str(value)) >= rule_value
    
    def _validate_max_length(self, value: Any, rule_value: int) -> bool:
        """Check if value doesn't exceed maximum length"""
        if value is None:
            return True
        return len(str(value)) <= rule_value
    
    def _validate_pattern(self, value: Any, rule_value: str) -> bool:
        """Check if value matches regex pattern"""
        if value is None:
            return True
        return bool(re.match(rule_value, str(value)))
    
    def _validate_email(self, value: Any, rule_value: Any) -> bool:
        """Validate email format"""
        if value is None:
            return True
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, str(value).strip()))
    
    def _validate_phone(self, value: Any, rule_value: Any) -> bool:
        """Validate phone number format"""
        if value is None:
            return True
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(value))
        # Phone number should have 7-15 digits
        return 7 <= len(digits) <= 15
    
    def _validate_url(self, value: Any, rule_value: Any) -> bool:
        """Validate URL format"""
        if value is None:
            return True
        url_pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
        return bool(re.match(url_pattern, str(value).strip(), re.IGNORECASE))
    
    def _validate_date(self, value: Any, rule_value: Any) -> bool:
        """Validate date format"""
        if value is None:
            return True
        
        if isinstance(value, date):
            return True
        
        # Try common date formats
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
        for fmt in date_formats:
            try:
                datetime.strptime(str(value), fmt)
                return True
            except ValueError:
                continue
        return False
    
    def _validate_datetime(self, value: Any, rule_value: Any) -> bool:
        """Validate datetime format"""
        if value is None:
            return True
        
        if isinstance(value, datetime):
            return True
        
        # Try common datetime formats
        datetime_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%m/%d/%Y %H:%M:%S'
        ]
        for fmt in datetime_formats:
            try:
                datetime.strptime(str(value), fmt)
                return True
            except ValueError:
                continue
        return False
    
    def _validate_range(self, value: Any, rule_value: tuple) -> bool:
        """Check if numeric value is within range"""
        if value is None:
            return True
        try:
            num_value = float(value)
            min_val, max_val = rule_value
            return min_val <= num_value <= max_val
        except (ValueError, TypeError):
            return False
    
    def _validate_min_value(self, value: Any, rule_value: float) -> bool:
        """Check if value meets minimum"""
        if value is None:
            return True
        try:
            return float(value) >= rule_value
        except (ValueError, TypeError):
            return False
    
    def _validate_max_value(self, value: Any, rule_value: float) -> bool:
        """Check if value doesn't exceed maximum"""
        if value is None:
            return True
        try:
            return float(value) <= rule_value
        except (ValueError, TypeError):
            return False
    
    def _validate_in_list(self, value: Any, rule_value: list) -> bool:
        """Check if value is in allowed list"""
        if value is None:
            return True
        return value in rule_value
    
    def _validate_unique(self, value: Any, rule_value: Set) -> bool:
        """Check if value is unique (used with record context)"""
        if value is None:
            return True
        return value not in rule_value
    
    def _validate_currency(self, value: Any, rule_value: Any) -> bool:
        """Validate currency format"""
        if value is None:
            return True
        try:
            # Remove currency symbols and validate as number
            cleaned = re.sub(r'[$€£¥₹,\s]', '', str(value))
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def _validate_tax_id(self, value: Any, rule_value: str) -> bool:
        """Validate tax ID format based on country"""
        if value is None:
            return True
        
        value_str = str(value).replace('-', '').replace(' ', '')
        
        if rule_value == 'US':
            # US EIN format: XX-XXXXXXX
            return len(value_str) == 9 and value_str.isdigit()
        elif rule_value == 'EU':
            # EU VAT format: varies by country, but generally alphanumeric
            return len(value_str) >= 8 and len(value_str) <= 15
        elif rule_value == 'UK':
            # UK VAT format: GB followed by 9 digits
            return (value_str.startswith('GB') and len(value_str) == 11 and 
                   value_str[2:].isdigit())
        else:
            # Generic validation - alphanumeric, 5-20 characters
            return 5 <= len(value_str) <= 20 and value_str.isalnum()
    
    def _validate_custom(self, value: Any, rule_value: str) -> bool:
        """Apply custom validation function"""
        if rule_value in self.custom_validators:
            return self.custom_validators[rule_value](value)
        return True
    
    def add_custom_validator(self, name: str, validator_func: Callable[[Any], bool]):
        """Add a custom validation function"""
        self.custom_validators[name] = validator_func
    
    def validate_field(self, value: Any, rules: List[ValidationRule]) -> List[str]:
        """Validate a single field against multiple rules"""
        errors = []
        
        for rule in rules:
            # Check required first
            if rule.required and not self._validate_required(value, None):
                errors.append(f"Field '{rule.field}' is required")
                continue
            
            # Skip other validations if value is None/empty and not required
            if not rule.required and (value is None or value == ''):
                continue
            
            # Apply validation rule
            if rule.rule_type in self.validators:
                validator = self.validators[rule.rule_type]
                if not validator(value, rule.rule_value):
                    errors.append(rule.message)
        
        return errors
    
    def validate_record(self, record: Dict[str, Any], schema: Dict[str, List[ValidationRule]]) -> List[str]:
        """Validate a single record against a schema"""
        errors = []
        
        for field, rules in schema.items():
            value = record.get(field)
            field_errors = self.validate_field(value, rules)
            errors.extend(field_errors)
        
        return errors
    
    def validate_dataset(self, data: List[Dict[str, Any]], schema: Dict[str, List[ValidationRule]]) -> Dict[str, List[str]]:
        """Validate an entire dataset"""
        validation_results = {}
        unique_trackers = {}
        
        # Initialize unique value trackers
        for field, rules in schema.items():
            for rule in rules:
                if rule.rule_type == 'unique':
                    unique_trackers[field] = set()
        
        for i, record in enumerate(data):
            record_key = f"record_{i+1}"
            errors = []
            
            # First pass: collect unique values
            for field in unique_trackers:
                value = record.get(field)
                if value is not None:
                    if value in unique_trackers[field]:
                        errors.append(f"Field '{field}' value '{value}' is not unique")
                    else:
                        unique_trackers[field].add(value)
            
            # Validate against schema
            record_errors = self.validate_record(record, schema)
            errors.extend(record_errors)
            
            if errors:
                validation_results[record_key] = errors
        
        return validation_results


class DataValidator:
    """Main data validator with system-specific validation rules"""
    
    def __init__(self):
        self.schema_validator = SchemaValidator()
        self.system_schemas = self._initialize_system_schemas()
    
    def _initialize_system_schemas(self) -> Dict[SystemType, Dict[str, List[ValidationRule]]]:
        """Initialize validation schemas for different systems"""
        schemas = {}
        
        # Odoo validation schema
        schemas[SystemType.ODOO] = {
            'name': [
                ValidationRule('name', 'required', required=True),
                ValidationRule('name', 'max_length', 64, "Name cannot exceed 64 characters"),
            ],
            'email': [
                ValidationRule('email', 'email', message="Invalid email format"),
            ],
            'phone': [
                ValidationRule('phone', 'phone', message="Invalid phone format"),
            ],
            'vat': [
                ValidationRule('vat', 'pattern', r'^[A-Z]{2}[0-9A-Z]+$', "Invalid VAT format"),
            ],
            'is_company': [
                ValidationRule('is_company', 'type', 'bool', "is_company must be boolean"),
            ],
        }
        
        # Zoho CRM validation schema
        schemas[SystemType.ZOHO_CRM] = {
            'Last_Name': [
                ValidationRule('Last_Name', 'required', required=True),
                ValidationRule('Last_Name', 'max_length', 120, "Last Name cannot exceed 120 characters"),
            ],
            'Email': [
                ValidationRule('Email', 'email', message="Invalid email format"),
            ],
            'Phone': [
                ValidationRule('Phone', 'phone', message="Invalid phone format"),
            ],
            'Annual_Revenue': [
                ValidationRule('Annual_Revenue', 'currency', message="Invalid currency format"),
                ValidationRule('Annual_Revenue', 'min_value', 0, "Annual revenue cannot be negative"),
            ],
            'No_of_Employees': [
                ValidationRule('No_of_Employees', 'type', 'int', "Number of employees must be integer"),
                ValidationRule('No_of_Employees', 'min_value', 0, "Number of employees cannot be negative"),
            ],
        }
        
        # SAP Business One validation schema
        schemas[SystemType.SAP_B1] = {
            'CardCode': [
                ValidationRule('CardCode', 'required', required=True),
                ValidationRule('CardCode', 'max_length', 15, "CardCode cannot exceed 15 characters"),
                ValidationRule('CardCode', 'pattern', r'^[A-Z0-9]+$', "CardCode must be alphanumeric uppercase"),
                ValidationRule('CardCode', 'unique', message="CardCode must be unique"),
            ],
            'CardName': [
                ValidationRule('CardName', 'required', required=True),
                ValidationRule('CardName', 'max_length', 100, "CardName cannot exceed 100 characters"),
            ],
            'E_Mail': [
                ValidationRule('E_Mail', 'email', message="Invalid email format"),
            ],
            'Phone1': [
                ValidationRule('Phone1', 'phone', message="Invalid phone format"),
            ],
            'FederalTaxID': [
                ValidationRule('FederalTaxID', 'tax_id', 'US', "Invalid tax ID format"),
            ],
        }
        
        # ERPNext validation schema
        schemas[SystemType.ERPNEXT] = {
            'customer_name': [
                ValidationRule('customer_name', 'required', required=True),
                ValidationRule('customer_name', 'max_length', 140, "Customer name cannot exceed 140 characters"),
                ValidationRule('customer_name', 'unique', message="Customer name must be unique"),
            ],
            'email_id': [
                ValidationRule('email_id', 'email', message="Invalid email format"),
            ],
            'mobile_no': [
                ValidationRule('mobile_no', 'phone', message="Invalid mobile number format"),
            ],
            'customer_type': [
                ValidationRule('customer_type', 'in_list', ['Company', 'Individual'], 
                             "Customer type must be Company or Individual"),
            ],
            'default_currency': [
                ValidationRule('default_currency', 'length', 3, "Currency code must be 3 characters"),
                ValidationRule('default_currency', 'pattern', r'^[A-Z]{3}$', "Currency code must be uppercase letters"),
            ],
        }
        
        # EspoCRM validation schema
        schemas[SystemType.ESPOCRM] = {
            'lastName': [
                ValidationRule('lastName', 'required', required=True),
                ValidationRule('lastName', 'max_length', 100, "Last name cannot exceed 100 characters"),
            ],
            'emailAddress': [
                ValidationRule('emailAddress', 'email', message="Invalid email format"),
            ],
            'phoneNumber': [
                ValidationRule('phoneNumber', 'phone', message="Invalid phone format"),
            ],
            'website': [
                ValidationRule('website', 'url', message="Invalid website URL format"),
            ],
        }
        
        # Firefly III validation schema
        schemas[SystemType.FIREFLY] = {
            'name': [
                ValidationRule('name', 'required', required=True),
                ValidationRule('name', 'max_length', 255, "Name cannot exceed 255 characters"),
            ],
            'type': [
                ValidationRule('type', 'in_list', ['asset', 'expense', 'revenue', 'liability'], 
                             "Invalid account type"),
            ],
            'currency_code': [
                ValidationRule('currency_code', 'length', 3, "Currency code must be 3 characters"),
                ValidationRule('currency_code', 'pattern', r'^[A-Z]{3}$', "Currency code must be uppercase letters"),
            ],
        }
        
        return schemas
    
    def validate_for_system(self, data: List[Dict[str, Any]], system_type: SystemType, 
                          custom_rules: Optional[Dict[str, List[ValidationRule]]] = None) -> Dict[str, Any]:
        """Validate data for a specific system"""
        
        # Get system schema
        schema = self.system_schemas.get(system_type, {})
        
        # Add custom rules if provided
        if custom_rules:
            for field, rules in custom_rules.items():
                if field in schema:
                    schema[field].extend(rules)
                else:
                    schema[field] = rules
        
        # Validate data
        validation_results = self.schema_validator.validate_dataset(data, schema)
        
        # Calculate summary statistics
        total_records = len(data)
        invalid_records = len(validation_results)
        valid_records = total_records - invalid_records
        
        # Count error types
        error_summary = {}
        for record_errors in validation_results.values():
            for error in record_errors:
                error_type = error.split(':')[0] if ':' in error else error
                error_summary[error_type] = error_summary.get(error_type, 0) + 1
        
        return {
            'valid': invalid_records == 0,
            'total_records': total_records,
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'validation_errors': validation_results,
            'error_summary': error_summary,
            'system_type': system_type.value
        }
    
    def validate_field_mapping(self, source_data: List[Dict[str, Any]], 
                             field_mappings: List, target_system: SystemType) -> List[str]:
        """Validate that field mappings will work correctly"""
        errors = []
        
        if not source_data:
            errors.append("No source data provided for validation")
            return errors
        
        # Get available source fields
        source_fields = set()
        for record in source_data[:10]:  # Check first 10 records
            source_fields.update(record.keys())
        
        # Check if mapped source fields exist
        for mapping in field_mappings:
            if hasattr(mapping, 'source_field') and mapping.source_field not in source_fields:
                errors.append(f"Source field '{mapping.source_field}' not found in data")
        
        # Check required fields for target system
        target_schema = self.system_schemas.get(target_system, {})
        required_fields = []
        for field, rules in target_schema.items():
            for rule in rules:
                if rule.required:
                    required_fields.append(field)
                    break
        
        mapped_target_fields = {getattr(mapping, 'target_field', '') for mapping in field_mappings if hasattr(mapping, 'target_field')}
        
        for required_field in required_fields:
            if required_field not in mapped_target_fields:
                errors.append(f"Required target field '{required_field}' is not mapped")
        
        return errors
    
    def create_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Create a human-readable validation report"""
        
        report = []
        report.append("=== Data Validation Report ===")
        report.append(f"System: {validation_result['system_type']}")
        report.append(f"Total Records: {validation_result['total_records']}")
        report.append(f"Valid Records: {validation_result['valid_records']}")
        report.append(f"Invalid Records: {validation_result['invalid_records']}")
        report.append(f"Overall Status: {'PASSED' if validation_result['valid'] else 'FAILED'}")
        report.append("")
        
        if validation_result['error_summary']:
            report.append("Error Summary:")
            for error_type, count in validation_result['error_summary'].items():
                report.append(f"  - {error_type}: {count} occurrences")
            report.append("")
        
        if validation_result['validation_errors']:
            report.append("Detailed Errors:")
            for record_id, errors in validation_result['validation_errors'].items():
                report.append(f"  {record_id}:")
                for error in errors:
                    report.append(f"    - {error}")
            report.append("")
        
        return "\n".join(report)