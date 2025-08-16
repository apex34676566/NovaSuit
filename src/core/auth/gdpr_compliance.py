"""
GDPR Compliance System
Handles data subject rights, consent management, and legal change tracking
"""

import json
import csv
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import smtplib
import uuid
from pathlib import Path

from .models import User, GDPRRecord, LegalChangeLog, AuditLog
from .audit_logger import AuditLogger


class GDPRCompliance:
    """GDPR Compliance management system"""
    
    def __init__(self, db_session: Session, audit_logger: AuditLogger, 
                 email_config: Dict[str, Any], data_controller_info: Dict[str, Any]):
        self.db = db_session
        self.audit_logger = audit_logger
        self.email_config = email_config
        self.data_controller_info = data_controller_info
        
        # Data categories for GDPR compliance
        self.data_categories = {
            'personal_identifiers': ['name', 'username', 'email', 'user_id'],
            'authentication_data': ['password_hash', '2fa_secret', 'backup_codes'],
            'security_data': ['login_attempts', 'failed_logins', 'api_keys'],
            'audit_data': ['access_logs', 'activity_logs', 'security_logs'],
            'technical_data': ['ip_addresses', 'user_agents', 'session_data'],
            'usage_data': ['api_usage', 'feature_usage', 'access_patterns']
        }
        
        # Processing purposes
        self.processing_purposes = {
            'authentication': 'User authentication and access control',
            'security': 'Security monitoring and threat detection',
            'service_provision': 'Providing and maintaining our services',
            'compliance': 'Legal and regulatory compliance',
            'analytics': 'Service improvement and analytics',
            'communication': 'Service-related communications'
        }
    
    def record_consent(self, user_id: int, consent_type: str, given: bool,
                      mechanism: str, data_categories: List[str] = None,
                      processing_purposes: List[str] = None) -> GDPRRecord:
        """Record user consent for data processing"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create GDPR record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='consent',
                legal_basis='consent',
                data_categories=data_categories or [],
                processing_purposes=processing_purposes or [],
                consent_given=given,
                consent_mechanism=mechanism,
                status='completed'
            )
            gdpr_record.processed_date = datetime.utcnow()
            
            # Update user consent status
            if given:
                user.gdpr_consent = True
                user.gdpr_consent_date = datetime.utcnow()
                # Set data retention period (7 years for financial data, 3 years for general)
                user.data_retention_until = datetime.utcnow() + timedelta(days=2555)  # 7 years
            else:
                user.gdpr_consent = False
                gdpr_record.consent_withdrawn = True
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='consent',
                status='completed',
                data_categories=data_categories,
                processing_purposes=processing_purposes,
                additional_data={
                    'consent_given': given,
                    'mechanism': mechanism,
                    'gdpr_record_id': gdpr_record.id
                }
            )
            
            return gdpr_record
            
        except Exception as e:
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='consent',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def withdraw_consent(self, user_id: int, reason: str = None) -> GDPRRecord:
        """Process consent withdrawal"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create withdrawal record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='consent_withdrawal',
                legal_basis='consent',
                consent_withdrawn=True,
                status='completed',
                notes=reason
            )
            gdpr_record.processed_date = datetime.utcnow()
            
            # Update user consent status
            user.gdpr_consent = False
            
            # Mark for data deletion (30 days grace period)
            user.data_retention_until = datetime.utcnow() + timedelta(days=30)
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='consent_withdrawal',
                status='completed',
                additional_data={
                    'reason': reason,
                    'gdpr_record_id': gdpr_record.id,
                    'data_deletion_scheduled': user.data_retention_until.isoformat()
                }
            )
            
            return gdpr_record
            
        except Exception as e:
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='consent_withdrawal',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def process_access_request(self, user_id: int, requested_categories: List[str] = None,
                             response_format: str = 'json') -> Tuple[GDPRRecord, Dict[str, Any]]:
        """Process data subject access request (Article 15)"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create GDPR record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='access',
                legal_basis='data_subject_rights',
                data_categories=requested_categories or list(self.data_categories.keys()),
                status='processing'
            )
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            # Collect user data
            user_data = self._collect_user_data(user_id, requested_categories)
            
            # Update GDPR record with response
            gdpr_record.status = 'completed'
            gdpr_record.processed_date = datetime.utcnow()
            gdpr_record.access_provided = True
            gdpr_record.response_data = user_data
            gdpr_record.response_format = response_format
            
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='access',
                status='completed',
                data_categories=requested_categories,
                additional_data={
                    'gdpr_record_id': gdpr_record.id,
                    'response_format': response_format,
                    'data_categories_provided': len(user_data.get('categories', {}))
                }
            )
            
            return gdpr_record, user_data
            
        except Exception as e:
            if 'gdpr_record' in locals():
                gdpr_record.status = 'failed'
                gdpr_record.notes = str(e)
                self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='access',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def process_rectification_request(self, user_id: int, field_updates: Dict[str, Any],
                                    justification: str) -> GDPRRecord:
        """Process data rectification request (Article 16)"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create GDPR record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='rectification',
                legal_basis='data_subject_rights',
                status='processing',
                notes=justification
            )
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            # Apply updates (with validation)
            updated_fields = []
            original_values = {}
            
            for field, new_value in field_updates.items():
                if hasattr(user, field) and field in ['username', 'email']:  # Only allow safe fields
                    original_values[field] = getattr(user, field)
                    setattr(user, field, new_value)
                    updated_fields.append(field)
            
            if updated_fields:
                user.updated_at = datetime.utcnow()
                
                # Update GDPR record
                gdpr_record.status = 'completed'
                gdpr_record.processed_date = datetime.utcnow()
                gdpr_record.rectification_completed = True
                gdpr_record.response_data = {
                    'updated_fields': updated_fields,
                    'original_values': original_values,
                    'new_values': field_updates
                }
            else:
                gdpr_record.status = 'rejected'
                gdpr_record.notes += ' - No valid fields to update'
            
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='rectification',
                status=gdpr_record.status,
                additional_data={
                    'gdpr_record_id': gdpr_record.id,
                    'updated_fields': updated_fields,
                    'justification': justification
                }
            )
            
            return gdpr_record
            
        except Exception as e:
            if 'gdpr_record' in locals():
                gdpr_record.status = 'failed'
                gdpr_record.notes = f"{gdpr_record.notes or ''} - Error: {str(e)}"
                self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='rectification',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def process_erasure_request(self, user_id: int, reason: str,
                              immediate: bool = False) -> GDPRRecord:
        """Process data erasure request (Article 17 - Right to be forgotten)"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create GDPR record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='erasure',
                legal_basis='data_subject_rights',
                status='processing',
                notes=reason
            )
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            if immediate:
                # Perform immediate erasure
                self._perform_data_erasure(user_id)
                gdpr_record.status = 'completed'
                gdpr_record.erasure_completed = True
            else:
                # Schedule for erasure (30 days notice period)
                user.data_retention_until = datetime.utcnow() + timedelta(days=30)
                gdpr_record.status = 'scheduled'
                gdpr_record.notes += f" - Scheduled for erasure on {user.data_retention_until.isoformat()}"
            
            gdpr_record.processed_date = datetime.utcnow()
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='erasure',
                status=gdpr_record.status,
                additional_data={
                    'gdpr_record_id': gdpr_record.id,
                    'reason': reason,
                    'immediate': immediate,
                    'scheduled_date': user.data_retention_until.isoformat() if not immediate else None
                }
            )
            
            return gdpr_record
            
        except Exception as e:
            if 'gdpr_record' in locals():
                gdpr_record.status = 'failed'
                gdpr_record.notes = f"{gdpr_record.notes or ''} - Error: {str(e)}"
                self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='erasure',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def process_portability_request(self, user_id: int, export_format: str = 'json') -> Tuple[GDPRRecord, str]:
        """Process data portability request (Article 20)"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Create GDPR record
            gdpr_record = GDPRRecord(
                user_id=user_id,
                request_type='portability',
                legal_basis='data_subject_rights',
                status='processing',
                response_format=export_format
            )
            
            self.db.add(gdpr_record)
            self.db.commit()
            
            # Export user data in portable format
            export_data = self._export_portable_data(user_id, export_format)
            
            # Save export file
            export_filename = f"user_{user_id}_data_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            export_path = Path(f"./exports/{export_filename}")
            export_path.parent.mkdir(exist_ok=True)
            
            if export_format == 'json':
                with open(export_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif export_format == 'csv':
                # Flatten data for CSV export
                self._save_as_csv(export_data, export_path)
            
            # Update GDPR record
            gdpr_record.status = 'completed'
            gdpr_record.processed_date = datetime.utcnow()
            gdpr_record.portability_provided = True
            gdpr_record.response_data = {'export_file': export_filename}
            
            self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='portability',
                status='completed',
                additional_data={
                    'gdpr_record_id': gdpr_record.id,
                    'export_format': export_format,
                    'export_file': export_filename
                }
            )
            
            return gdpr_record, str(export_path)
            
        except Exception as e:
            if 'gdpr_record' in locals():
                gdpr_record.status = 'failed'
                gdpr_record.notes = str(e)
                self.db.commit()
            
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='portability',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def log_legal_change(self, change_type: str, title: str, description: str,
                        jurisdiction: str = 'EU', regulation: str = 'GDPR',
                        compliance_deadline: datetime = None,
                        created_by: str = 'system') -> LegalChangeLog:
        """Log important legal changes"""
        try:
            # Determine version number
            latest_version = self.db.query(LegalChangeLog).filter(
                LegalChangeLog.change_type == change_type
            ).order_by(LegalChangeLog.created_at.desc()).first()
            
            if latest_version and latest_version.version:
                try:
                    major, minor = latest_version.version.split('.')
                    new_version = f"{major}.{int(minor) + 1}"
                except:
                    new_version = "1.1"
            else:
                new_version = "1.0"
            
            legal_change = LegalChangeLog(
                change_type=change_type,
                title=title,
                description=description,
                jurisdiction=jurisdiction,
                regulation=regulation,
                compliance_deadline=compliance_deadline,
                created_by=created_by,
                version=new_version
            )
            
            if latest_version:
                legal_change.previous_version_id = latest_version.id
            
            self.db.add(legal_change)
            self.db.commit()
            
            self.audit_logger.log_compliance_event(
                regulation=regulation,
                event_type='legal_change_logged',
                compliance_status='pending',
                details=f"{title}: {description}",
                deadline=compliance_deadline,
                additional_data={
                    'change_id': legal_change.id,
                    'change_type': change_type,
                    'version': new_version,
                    'jurisdiction': jurisdiction
                }
            )
            
            return legal_change
            
        except Exception as e:
            self.audit_logger.log_compliance_event(
                regulation=regulation or 'GDPR',
                event_type='legal_change_log_error',
                compliance_status='error',
                details=f"Failed to log legal change: {str(e)}",
                additional_data={'error': str(e)}
            )
            raise
    
    def process_scheduled_deletions(self) -> List[Dict[str, Any]]:
        """Process users scheduled for data deletion"""
        try:
            now = datetime.utcnow()
            
            # Find users scheduled for deletion
            users_to_delete = self.db.query(User).filter(
                and_(
                    User.data_retention_until.isnot(None),
                    User.data_retention_until <= now,
                    User.gdpr_consent == False
                )
            ).all()
            
            deleted_users = []
            
            for user in users_to_delete:
                try:
                    # Perform data erasure
                    self._perform_data_erasure(user.id)
                    
                    # Create completion record
                    gdpr_record = GDPRRecord(
                        user_id=user.id,
                        request_type='erasure',
                        status='completed',
                        erasure_completed=True,
                        processed_date=now,
                        notes='Automatic deletion due to consent withdrawal'
                    )
                    self.db.add(gdpr_record)
                    
                    deleted_users.append({
                        'user_id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'deletion_date': now.isoformat()
                    })
                    
                except Exception as e:
                    self.audit_logger.log_gdpr_event(
                        user_id=user.id,
                        request_type='erasure',
                        status='failed',
                        additional_data={'error': str(e)}
                    )
            
            self.db.commit()
            
            if deleted_users:
                self.audit_logger.log_gdpr_event(
                    user_id=None,
                    request_type='scheduled_deletion',
                    status='completed',
                    additional_data={
                        'deleted_users_count': len(deleted_users),
                        'deleted_users': deleted_users
                    }
                )
            
            return deleted_users
            
        except Exception as e:
            self.audit_logger.log_gdpr_event(
                user_id=None,
                request_type='scheduled_deletion',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise
    
    def _collect_user_data(self, user_id: int, requested_categories: List[str] = None) -> Dict[str, Any]:
        """Collect all user data for access requests"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}
        
        categories_to_include = requested_categories or list(self.data_categories.keys())
        
        user_data = {
            'user_id': user_id,
            'export_date': datetime.utcnow().isoformat(),
            'data_controller': self.data_controller_info,
            'categories': {},
            'processing_purposes': {k: v for k, v in self.processing_purposes.items()},
            'legal_basis': 'consent' if user.gdpr_consent else 'legitimate_interest',
            'retention_period': user.data_retention_until.isoformat() if user.data_retention_until else None
        }
        
        # Personal identifiers
        if 'personal_identifiers' in categories_to_include:
            user_data['categories']['personal_identifiers'] = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            }
        
        # Authentication data (limited for security)
        if 'authentication_data' in categories_to_include:
            user_data['categories']['authentication_data'] = {
                'two_factor_enabled': user.two_factor_enabled,
                'backup_codes_count': len(user.backup_codes) if user.backup_codes else 0,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        
        # Security data
        if 'security_data' in categories_to_include:
            user_data['categories']['security_data'] = {
                'failed_login_attempts': user.failed_login_attempts,
                'account_locked': user.is_locked(),
                'api_keys_count': len(user.api_keys)
            }
        
        # Audit data (recent logs only)
        if 'audit_data' in categories_to_include:
            recent_logs = self.audit_logger.export_user_audit_data(user_id)
            user_data['categories']['audit_data'] = recent_logs
        
        # GDPR records
        if 'gdpr_data' in categories_to_include:
            gdpr_records = self.db.query(GDPRRecord).filter(GDPRRecord.user_id == user_id).all()
            user_data['categories']['gdpr_data'] = [
                {
                    'request_type': record.request_type,
                    'request_date': record.request_date.isoformat(),
                    'status': record.status,
                    'processed_date': record.processed_date.isoformat() if record.processed_date else None
                }
                for record in gdpr_records
            ]
        
        return user_data
    
    def _export_portable_data(self, user_id: int, format: str) -> Dict[str, Any]:
        """Export user data in portable format"""
        # Get complete user data
        user_data = self._collect_user_data(user_id)
        
        # Add portability-specific information
        user_data['export_type'] = 'data_portability'
        user_data['format'] = format
        user_data['rights_notice'] = {
            'right_to_rectification': 'You can request corrections to your data',
            'right_to_erasure': 'You can request deletion of your data',
            'right_to_restrict_processing': 'You can request restriction of processing',
            'right_to_object': 'You can object to processing based on legitimate interests'
        }
        
        return user_data
    
    def _save_as_csv(self, data: Dict[str, Any], file_path: Path):
        """Save data as CSV format"""
        flattened_data = []
        
        def flatten_dict(d, parent_key='', sep='_'):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                        else:
                            items.append((f"{new_key}_{i}", item))
                else:
                    items.append((new_key, v))
            return dict(items)
        
        flat_data = flatten_dict(data)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Field', 'Value'])
            for key, value in flat_data.items():
                writer.writerow([key, str(value)])
    
    def _perform_data_erasure(self, user_id: int):
        """Perform complete data erasure for user"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # Anonymize user data instead of hard deletion (for audit trail)
        user.username = f"deleted_user_{user_id}"
        user.email = f"deleted_{user_id}@example.com"
        user.password_hash = None
        user.two_factor_secret = None
        user.backup_codes = None
        user.data_retention_until = None
        
        # Deactivate API keys
        for api_key in user.api_keys:
            api_key.is_active = False
        
        # Note: Audit logs are kept for compliance but user data is anonymized
        
        self.audit_logger.log_gdpr_event(
            user_id=user_id,
            request_type='data_erasure_completed',
            status='completed',
            additional_data={'erasure_method': 'anonymization'}
        )
    
    def get_gdpr_dashboard(self, user_id: int = None) -> Dict[str, Any]:
        """Get GDPR compliance dashboard data"""
        try:
            # Overall statistics
            total_requests = self.db.query(GDPRRecord).count()
            pending_requests = self.db.query(GDPRRecord).filter(
                GDPRRecord.status.in_(['pending', 'processing'])
            ).count()
            
            # Requests by type
            request_types = {}
            for request_type in ['consent', 'access', 'rectification', 'erasure', 'portability']:
                count = self.db.query(GDPRRecord).filter(
                    GDPRRecord.request_type == request_type
                ).count()
                request_types[request_type] = count
            
            # Recent legal changes
            recent_changes = self.db.query(LegalChangeLog).order_by(
                LegalChangeLog.created_at.desc()
            ).limit(10).all()
            
            # Users scheduled for deletion
            scheduled_deletions = self.db.query(User).filter(
                and_(
                    User.data_retention_until.isnot(None),
                    User.data_retention_until > datetime.utcnow()
                )
            ).count()
            
            dashboard = {
                'overview': {
                    'total_gdpr_requests': total_requests,
                    'pending_requests': pending_requests,
                    'scheduled_deletions': scheduled_deletions
                },
                'requests_by_type': request_types,
                'recent_legal_changes': [
                    {
                        'id': change.id,
                        'type': change.change_type,
                        'title': change.title,
                        'version': change.version,
                        'created_at': change.created_at.isoformat(),
                        'status': change.implementation_status,
                        'deadline': change.compliance_deadline.isoformat() if change.compliance_deadline else None
                    }
                    for change in recent_changes
                ]
            }
            
            # User-specific data if requested
            if user_id:
                user_requests = self.db.query(GDPRRecord).filter(
                    GDPRRecord.user_id == user_id
                ).order_by(GDPRRecord.request_date.desc()).all()
                
                dashboard['user_requests'] = [
                    {
                        'id': req.id,
                        'type': req.request_type,
                        'status': req.status,
                        'request_date': req.request_date.isoformat(),
                        'processed_date': req.processed_date.isoformat() if req.processed_date else None
                    }
                    for req in user_requests
                ]
            
            return dashboard
            
        except Exception as e:
            self.audit_logger.log_gdpr_event(
                user_id=user_id,
                request_type='dashboard_access',
                status='failed',
                additional_data={'error': str(e)}
            )
            raise