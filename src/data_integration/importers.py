"""
Data importers for various file formats and ERP systems
"""

import csv
import json
import pandas as pd
import requests
import time
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

from .base import (
    BaseImporter, ImportResult, SystemConfig, DataTransformer,
    DataFormat, SystemType
)

logger = logging.getLogger(__name__)


class CSVImporter(BaseImporter):
    """Importer for CSV files"""
    
    def __init__(self, config: SystemConfig, csv_file_path: str, delimiter: str = ','):
        super().__init__(config)
        self.csv_file_path = csv_file_path
        self.delimiter = delimiter
    
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse CSV file into list of dictionaries"""
        try:
            df = pd.read_csv(self.csv_file_path, delimiter=self.delimiter)
            # Convert NaN to None for better JSON compatibility
            df = df.where(pd.notna(df), None)
            return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"Failed to parse CSV file: {str(e)}")
            raise
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate CSV data"""
        errors = []
        
        if not data:
            errors.append("No data found in CSV file")
            return errors
        
        # Check required fields
        required_fields = [mapping.source_field for mapping in self.config.field_mappings if mapping.required]
        
        for i, record in enumerate(data):
            for field in required_fields:
                if field not in record or record[field] is None or record[field] == '':
                    errors.append(f"Row {i+1}: Required field '{field}' is missing or empty")
        
        return errors
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform CSV data according to field mappings"""
        transformed_data = []
        
        for record in data:
            transformed_record = DataTransformer.apply_field_mapping(record, self.config.field_mappings)
            transformed_data.append(transformed_record)
        
        return transformed_data
    
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import transformed data (to be implemented by specific target system)"""
        # This is a base implementation - should be overridden by specific importers
        start_time = time.time()
        
        # Simulate import process
        imported_count = len(data)
        
        end_time = time.time()
        
        return ImportResult(
            success=True,
            total_records=len(data),
            imported_records=imported_count,
            failed_records=0,
            errors=[],
            warnings=[],
            execution_time=end_time - start_time
        )


class JSONImporter(BaseImporter):
    """Importer for JSON files"""
    
    def __init__(self, config: SystemConfig, json_file_path: str):
        super().__init__(config)
        self.json_file_path = json_file_path
    
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse JSON file into list of dictionaries"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Handle different JSON structures
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # If it's a dict, look for common array keys
                for key in ['data', 'records', 'items', 'results']:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                # If no array found, wrap the dict in a list
                return [data]
            else:
                raise ValueError("Invalid JSON structure")
                
        except Exception as e:
            self.logger.error(f"Failed to parse JSON file: {str(e)}")
            raise
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate JSON data"""
        errors = []
        
        if not data:
            errors.append("No data found in JSON file")
            return errors
        
        # Check required fields
        required_fields = [mapping.source_field for mapping in self.config.field_mappings if mapping.required]
        
        for i, record in enumerate(data):
            if not isinstance(record, dict):
                errors.append(f"Record {i+1}: Expected dictionary, got {type(record)}")
                continue
                
            for field in required_fields:
                if field not in record or record[field] is None:
                    errors.append(f"Record {i+1}: Required field '{field}' is missing or null")
        
        return errors
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform JSON data according to field mappings"""
        transformed_data = []
        
        for record in data:
            transformed_record = DataTransformer.apply_field_mapping(record, self.config.field_mappings)
            transformed_data.append(transformed_record)
        
        return transformed_data
    
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import transformed data (to be implemented by specific target system)"""
        # This is a base implementation - should be overridden by specific importers
        start_time = time.time()
        
        # Simulate import process
        imported_count = len(data)
        
        end_time = time.time()
        
        return ImportResult(
            success=True,
            total_records=len(data),
            imported_records=imported_count,
            failed_records=0,
            errors=[],
            warnings=[],
            execution_time=end_time - start_time
        )


class OdooImporter(BaseImporter):
    """Importer for Odoo system data"""
    
    def __init__(self, config: SystemConfig, odoo_url: str, database: str, 
                 username: str, password: str, model: str):
        super().__init__(config)
        self.odoo_url = odoo_url
        self.database = database
        self.username = username
        self.password = password
        self.model = model
        self.uid = None
        self.session = requests.Session()
    
    def _authenticate(self) -> bool:
        """Authenticate with Odoo"""
        try:
            # Odoo authentication via JSON-RPC
            auth_data = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'service': 'common',
                    'method': 'authenticate',
                    'args': [self.database, self.username, self.password, {}]
                },
                'id': 1
            }
            
            response = self.session.post(f"{self.odoo_url}/jsonrpc", json=auth_data)
            result = response.json()
            
            if 'result' in result and result['result']:
                self.uid = result['result']
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Odoo authentication failed: {str(e)}")
            return False
    
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse source data (for Odoo, this would typically be from file or API)"""
        if isinstance(source_data, str):
            # Assume it's a file path
            if source_data.endswith('.json'):
                json_importer = JSONImporter(self.config, source_data)
                return json_importer._parse_source_data(source_data)
            elif source_data.endswith('.csv'):
                csv_importer = CSVImporter(self.config, source_data)
                return csv_importer._parse_source_data(source_data)
        
        return source_data if isinstance(source_data, list) else [source_data]
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate data for Odoo import"""
        errors = []
        
        if not data:
            errors.append("No data to import")
            return errors
        
        # Odoo-specific validation
        for i, record in enumerate(data):
            # Check for required Odoo fields
            if 'name' in record and not record['name']:
                errors.append(f"Record {i+1}: 'name' field is required for most Odoo models")
        
        return errors
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform data for Odoo format"""
        transformed_data = []
        
        for record in data:
            transformed_record = DataTransformer.apply_field_mapping(record, self.config.field_mappings)
            
            # Odoo-specific transformations
            if 'active' not in transformed_record:
                transformed_record['active'] = True
            
            transformed_data.append(transformed_record)
        
        return transformed_data
    
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import data into Odoo"""
        start_time = time.time()
        
        if not self._authenticate():
            return ImportResult(
                success=False,
                total_records=len(data),
                imported_records=0,
                failed_records=len(data),
                errors=["Odoo authentication failed"],
                warnings=[],
                execution_time=0.0
            )
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        # Process data in batches
        batch_size = self.config.batch_size
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            try:
                # Create records via JSON-RPC
                create_data = {
                    'jsonrpc': '2.0',
                    'method': 'call',
                    'params': {
                        'service': 'object',
                        'method': 'execute_kw',
                        'args': [
                            self.database, self.uid, self.password,
                            self.model, 'create', [batch]
                        ]
                    },
                    'id': i // batch_size + 1
                }
                
                response = self.session.post(f"{self.odoo_url}/jsonrpc", json=create_data)
                result = response.json()
                
                if 'error' in result:
                    errors.append(f"Batch {i//batch_size + 1}: {result['error']['message']}")
                    failed_count += len(batch)
                else:
                    imported_count += len(batch)
                    
            except Exception as e:
                errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
                failed_count += len(batch)
        
        end_time = time.time()
        
        return ImportResult(
            success=imported_count > 0,
            total_records=len(data),
            imported_records=imported_count,
            failed_records=failed_count,
            errors=errors,
            warnings=[],
            execution_time=end_time - start_time
        )


class ZohoImporter(BaseImporter):
    """Importer for Zoho CRM/Books data"""
    
    def __init__(self, config: SystemConfig, access_token: str, refresh_token: str,
                 client_id: str, client_secret: str, module: str, 
                 api_domain: str = "https://www.zohoapis.com"):
        super().__init__(config)
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.module = module
        self.api_domain = api_domain
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Zoho-oauthtoken {self.access_token}',
            'Content-Type': 'application/json'
        })
    
    def _refresh_access_token(self) -> bool:
        """Refresh Zoho access token"""
        try:
            refresh_data = {
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(
                'https://accounts.zoho.com/oauth/v2/token',
                data=refresh_data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.session.headers.update({
                    'Authorization': f'Zoho-oauthtoken {self.access_token}'
                })
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to refresh Zoho token: {str(e)}")
            return False
    
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse source data for Zoho import"""
        if isinstance(source_data, str):
            # Assume it's a file path
            if source_data.endswith('.json'):
                json_importer = JSONImporter(self.config, source_data)
                return json_importer._parse_source_data(source_data)
            elif source_data.endswith('.csv'):
                csv_importer = CSVImporter(self.config, source_data)
                return csv_importer._parse_source_data(source_data)
        
        return source_data if isinstance(source_data, list) else [source_data]
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate data for Zoho import"""
        errors = []
        
        if not data:
            errors.append("No data to import")
            return errors
        
        # Zoho-specific validation
        for i, record in enumerate(data):
            # Most Zoho modules require at least a name or email
            if self.module.lower() in ['leads', 'contacts', 'accounts']:
                if not any(field in record for field in ['Last_Name', 'Company', 'Email']):
                    errors.append(f"Record {i+1}: At least one of Last_Name, Company, or Email is required")
        
        return errors
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform data for Zoho format"""
        transformed_data = []
        
        for record in data:
            transformed_record = DataTransformer.apply_field_mapping(record, self.config.field_mappings)
            transformed_data.append(transformed_record)
        
        return transformed_data
    
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import data into Zoho"""
        start_time = time.time()
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        # Process data in batches (Zoho allows up to 100 records per request)
        batch_size = min(self.config.batch_size, 100)
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            try:
                # Create records via Zoho API
                create_data = {
                    'data': batch,
                    'trigger': ['approval', 'workflow', 'blueprint']
                }
                
                response = self.session.post(
                    f"{self.api_domain}/crm/v2/{self.module}",
                    json=create_data
                )
                
                if response.status_code == 401:
                    # Token expired, try to refresh
                    if self._refresh_access_token():
                        response = self.session.post(
                            f"{self.api_domain}/crm/v2/{self.module}",
                            json=create_data
                        )
                
                result = response.json()
                
                if response.status_code == 201:
                    # Success
                    for record_result in result.get('data', []):
                        if record_result.get('status') == 'success':
                            imported_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"Record failed: {record_result.get('message', 'Unknown error')}")
                else:
                    errors.append(f"Batch {i//batch_size + 1}: {result.get('message', 'Unknown error')}")
                    failed_count += len(batch)
                    
            except Exception as e:
                errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
                failed_count += len(batch)
        
        end_time = time.time()
        
        return ImportResult(
            success=imported_count > 0,
            total_records=len(data),
            imported_records=imported_count,
            failed_records=failed_count,
            errors=errors,
            warnings=[],
            execution_time=end_time - start_time
        )


class SAPImporter(BaseImporter):
    """Importer for SAP Business One data"""
    
    def __init__(self, config: SystemConfig, server_url: str, company_db: str,
                 username: str, password: str, object_type: str):
        super().__init__(config)
        self.server_url = server_url
        self.company_db = company_db
        self.username = username
        self.password = password
        self.object_type = object_type
        self.session_id = None
        self.session = requests.Session()
    
    def _authenticate(self) -> bool:
        """Authenticate with SAP Business One"""
        try:
            auth_data = {
                'CompanyDB': self.company_db,
                'Password': self.password,
                'UserName': self.username
            }
            
            response = self.session.post(
                f"{self.server_url}/Login",
                json=auth_data
            )
            
            if response.status_code == 200:
                result = response.json()
                self.session_id = result.get('SessionId')
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"SAP authentication failed: {str(e)}")
            return False
    
    def _parse_source_data(self, source_data: Any) -> List[Dict[str, Any]]:
        """Parse source data for SAP import"""
        if isinstance(source_data, str):
            # Assume it's a file path
            if source_data.endswith('.json'):
                json_importer = JSONImporter(self.config, source_data)
                return json_importer._parse_source_data(source_data)
            elif source_data.endswith('.csv'):
                csv_importer = CSVImporter(self.config, source_data)
                return csv_importer._parse_source_data(source_data)
        
        return source_data if isinstance(source_data, list) else [source_data]
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[str]:
        """Validate data for SAP import"""
        errors = []
        
        if not data:
            errors.append("No data to import")
            return errors
        
        # SAP-specific validation
        for i, record in enumerate(data):
            # Common SAP required fields
            if self.object_type == 'BusinessPartners':
                if 'CardCode' not in record or not record['CardCode']:
                    errors.append(f"Record {i+1}: CardCode is required for Business Partners")
                if 'CardName' not in record or not record['CardName']:
                    errors.append(f"Record {i+1}: CardName is required for Business Partners")
        
        return errors
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform data for SAP format"""
        transformed_data = []
        
        for record in data:
            transformed_record = DataTransformer.apply_field_mapping(record, self.config.field_mappings)
            
            # SAP-specific transformations
            if self.object_type == 'BusinessPartners':
                if 'Valid' not in transformed_record:
                    transformed_record['Valid'] = 'tYES'
                if 'CardType' not in transformed_record:
                    transformed_record['CardType'] = 'cCustomer'
            
            transformed_data.append(transformed_record)
        
        return transformed_data
    
    def import_data(self, data: List[Dict[str, Any]]) -> ImportResult:
        """Import data into SAP Business One"""
        start_time = time.time()
        
        if not self._authenticate():
            return ImportResult(
                success=False,
                total_records=len(data),
                imported_records=0,
                failed_records=len(data),
                errors=["SAP authentication failed"],
                warnings=[],
                execution_time=0.0
            )
        
        imported_count = 0
        failed_count = 0
        errors = []
        
        # SAP typically processes records one by one
        for i, record in enumerate(data):
            try:
                response = self.session.post(
                    f"{self.server_url}/{self.object_type}",
                    json=record
                )
                
                if response.status_code == 201:
                    imported_count += 1
                else:
                    failed_count += 1
                    error_msg = response.text
                    errors.append(f"Record {i+1}: {error_msg}")
                    
            except Exception as e:
                failed_count += 1
                errors.append(f"Record {i+1}: {str(e)}")
        
        end_time = time.time()
        
        return ImportResult(
            success=imported_count > 0,
            total_records=len(data),
            imported_records=imported_count,
            failed_records=failed_count,
            errors=errors,
            warnings=[],
            execution_time=end_time - start_time
        )