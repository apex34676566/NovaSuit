"""
Data exporters for various file formats and ERP systems
"""

import csv
import json
import pandas as pd
import requests
import time
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging
from datetime import datetime

from .base import (
    BaseExporter, ExportResult, SystemConfig, DataFormat, SystemType
)

logger = logging.getLogger(__name__)


class JSONExporter(BaseExporter):
    """JSON data exporter"""
    
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from the source system (to be implemented by specific exporters)"""
        # Base implementation - should be overridden
        return []
    
    def format_data(self, data: List[Dict[str, Any]], format_type: DataFormat) -> Any:
        """Format data for JSON export"""
        if format_type == DataFormat.JSON:
            # Create a structured export with metadata
            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "total_records": len(data),
                    "source_system": self.config.system_type.value,
                    "version": "1.0"
                },
                "data": data
            }
            return export_data
        else:
            return data
    
    def export_data(self, data: Any, output_path: str, format_type: DataFormat) -> ExportResult:
        """Export data to JSON file"""
        start_time = time.time()
        
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False, default=str)
            
            end_time = time.time()
            
            # Get actual record count
            record_count = data.get('metadata', {}).get('total_records', 0) if isinstance(data, dict) else len(data)
            
            return ExportResult(
                success=True,
                total_records=record_count,
                exported_records=record_count,
                file_path=str(output_file),
                errors=[],
                execution_time=end_time - start_time
            )
            
        except Exception as e:
            end_time = time.time()
            self.logger.error(f"JSON export failed: {str(e)}")
            return ExportResult(
                success=False,
                total_records=0,
                exported_records=0,
                file_path=None,
                errors=[str(e)],
                execution_time=end_time - start_time
            )


class CSVExporter(BaseExporter):
    """CSV data exporter"""
    
    def __init__(self, config: SystemConfig, delimiter: str = ','):
        super().__init__(config)
        self.delimiter = delimiter
    
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from the source system (to be implemented by specific exporters)"""
        # Base implementation - should be overridden
        return []
    
    def format_data(self, data: List[Dict[str, Any]], format_type: DataFormat) -> Any:
        """Format data for CSV export"""
        if format_type == DataFormat.CSV:
            # Convert to pandas DataFrame for easier CSV handling
            if data:
                df = pd.DataFrame(data)
                return df
            else:
                return pd.DataFrame()
        else:
            return data
    
    def export_data(self, data: Any, output_path: str, format_type: DataFormat) -> ExportResult:
        """Export data to CSV file"""
        start_time = time.time()
        
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            if isinstance(data, pd.DataFrame):
                data.to_csv(output_file, index=False, sep=self.delimiter, encoding='utf-8')
                record_count = len(data)
            else:
                # Fallback to manual CSV writing
                if not data:
                    record_count = 0
                    # Create empty file
                    with open(output_file, 'w', encoding='utf-8') as file:
                        pass
                else:
                    record_count = len(data)
                    fieldnames = list(data[0].keys()) if data else []
                    
                    with open(output_file, 'w', newline='', encoding='utf-8') as file:
                        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=self.delimiter)
                        writer.writeheader()
                        writer.writerows(data)
            
            end_time = time.time()
            
            return ExportResult(
                success=True,
                total_records=record_count,
                exported_records=record_count,
                file_path=str(output_file),
                errors=[],
                execution_time=end_time - start_time
            )
            
        except Exception as e:
            end_time = time.time()
            self.logger.error(f"CSV export failed: {str(e)}")
            return ExportResult(
                success=False,
                total_records=0,
                exported_records=0,
                file_path=None,
                errors=[str(e)],
                execution_time=end_time - start_time
            )


class ERPNextExporter(JSONExporter):
    """Exporter for ERPNext/Frappe data"""
    
    def __init__(self, config: SystemConfig, frappe_url: str, api_key: str, api_secret: str, doctype: str):
        super().__init__(config)
        self.frappe_url = frappe_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.doctype = doctype
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        })
    
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from ERPNext"""
        try:
            # Build API URL
            url = f"{self.frappe_url}/api/resource/{self.doctype}"
            
            # Prepare filters
            params = {}
            if filters:
                # Convert filters to ERPNext format
                for key, value in filters.items():
                    params[f'filters[{key}]'] = value
            
            # Add fields if specified in config
            if hasattr(self.config, 'export_fields') and self.config.export_fields:
                params['fields'] = json.dumps(self.config.export_fields)
            
            # Set limit
            params['limit_page_length'] = getattr(self.config, 'export_limit', 1000)
            
            all_data = []
            page = 1
            
            while True:
                params['limit_start'] = (page - 1) * params['limit_page_length']
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                result = response.json()
                data = result.get('data', [])
                
                if not data:
                    break
                
                all_data.extend(data)
                
                # Check if there are more pages
                if len(data) < params['limit_page_length']:
                    break
                
                page += 1
            
            return all_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract ERPNext data: {str(e)}")
            return []


class EspoCRMExporter(JSONExporter):
    """Exporter for EspoCRM data"""
    
    def __init__(self, config: SystemConfig, espo_url: str, api_key: str, entity_type: str):
        super().__init__(config)
        self.espo_url = espo_url.rstrip('/')
        self.api_key = api_key
        self.entity_type = entity_type
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from EspoCRM"""
        try:
            # Build API URL
            url = f"{self.espo_url}/api/v1/{self.entity_type}"
            
            # Prepare parameters
            params = {}
            if filters:
                params['where'] = json.dumps(filters)
            
            # Set pagination
            limit = getattr(self.config, 'export_limit', 200)  # EspoCRM default limit
            params['maxSize'] = limit
            
            all_data = []
            offset = 0
            
            while True:
                params['offset'] = offset
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                result = response.json()
                data = result.get('list', [])
                
                if not data:
                    break
                
                all_data.extend(data)
                
                # Check if there are more records
                if len(data) < limit:
                    break
                
                offset += limit
            
            return all_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract EspoCRM data: {str(e)}")
            return []


class FireflyIIIExporter(JSONExporter):
    """Exporter for Firefly III financial data"""
    
    def __init__(self, config: SystemConfig, firefly_url: str, access_token: str, data_type: str):
        super().__init__(config)
        self.firefly_url = firefly_url.rstrip('/')
        self.access_token = access_token
        self.data_type = data_type  # transactions, accounts, budgets, etc.
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/json'
        })
    
    def extract_data(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract data from Firefly III"""
        try:
            # Build API URL
            url = f"{self.firefly_url}/api/v1/{self.data_type}"
            
            # Prepare parameters
            params = {}
            if filters:
                # Apply date filters for transactions
                if self.data_type == 'transactions':
                    if 'start_date' in filters:
                        params['start'] = filters['start_date']
                    if 'end_date' in filters:
                        params['end'] = filters['end_date']
                    if 'type' in filters:
                        params['type'] = filters['type']
            
            # Set pagination
            page_size = getattr(self.config, 'export_limit', 50)  # Firefly III default
            params['limit'] = page_size
            
            all_data = []
            page = 1
            
            while True:
                params['page'] = page
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                result = response.json()
                data = result.get('data', [])
                
                if not data:
                    break
                
                # Transform Firefly III data format
                transformed_data = []
                for item in data:
                    # Flatten the JSON:API structure
                    flattened = {
                        'id': item.get('id'),
                        'type': item.get('type'),
                        **item.get('attributes', {})
                    }
                    transformed_data.append(flattened)
                
                all_data.extend(transformed_data)
                
                # Check pagination
                meta = result.get('meta', {})
                pagination = meta.get('pagination', {})
                
                if page >= pagination.get('total_pages', 1):
                    break
                
                page += 1
            
            return all_data
            
        except Exception as e:
            self.logger.error(f"Failed to extract Firefly III data: {str(e)}")
            return []


class DataExporter:
    """Main data exporter that can handle multiple systems and formats"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def export_system_data(self, system_config: SystemConfig, output_path: str, 
                          format_type: DataFormat, filters: Optional[Dict[str, Any]] = None) -> ExportResult:
        """Export data from any supported system"""
        
        try:
            # Create appropriate exporter based on system type
            if system_config.system_type == SystemType.ERPNEXT:
                connection_params = system_config.connection_params
                exporter = ERPNextExporter(
                    system_config,
                    connection_params['frappe_url'],
                    connection_params['api_key'],
                    connection_params['api_secret'],
                    connection_params['doctype']
                )
            elif system_config.system_type == SystemType.ESPOCRM:
                connection_params = system_config.connection_params
                exporter = EspoCRMExporter(
                    system_config,
                    connection_params['espo_url'],
                    connection_params['api_key'],
                    connection_params['entity_type']
                )
            elif system_config.system_type == SystemType.FIREFLY:
                connection_params = system_config.connection_params
                exporter = FireflyIIIExporter(
                    system_config,
                    connection_params['firefly_url'],
                    connection_params['access_token'],
                    connection_params['data_type']
                )
            else:
                # Use generic exporter for other systems
                if format_type == DataFormat.JSON:
                    exporter = JSONExporter(system_config)
                elif format_type == DataFormat.CSV:
                    exporter = CSVExporter(system_config)
                else:
                    raise ValueError(f"Unsupported format: {format_type}")
            
            # Perform export
            return exporter.process_export(output_path, format_type, filters)
            
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            return ExportResult(
                success=False,
                total_records=0,
                exported_records=0,
                file_path=None,
                errors=[str(e)],
                execution_time=0.0
            )
    
    def export_all_systems(self, systems_config: List[SystemConfig], output_dir: str,
                          format_type: DataFormat = DataFormat.JSON,
                          filters: Optional[Dict[str, Any]] = None) -> Dict[str, ExportResult]:
        """Export data from all configured systems"""
        
        results = {}
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for config in systems_config:
            system_name = config.system_type.value
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if format_type == DataFormat.JSON:
                filename = f"{system_name}_export_{timestamp}.json"
            elif format_type == DataFormat.CSV:
                filename = f"{system_name}_export_{timestamp}.csv"
            else:
                filename = f"{system_name}_export_{timestamp}.{format_type.value}"
            
            file_path = output_path / filename
            
            # Export system data
            result = self.export_system_data(config, str(file_path), format_type, filters)
            results[system_name] = result
            
            if result.success:
                self.logger.info(f"Successfully exported {result.exported_records} records from {system_name}")
            else:
                self.logger.error(f"Failed to export from {system_name}: {result.errors}")
        
        return results
    
    def create_consolidated_export(self, systems_config: List[SystemConfig], output_path: str,
                                 filters: Optional[Dict[str, Any]] = None) -> ExportResult:
        """Create a single consolidated JSON export with data from all systems"""
        
        start_time = time.time()
        
        try:
            consolidated_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "systems": [config.system_type.value for config in systems_config],
                    "version": "1.0"
                },
                "data": {}
            }
            
            total_records = 0
            errors = []
            
            for config in systems_config:
                system_name = config.system_type.value
                
                try:
                    # Export individual system
                    temp_result = self.export_system_data(
                        config, 
                        f"/tmp/{system_name}_temp.json", 
                        DataFormat.JSON, 
                        filters
                    )
                    
                    if temp_result.success:
                        # Load the exported data
                        with open(temp_result.file_path, 'r') as f:
                            system_data = json.load(f)
                        
                        # Add to consolidated export
                        if isinstance(system_data, dict) and 'data' in system_data:
                            consolidated_data['data'][system_name] = system_data['data']
                            total_records += len(system_data['data'])
                        else:
                            consolidated_data['data'][system_name] = system_data
                            total_records += len(system_data) if isinstance(system_data, list) else 1
                        
                        # Clean up temp file
                        Path(temp_result.file_path).unlink(missing_ok=True)
                    else:
                        errors.extend([f"{system_name}: {error}" for error in temp_result.errors])
                        
                except Exception as e:
                    errors.append(f"{system_name}: {str(e)}")
            
            # Update metadata
            consolidated_data['metadata']['total_records'] = total_records
            
            # Save consolidated export
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(consolidated_data, file, indent=2, ensure_ascii=False, default=str)
            
            end_time = time.time()
            
            return ExportResult(
                success=total_records > 0,
                total_records=total_records,
                exported_records=total_records,
                file_path=str(output_file),
                errors=errors,
                execution_time=end_time - start_time
            )
            
        except Exception as e:
            end_time = time.time()
            self.logger.error(f"Consolidated export failed: {str(e)}")
            return ExportResult(
                success=False,
                total_records=0,
                exported_records=0,
                file_path=None,
                errors=[str(e)],
                execution_time=end_time - start_time
            )