"""
Command-line interface for NovaSuite-AI Data Integration
"""

import click
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

from .base import SystemType, DataFormat, SystemConfig, FieldMapping
from .importers import CSVImporter, JSONImporter, OdooImporter, ZohoImporter, SAPImporter
from .exporters import DataExporter
from .validators import DataValidator
from .mappers import DataMapper, SystemMapper

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """NovaSuite-AI Data Integration CLI
    
    Import and export data between various ERP/CRM systems including
    Odoo, Zoho, SAP, ERPNext, EspoCRM, and Firefly III.
    """
    pass

@cli.command()
@click.option('--input-file', '-i', required=True, help='Input file path (CSV or JSON)')
@click.option('--output-file', '-o', help='Output file path for validation report')
@click.option('--system', '-s', type=click.Choice(['odoo', 'zoho_crm', 'sap_b1', 'erpnext', 'espocrm', 'firefly']),
              required=True, help='Target system type')
@click.option('--mapping-file', '-m', help='JSON file with field mappings')
@click.option('--delimiter', '-d', default=',', help='CSV delimiter (default: comma)')
def validate(input_file, output_file, system, mapping_file, delimiter):
    """Validate data file for system compatibility"""
    
    try:
        # Load data
        input_path = Path(input_file)
        if not input_path.exists():
            click.echo(f"Error: Input file '{input_file}' not found", err=True)
            sys.exit(1)
        
        # Parse data based on file type
        if input_path.suffix.lower() == '.csv':
            import pandas as pd
            df = pd.read_csv(input_path, delimiter=delimiter)
            data = df.to_dict('records')
        elif input_path.suffix.lower() == '.json':
            with open(input_path, 'r') as f:
                file_data = json.load(f)
                if isinstance(file_data, list):
                    data = file_data
                elif isinstance(file_data, dict) and 'data' in file_data:
                    data = file_data['data']
                else:
                    data = [file_data]
        else:
            click.echo("Error: Unsupported file format. Use CSV or JSON.", err=True)
            sys.exit(1)
        
        if not data:
            click.echo("Error: No data found in input file", err=True)
            sys.exit(1)
        
        # Load field mappings if provided
        field_mappings = []
        if mapping_file:
            with open(mapping_file, 'r') as f:
                mappings_data = json.load(f)
                for mapping in mappings_data:
                    field_mappings.append(FieldMapping(
                        source_field=mapping['source_field'],
                        target_field=mapping['target_field'],
                        transform_function=mapping.get('transform_function'),
                        default_value=mapping.get('default_value'),
                        required=mapping.get('required', False)
                    ))
        
        # Validate data
        validator = DataValidator()
        system_type = SystemType(system)
        
        # Validate field mappings if provided
        if field_mappings:
            mapping_errors = validator.validate_field_mapping(data, field_mappings, system_type)
            if mapping_errors:
                click.echo("Field mapping validation errors:")
                for error in mapping_errors:
                    click.echo(f"  - {error}", err=True)
                click.echo()
        
        # Validate data
        result = validator.validate_for_system(data, system_type)
        
        # Create report
        report = validator.create_validation_report(result)
        
        # Output report
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            click.echo(f"Validation report saved to: {output_file}")
        else:
            click.echo(report)
        
        # Exit with appropriate code
        if result['valid']:
            click.echo(f"✅ Validation PASSED - {result['valid_records']} records are valid")
            sys.exit(0)
        else:
            click.echo(f"❌ Validation FAILED - {result['invalid_records']} records have errors")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during validation: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--input-file', '-i', required=True, help='Input file path (CSV or JSON)')
@click.option('--config-file', '-c', required=True, help='JSON configuration file')
@click.option('--batch-size', '-b', default=100, help='Batch size for processing')
@click.option('--dry-run', is_flag=True, help='Validate only, do not import')
def import_data(input_file, config_file, batch_size, dry_run):
    """Import data into target system"""
    
    try:
        # Load configuration
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        system_type = SystemType(config_data['system_type'])
        connection_params = config_data['connection_params']
        
        # Create field mappings
        field_mappings = []
        for mapping in config_data.get('field_mappings', []):
            field_mappings.append(FieldMapping(
                source_field=mapping['source_field'],
                target_field=mapping['target_field'],
                transform_function=mapping.get('transform_function'),
                default_value=mapping.get('default_value'),
                required=mapping.get('required', False)
            ))
        
        # Create system config
        system_config = SystemConfig(
            system_type=system_type,
            connection_params=connection_params,
            field_mappings=field_mappings,
            batch_size=batch_size
        )
        
        # Create appropriate importer
        input_path = Path(input_file)
        
        if system_type == SystemType.ODOO:
            importer = OdooImporter(
                system_config,
                connection_params['odoo_url'],
                connection_params['database'],
                connection_params['username'],
                connection_params['password'],
                connection_params['model']
            )
        elif system_type == SystemType.ZOHO_CRM:
            importer = ZohoImporter(
                system_config,
                connection_params['access_token'],
                connection_params['refresh_token'],
                connection_params['client_id'],
                connection_params['client_secret'],
                connection_params['module']
            )
        elif system_type == SystemType.SAP_B1:
            importer = SAPImporter(
                system_config,
                connection_params['server_url'],
                connection_params['company_db'],
                connection_params['username'],
                connection_params['password'],
                connection_params['object_type']
            )
        else:
            # Use file-based importer
            if input_path.suffix.lower() == '.csv':
                importer = CSVImporter(system_config, str(input_path))
            else:
                importer = JSONImporter(system_config, str(input_path))
        
        if dry_run:
            click.echo("🔍 Dry run mode - validating data only...")
            
            # Validate data first
            validator = DataValidator()
            
            # Load and validate data
            if input_path.suffix.lower() == '.csv':
                import pandas as pd
                df = pd.read_csv(input_path)
                data = df.to_dict('records')
            else:
                with open(input_path, 'r') as f:
                    file_data = json.load(f)
                    data = file_data if isinstance(file_data, list) else [file_data]
            
            result = validator.validate_for_system(data, system_type)
            report = validator.create_validation_report(result)
            click.echo(report)
            
            if result['valid']:
                click.echo("✅ Data is valid for import")
            else:
                click.echo("❌ Data validation failed")
                sys.exit(1)
        else:
            # Perform actual import
            click.echo("📥 Starting data import...")
            
            result = importer.process_import(str(input_path))
            
            if result.success:
                click.echo(f"✅ Import completed successfully!")
                click.echo(f"   Total records: {result.total_records}")
                click.echo(f"   Imported: {result.imported_records}")
                click.echo(f"   Failed: {result.failed_records}")
                click.echo(f"   Execution time: {result.execution_time:.2f} seconds")
                
                if result.warnings:
                    click.echo("⚠️  Warnings:")
                    for warning in result.warnings:
                        click.echo(f"   - {warning}")
            else:
                click.echo(f"❌ Import failed!")
                click.echo(f"   Errors:")
                for error in result.errors:
                    click.echo(f"   - {error}")
                sys.exit(1)
                
    except Exception as e:
        click.echo(f"Error during import: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--config-file', '-c', required=True, help='JSON configuration file')
@click.option('--output-file', '-o', required=True, help='Output file path')
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json', help='Export format')
@click.option('--filters', help='JSON string with export filters')
def export_data(config_file, output_file, format, filters):
    """Export data from source system"""
    
    try:
        # Load configuration
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        system_type = SystemType(config_data['system_type'])
        connection_params = config_data['connection_params']
        
        # Create system config
        system_config = SystemConfig(
            system_type=system_type,
            connection_params=connection_params,
            field_mappings=[],  # Not needed for export
            batch_size=config_data.get('batch_size', 1000)
        )
        
        # Parse filters
        filter_dict = None
        if filters:
            filter_dict = json.loads(filters)
        
        # Export data
        exporter = DataExporter()
        data_format = DataFormat.JSON if format == 'json' else DataFormat.CSV
        
        click.echo("📤 Starting data export...")
        
        result = exporter.export_system_data(
            system_config, 
            output_file, 
            data_format, 
            filter_dict
        )
        
        if result.success:
            click.echo(f"✅ Export completed successfully!")
            click.echo(f"   Total records: {result.total_records}")
            click.echo(f"   Exported: {result.exported_records}")
            click.echo(f"   Output file: {result.file_path}")
            click.echo(f"   Execution time: {result.execution_time:.2f} seconds")
        else:
            click.echo(f"❌ Export failed!")
            click.echo(f"   Errors:")
            for error in result.errors:
                click.echo(f"   - {error}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error during export: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--configs-dir', '-c', required=True, help='Directory with system configuration files')
@click.option('--output-dir', '-o', required=True, help='Output directory for exports')
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json', help='Export format')
@click.option('--consolidated', is_flag=True, help='Create single consolidated export file')
def export_all(configs_dir, output_dir, format, consolidated):
    """Export data from all configured systems"""
    
    try:
        configs_path = Path(configs_dir)
        if not configs_path.exists():
            click.echo(f"Error: Configuration directory '{configs_dir}' not found", err=True)
            sys.exit(1)
        
        # Load all configuration files
        systems_config = []
        config_files = list(configs_path.glob('*.json'))
        
        if not config_files:
            click.echo(f"Error: No configuration files found in '{configs_dir}'", err=True)
            sys.exit(1)
        
        for config_file in config_files:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            system_type = SystemType(config_data['system_type'])
            system_config = SystemConfig(
                system_type=system_type,
                connection_params=config_data['connection_params'],
                field_mappings=[],
                batch_size=config_data.get('batch_size', 1000)
            )
            systems_config.append(system_config)
        
        exporter = DataExporter()
        data_format = DataFormat.JSON if format == 'json' else DataFormat.CSV
        
        click.echo(f"📤 Starting export from {len(systems_config)} systems...")
        
        if consolidated:
            # Create consolidated export
            output_file = Path(output_dir) / f"consolidated_export.json"
            result = exporter.create_consolidated_export(systems_config, str(output_file))
            
            if result.success:
                click.echo(f"✅ Consolidated export completed!")
                click.echo(f"   Total records: {result.total_records}")
                click.echo(f"   Output file: {result.file_path}")
                click.echo(f"   Execution time: {result.execution_time:.2f} seconds")
            else:
                click.echo(f"❌ Consolidated export failed!")
                for error in result.errors:
                    click.echo(f"   - {error}")
                sys.exit(1)
        else:
            # Export each system separately
            results = exporter.export_all_systems(systems_config, output_dir, data_format)
            
            successful_exports = 0
            total_records = 0
            
            for system_name, result in results.items():
                if result.success:
                    successful_exports += 1
                    total_records += result.exported_records
                    click.echo(f"✅ {system_name}: {result.exported_records} records exported")
                else:
                    click.echo(f"❌ {system_name}: Export failed")
                    for error in result.errors:
                        click.echo(f"   - {error}")
            
            click.echo(f"\n📊 Summary:")
            click.echo(f"   Successful exports: {successful_exports}/{len(systems_config)}")
            click.echo(f"   Total records exported: {total_records}")
            
            if successful_exports == 0:
                sys.exit(1)
                
    except Exception as e:
        click.echo(f"Error during export: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--input-file', '-i', required=True, help='Sample data file (CSV or JSON)')
@click.option('--target-system', '-t', type=click.Choice(['odoo', 'zoho_crm', 'sap_b1', 'erpnext', 'espocrm']),
              required=True, help='Target system type')
@click.option('--output-file', '-o', required=True, help='Output file for mapping template')
def generate_mapping(input_file, target_system, output_file):
    """Generate field mapping template"""
    
    try:
        # Load sample data to get field names
        input_path = Path(input_file)
        if not input_path.exists():
            click.echo(f"Error: Input file '{input_file}' not found", err=True)
            sys.exit(1)
        
        if input_path.suffix.lower() == '.csv':
            import pandas as pd
            df = pd.read_csv(input_path, nrows=1)  # Just read header
            source_fields = df.columns.tolist()
        else:
            with open(input_path, 'r') as f:
                file_data = json.load(f)
                if isinstance(file_data, list) and file_data:
                    source_fields = list(file_data[0].keys())
                elif isinstance(file_data, dict):
                    if 'data' in file_data and file_data['data']:
                        source_fields = list(file_data['data'][0].keys())
                    else:
                        source_fields = list(file_data.keys())
                else:
                    raise ValueError("Cannot determine field structure from JSON")
        
        # Generate mapping template
        mapper = DataMapper()
        system_type = SystemType(target_system)
        template_mappings = mapper.create_mapping_template(source_fields, system_type)
        
        # Convert to serializable format
        mappings_data = []
        for mapping in template_mappings:
            mappings_data.append({
                'source_field': mapping.source_field,
                'target_field': mapping.target_field,
                'transform_function': mapping.transform_function,
                'default_value': mapping.default_value,
                'required': mapping.required
            })
        
        # Save template
        with open(output_file, 'w') as f:
            json.dump(mappings_data, f, indent=2)
        
        click.echo(f"✅ Mapping template generated: {output_file}")
        click.echo(f"   Source fields: {len(source_fields)}")
        click.echo(f"   Target system: {target_system}")
        click.echo(f"   Mappings created: {len(template_mappings)}")
        click.echo("\n💡 Review and customize the generated mappings before importing")
        
    except Exception as e:
        click.echo(f"Error generating mapping template: {str(e)}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()