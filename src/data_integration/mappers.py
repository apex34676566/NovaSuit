"""
Data mappers for field mapping and system-specific transformations
"""

from typing import Any, Dict, List, Optional, Callable
import logging
from datetime import datetime, date
import re

from .base import FieldMapping, SystemType

logger = logging.getLogger(__name__)


class FieldMapper:
    """Handles field mapping between different systems"""
    
    def __init__(self):
        self.transform_functions = {
            'upper': lambda x: str(x).upper() if x else x,
            'lower': lambda x: str(x).lower() if x else x,
            'strip': lambda x: str(x).strip() if x else x,
            'title': lambda x: str(x).title() if x else x,
            'float': self._to_float,
            'int': self._to_int,
            'bool': self._to_bool,
            'date': self._to_date,
            'datetime': self._to_datetime,
            'phone': self._format_phone,
            'email': self._format_email,
            'currency': self._format_currency,
        }
    
    def _to_float(self, value: Any) -> float:
        """Convert value to float"""
        if value is None or value == '':
            return 0.0
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                cleaned = re.sub(r'[^\d.-]', '', value)
                return float(cleaned) if cleaned else 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _to_int(self, value: Any) -> int:
        """Convert value to integer"""
        if value is None or value == '':
            return 0
        try:
            if isinstance(value, str):
                cleaned = re.sub(r'[^\d-]', '', value)
                return int(float(cleaned)) if cleaned else 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _to_bool(self, value: Any) -> bool:
        """Convert value to boolean"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 't', 'yes', 'y', '1', 'on', 'active')
        return bool(value)
    
    def _to_date(self, value: Any) -> Optional[str]:
        """Convert value to date string (YYYY-MM-DD)"""
        if not value:
            return None
        
        try:
            if isinstance(value, date):
                return value.isoformat()
            elif isinstance(value, datetime):
                return value.date().isoformat()
            elif isinstance(value, str):
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                    try:
                        parsed_date = datetime.strptime(value, fmt).date()
                        return parsed_date.isoformat()
                    except ValueError:
                        continue
                # If no format matches, return original
                return value
            else:
                return str(value)
        except Exception:
            return None
    
    def _to_datetime(self, value: Any) -> Optional[str]:
        """Convert value to datetime string (ISO format)"""
        if not value:
            return None
        
        try:
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, date):
                return datetime.combine(value, datetime.min.time()).isoformat()
            elif isinstance(value, str):
                # Try common datetime formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        parsed_datetime = datetime.strptime(value, fmt)
                        return parsed_datetime.isoformat()
                    except ValueError:
                        continue
                # If no format matches, return original
                return value
            else:
                return str(value)
        except Exception:
            return None
    
    def _format_phone(self, value: Any) -> Optional[str]:
        """Format phone number"""
        if not value:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(value))
        
        if len(digits) == 10:
            # US format: (123) 456-7890
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            # US format with country code: +1 (123) 456-7890
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            # International format: +XX XXXXXXXX
            return f"+{digits}"
    
    def _format_email(self, value: Any) -> Optional[str]:
        """Format and validate email"""
        if not value:
            return None
        
        email = str(value).strip().lower()
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, email):
            return email
        else:
            return None
    
    def _format_currency(self, value: Any) -> float:
        """Format currency value"""
        if not value:
            return 0.0
        
        try:
            # Remove currency symbols and formatting
            if isinstance(value, str):
                # Remove common currency symbols and commas
                cleaned = re.sub(r'[$€£¥₹,\s]', '', value)
                return float(cleaned) if cleaned else 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def apply_mapping(self, record: Dict[str, Any], mappings: List[FieldMapping]) -> Dict[str, Any]:
        """Apply field mappings to a record"""
        mapped_record = {}
        
        for mapping in mappings:
            source_value = record.get(mapping.source_field)
            
            # Use default value if source is empty
            if (source_value is None or source_value == '') and mapping.default_value is not None:
                source_value = mapping.default_value
            
            # Apply transformation function if specified
            if mapping.transform_function and source_value is not None:
                if mapping.transform_function in self.transform_functions:
                    source_value = self.transform_functions[mapping.transform_function](source_value)
                else:
                    logger.warning(f"Unknown transform function: {mapping.transform_function}")
            
            mapped_record[mapping.target_field] = source_value
        
        return mapped_record
    
    def add_custom_transform(self, name: str, function: Callable[[Any], Any]):
        """Add a custom transformation function"""
        self.transform_functions[name] = function


class SystemMapper:
    """Predefined field mappings for common system integrations"""
    
    @staticmethod
    def get_odoo_customer_mapping() -> List[FieldMapping]:
        """Standard mapping for Odoo customer import"""
        return [
            FieldMapping('name', 'name', required=True),
            FieldMapping('company_name', 'name', required=True),
            FieldMapping('email', 'email', transform_function='email'),
            FieldMapping('phone', 'phone', transform_function='phone'),
            FieldMapping('mobile', 'mobile', transform_function='phone'),
            FieldMapping('street', 'street'),
            FieldMapping('city', 'city'),
            FieldMapping('state', 'state_id'),
            FieldMapping('zip', 'zip'),
            FieldMapping('country', 'country_id'),
            FieldMapping('vat', 'vat'),
            FieldMapping('is_company', 'is_company', transform_function='bool', default_value=True),
            FieldMapping('customer', 'customer', transform_function='bool', default_value=True),
            FieldMapping('supplier', 'supplier', transform_function='bool', default_value=False),
        ]
    
    @staticmethod
    def get_zoho_lead_mapping() -> List[FieldMapping]:
        """Standard mapping for Zoho Leads import"""
        return [
            FieldMapping('first_name', 'First_Name'),
            FieldMapping('last_name', 'Last_Name', required=True),
            FieldMapping('company', 'Company', required=True),
            FieldMapping('email', 'Email', transform_function='email'),
            FieldMapping('phone', 'Phone', transform_function='phone'),
            FieldMapping('mobile', 'Mobile', transform_function='phone'),
            FieldMapping('website', 'Website'),
            FieldMapping('industry', 'Industry'),
            FieldMapping('lead_source', 'Lead_Source'),
            FieldMapping('lead_status', 'Lead_Status', default_value='Not Contacted'),
            FieldMapping('rating', 'Rating'),
            FieldMapping('annual_revenue', 'Annual_Revenue', transform_function='currency'),
            FieldMapping('no_of_employees', 'No_of_Employees', transform_function='int'),
            FieldMapping('street', 'Street'),
            FieldMapping('city', 'City'),
            FieldMapping('state', 'State'),
            FieldMapping('zip_code', 'Zip_Code'),
            FieldMapping('country', 'Country'),
        ]
    
    @staticmethod
    def get_sap_business_partner_mapping() -> List[FieldMapping]:
        """Standard mapping for SAP Business Partner import"""
        return [
            FieldMapping('card_code', 'CardCode', required=True),
            FieldMapping('card_name', 'CardName', required=True),
            FieldMapping('card_type', 'CardType', default_value='cCustomer'),
            FieldMapping('group_code', 'GroupCode', default_value=100),
            FieldMapping('currency', 'Currency', default_value='USD'),
            FieldMapping('phone1', 'Phone1', transform_function='phone'),
            FieldMapping('phone2', 'Phone2', transform_function='phone'),
            FieldMapping('cellular', 'Cellular', transform_function='phone'),
            FieldMapping('email', 'E_Mail', transform_function='email'),
            FieldMapping('website', 'Website'),
            FieldMapping('federal_tax_id', 'FederalTaxID'),
            FieldMapping('valid', 'Valid', transform_function='bool', default_value=True),
            FieldMapping('frozen', 'Frozen', transform_function='bool', default_value=False),
        ]
    
    @staticmethod
    def get_erpnext_customer_mapping() -> List[FieldMapping]:
        """Standard mapping for ERPNext Customer import"""
        return [
            FieldMapping('customer_name', 'customer_name', required=True),
            FieldMapping('customer_type', 'customer_type', default_value='Company'),
            FieldMapping('customer_group', 'customer_group', default_value='All Customer Groups'),
            FieldMapping('territory', 'territory', default_value='All Territories'),
            FieldMapping('email_id', 'email_id', transform_function='email'),
            FieldMapping('mobile_no', 'mobile_no', transform_function='phone'),
            FieldMapping('website', 'website'),
            FieldMapping('tax_id', 'tax_id'),
            FieldMapping('tax_category', 'tax_category'),
            FieldMapping('default_currency', 'default_currency', default_value='USD'),
            FieldMapping('is_frozen', 'is_frozen', transform_function='bool', default_value=False),
            FieldMapping('disabled', 'disabled', transform_function='bool', default_value=False),
        ]
    
    @staticmethod
    def get_espo_contact_mapping() -> List[FieldMapping]:
        """Standard mapping for EspoCRM Contact import"""
        return [
            FieldMapping('first_name', 'firstName'),
            FieldMapping('last_name', 'lastName', required=True),
            FieldMapping('account_name', 'accountName'),
            FieldMapping('title', 'title'),
            FieldMapping('email', 'emailAddress', transform_function='email'),
            FieldMapping('phone_number', 'phoneNumber', transform_function='phone'),
            FieldMapping('mobile_number', 'phoneNumberMobile', transform_function='phone'),
            FieldMapping('office_phone', 'phoneNumberOffice', transform_function='phone'),
            FieldMapping('fax', 'phoneNumberFax', transform_function='phone'),
            FieldMapping('website', 'website'),
            FieldMapping('address_street', 'addressStreet'),
            FieldMapping('address_city', 'addressCity'),
            FieldMapping('address_state', 'addressState'),
            FieldMapping('address_postal_code', 'addressPostalCode'),
            FieldMapping('address_country', 'addressCountry'),
            FieldMapping('description', 'description'),
        ]


class DataMapper:
    """Advanced data mapping with business logic"""
    
    def __init__(self):
        self.field_mapper = FieldMapper()
        self.system_mapper = SystemMapper()
    
    def map_system_to_system(self, source_data: List[Dict[str, Any]], 
                           source_system: SystemType, target_system: SystemType,
                           custom_mappings: Optional[List[FieldMapping]] = None) -> List[Dict[str, Any]]:
        """Map data from one system to another"""
        
        # Get standard mappings based on target system
        if target_system == SystemType.ODOO:
            mappings = self.system_mapper.get_odoo_customer_mapping()
        elif target_system == SystemType.ZOHO_CRM:
            mappings = self.system_mapper.get_zoho_lead_mapping()
        elif target_system == SystemType.SAP_B1:
            mappings = self.system_mapper.get_sap_business_partner_mapping()
        elif target_system == SystemType.ERPNEXT:
            mappings = self.system_mapper.get_erpnext_customer_mapping()
        elif target_system == SystemType.ESPOCRM:
            mappings = self.system_mapper.get_espo_contact_mapping()
        else:
            mappings = custom_mappings or []
        
        # Apply custom mappings if provided
        if custom_mappings:
            # Merge or override standard mappings
            mapping_dict = {m.target_field: m for m in mappings}
            for custom_mapping in custom_mappings:
                mapping_dict[custom_mapping.target_field] = custom_mapping
            mappings = list(mapping_dict.values())
        
        # Apply mappings to all records
        mapped_data = []
        for record in source_data:
            mapped_record = self.field_mapper.apply_mapping(record, mappings)
            
            # Apply system-specific business logic
            mapped_record = self._apply_system_business_logic(mapped_record, target_system)
            
            mapped_data.append(mapped_record)
        
        return mapped_data
    
    def _apply_system_business_logic(self, record: Dict[str, Any], target_system: SystemType) -> Dict[str, Any]:
        """Apply system-specific business logic"""
        
        if target_system == SystemType.ODOO:
            # Odoo-specific logic
            if 'is_company' not in record:
                # Determine if it's a company based on data
                record['is_company'] = bool(record.get('name') and not record.get('first_name'))
            
            # Set customer/supplier flags
            if 'customer' not in record:
                record['customer'] = True
            if 'supplier' not in record:
                record['supplier'] = False
        
        elif target_system == SystemType.ZOHO_CRM:
            # Zoho-specific logic
            if not record.get('Lead_Status'):
                record['Lead_Status'] = 'Not Contacted'
            
            # Ensure required fields have values
            if not record.get('Last_Name') and record.get('Company'):
                record['Last_Name'] = record['Company']
        
        elif target_system == SystemType.SAP_B1:
            # SAP-specific logic
            if not record.get('CardCode'):
                # Generate CardCode from name
                name = record.get('CardName', '')
                record['CardCode'] = re.sub(r'[^A-Z0-9]', '', name.upper())[:15]
            
            # Set default values
            if 'Valid' not in record:
                record['Valid'] = 'tYES'
            if 'CardType' not in record:
                record['CardType'] = 'cCustomer'
        
        elif target_system == SystemType.ERPNEXT:
            # ERPNext-specific logic
            if not record.get('customer_group'):
                record['customer_group'] = 'All Customer Groups'
            if not record.get('territory'):
                record['territory'] = 'All Territories'
            if not record.get('customer_type'):
                record['customer_type'] = 'Company' if not record.get('first_name') else 'Individual'
        
        elif target_system == SystemType.ESPOCRM:
            # EspoCRM-specific logic
            if not record.get('lastName') and record.get('accountName'):
                record['lastName'] = record['accountName']
        
        return record
    
    def create_mapping_template(self, source_fields: List[str], target_system: SystemType) -> List[FieldMapping]:
        """Create a mapping template for manual configuration"""
        
        # Get target fields based on system
        if target_system == SystemType.ODOO:
            target_mappings = self.system_mapper.get_odoo_customer_mapping()
        elif target_system == SystemType.ZOHO_CRM:
            target_mappings = self.system_mapper.get_zoho_lead_mapping()
        elif target_system == SystemType.SAP_B1:
            target_mappings = self.system_mapper.get_sap_business_partner_mapping()
        elif target_system == SystemType.ERPNEXT:
            target_mappings = self.system_mapper.get_erpnext_customer_mapping()
        elif target_system == SystemType.ESPOCRM:
            target_mappings = self.system_mapper.get_espo_contact_mapping()
        else:
            target_mappings = []
        
        # Create template mappings
        template_mappings = []
        target_fields = {m.target_field: m for m in target_mappings}
        
        for source_field in source_fields:
            # Try to find matching target field
            matched_target = None
            source_lower = source_field.lower()
            
            for target_field, mapping in target_fields.items():
                target_lower = target_field.lower()
                if (source_lower == target_lower or 
                    source_lower in target_lower or 
                    target_lower in source_lower):
                    matched_target = mapping
                    break
            
            if matched_target:
                template_mappings.append(FieldMapping(
                    source_field=source_field,
                    target_field=matched_target.target_field,
                    transform_function=matched_target.transform_function,
                    default_value=matched_target.default_value,
                    required=matched_target.required
                ))
            else:
                # Create a basic mapping
                template_mappings.append(FieldMapping(
                    source_field=source_field,
                    target_field=source_field,  # Use same name as fallback
                    required=False
                ))
        
        return template_mappings