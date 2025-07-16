"""
Comprehensive Audit Logging System
Provides structured logging for security events, compliance, and operational monitoring
"""

import json
import logging
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pythonjsonlogger import jsonlogger
import os
from pathlib import Path

from .models import AuditLog, User


class AuditLogger:
    """Comprehensive audit logging system"""
    
    def __init__(self, db_session: Session, log_directory: str = "./logs"):
        self.db = db_session
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        
        # Configure structured logging
        self._setup_structured_logging()
        
        # Set up different log levels for different categories
        self.security_logger = structlog.get_logger("security")
        self.auth_logger = structlog.get_logger("auth")
        self.api_logger = structlog.get_logger("api")
        self.gdpr_logger = structlog.get_logger("gdpr")
        self.compliance_logger = structlog.get_logger("compliance")
        self.general_logger = structlog.get_logger("general")
    
    def _setup_structured_logging(self):
        """Configure structured logging with JSON output"""
        
        # Create log files for different categories
        log_files = {
            'security': self.log_directory / 'security.log',
            'auth': self.log_directory / 'auth.log',
            'api': self.log_directory / 'api.log',
            'gdpr': self.log_directory / 'gdpr.log',
            'compliance': self.log_directory / 'compliance.log',
            'general': self.log_directory / 'general.log'
        }
        
        # Configure Python logging
        logging.basicConfig(level=logging.INFO)
        
        # JSON formatter
        json_formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create handlers for each log file
        handlers = {}
        for category, log_file in log_files.items():
            handler = logging.FileHandler(log_file)
            handler.setFormatter(json_formatter)
            handlers[category] = handler
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Add handlers to loggers
        for category, handler in handlers.items():
            logger = logging.getLogger(category)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: str, event_category: str, action: str,
                  user_id: Optional[int] = None, success: bool = True,
                  ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                  session_id: Optional[str] = None, api_key_id: Optional[int] = None,
                  resource: Optional[str] = None, error_message: Optional[str] = None,
                  metadata: Optional[Dict[str, Any]] = None):
        """
        Log an audit event to both database and structured logs
        """
        try:
            # Create audit log entry in database
            audit_log = AuditLog(
                event_type=event_type,
                event_category=event_category,
                action=action,
                user_id=user_id
            )
            
            # Set optional fields
            if ip_address:
                audit_log.ip_address = ip_address
            if user_agent:
                audit_log.user_agent = user_agent
            if session_id:
                audit_log.session_id = session_id
            if api_key_id:
                audit_log.api_key_id = api_key_id
            if resource:
                audit_log.resource = resource
            if error_message:
                audit_log.error_message = error_message
            if metadata:
                audit_log.metadata = metadata
            
            audit_log.success = success
            
            # Save to database
            self.db.add(audit_log)
            self.db.commit()
            
            # Log to structured logs
            self._log_to_structured(audit_log)
            
        except Exception as e:
            # Fallback logging if database fails
            self._emergency_log(event_type, event_category, action, str(e), user_id)
    
    def _log_to_structured(self, audit_log: AuditLog):
        """Log to structured logging system"""
        
        log_data = {
            'event_id': audit_log.id,
            'event_type': audit_log.event_type,
            'action': audit_log.action,
            'success': audit_log.success,
            'user_id': audit_log.user_id,
            'ip_address': audit_log.ip_address,
            'user_agent': audit_log.user_agent,
            'session_id': audit_log.session_id,
            'api_key_id': audit_log.api_key_id,
            'resource': audit_log.resource,
            'metadata': audit_log.metadata,
            'timestamp': audit_log.timestamp.isoformat()
        }
        
        if audit_log.error_message:
            log_data['error_message'] = audit_log.error_message
        
        # Choose appropriate logger based on category
        logger = self._get_category_logger(audit_log.event_category)
        
        if audit_log.success:
            logger.info(f"{audit_log.action} completed", **log_data)
        else:
            logger.error(f"{audit_log.action} failed", **log_data)
    
    def _get_category_logger(self, category: str) -> structlog.BoundLogger:
        """Get appropriate logger for event category"""
        category_loggers = {
            'security': self.security_logger,
            'auth': self.auth_logger,
            'api': self.api_logger,
            'gdpr': self.gdpr_logger,
            'compliance': self.compliance_logger
        }
        return category_loggers.get(category, self.general_logger)
    
    def _emergency_log(self, event_type: str, event_category: str, action: str, 
                      error: str, user_id: Optional[int] = None):
        """Emergency logging when database is unavailable"""
        emergency_log = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'event_category': event_category,
            'action': action,
            'user_id': user_id,
            'error': error,
            'emergency': True
        }
        
        emergency_file = self.log_directory / 'emergency.log'
        with open(emergency_file, 'a') as f:
            f.write(json.dumps(emergency_log) + '\n')
    
    def log_authentication_event(self, user_id: int, event_type: str, success: bool,
                                ip_address: str = None, user_agent: str = None,
                                session_id: str = None, additional_data: Dict[str, Any] = None):
        """Log authentication-specific events"""
        self.log_event(
            event_type=event_type,
            event_category="auth",
            action=f"user_{event_type}",
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=additional_data
        )
    
    def log_security_event(self, event_type: str, description: str, 
                          severity: str = "medium", user_id: int = None,
                          ip_address: str = None, additional_data: Dict[str, Any] = None):
        """Log security-specific events"""
        metadata = additional_data or {}
        metadata['severity'] = severity
        metadata['description'] = description
        
        self.log_event(
            event_type=event_type,
            event_category="security",
            action="security_event",
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            metadata=metadata
        )
    
    def log_gdpr_event(self, user_id: int, request_type: str, status: str,
                      data_categories: List[str] = None, 
                      processing_purposes: List[str] = None,
                      additional_data: Dict[str, Any] = None):
        """Log GDPR-specific events"""
        metadata = additional_data or {}
        metadata.update({
            'request_type': request_type,
            'status': status,
            'data_categories': data_categories or [],
            'processing_purposes': processing_purposes or []
        })
        
        self.log_event(
            event_type=f"gdpr_{request_type}",
            event_category="gdpr",
            action=f"gdpr_{request_type}_{status}",
            user_id=user_id,
            success=status in ['completed', 'processed'],
            metadata=metadata
        )
    
    def log_api_access(self, api_key_id: int, endpoint: str, method: str,
                      response_code: int, user_id: int = None,
                      ip_address: str = None, processing_time: float = None,
                      request_size: int = None, response_size: int = None):
        """Log API access events"""
        metadata = {
            'endpoint': endpoint,
            'method': method,
            'response_code': response_code,
            'processing_time_ms': processing_time,
            'request_size_bytes': request_size,
            'response_size_bytes': response_size
        }
        
        self.log_event(
            event_type="api_request",
            event_category="api",
            action=f"{method}_{endpoint}",
            user_id=user_id,
            success=200 <= response_code < 400,
            ip_address=ip_address,
            api_key_id=api_key_id,
            resource=endpoint,
            metadata=metadata
        )
    
    def log_compliance_event(self, regulation: str, event_type: str,
                           compliance_status: str, details: str,
                           deadline: datetime = None, 
                           additional_data: Dict[str, Any] = None):
        """Log compliance-related events"""
        metadata = additional_data or {}
        metadata.update({
            'regulation': regulation,
            'compliance_status': compliance_status,
            'details': details,
            'deadline': deadline.isoformat() if deadline else None
        })
        
        self.log_event(
            event_type=event_type,
            event_category="compliance",
            action=f"compliance_{event_type}",
            success=compliance_status == 'compliant',
            metadata=metadata
        )
    
    def search_audit_logs(self, filters: Dict[str, Any], 
                         limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Search audit logs with filters
        Returns paginated results with metadata
        """
        try:
            query = self.db.query(AuditLog)
            
            # Apply filters
            if 'user_id' in filters:
                query = query.filter(AuditLog.user_id == filters['user_id'])
            
            if 'event_category' in filters:
                query = query.filter(AuditLog.event_category == filters['event_category'])
            
            if 'event_type' in filters:
                query = query.filter(AuditLog.event_type == filters['event_type'])
            
            if 'success' in filters:
                query = query.filter(AuditLog.success == filters['success'])
            
            if 'ip_address' in filters:
                query = query.filter(AuditLog.ip_address == filters['ip_address'])
            
            if 'start_date' in filters:
                query = query.filter(AuditLog.timestamp >= filters['start_date'])
            
            if 'end_date' in filters:
                query = query.filter(AuditLog.timestamp <= filters['end_date'])
            
            if 'api_key_id' in filters:
                query = query.filter(AuditLog.api_key_id == filters['api_key_id'])
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination and ordering
            logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
            
            # Format results
            results = []
            for log in logs:
                results.append({
                    'id': log.id,
                    'event_type': log.event_type,
                    'event_category': log.event_category,
                    'action': log.action,
                    'user_id': log.user_id,
                    'success': log.success,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'session_id': log.session_id,
                    'api_key_id': log.api_key_id,
                    'resource': log.resource,
                    'error_message': log.error_message,
                    'metadata': log.metadata,
                    'timestamp': log.timestamp.isoformat(),
                    'retention_until': log.retention_until.isoformat() if log.retention_until else None
                })
            
            return {
                'logs': results,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': total_count > offset + limit
            }
            
        except Exception as e:
            self.log_event(
                event_type="audit_search_error",
                event_category="compliance",
                action="search_audit_logs",
                success=False,
                error_message=str(e),
                metadata={'filters': filters}
            )
            raise
    
    def generate_compliance_report(self, start_date: datetime, end_date: datetime,
                                 categories: List[str] = None) -> Dict[str, Any]:
        """Generate compliance report for specified period"""
        try:
            query = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            )
            
            if categories:
                query = query.filter(AuditLog.event_category.in_(categories))
            
            logs = query.all()
            
            # Generate statistics
            total_events = len(logs)
            successful_events = len([log for log in logs if log.success])
            failed_events = total_events - successful_events
            
            # Events by category
            events_by_category = {}
            events_by_type = {}
            events_by_user = {}
            daily_activity = {}
            
            for log in logs:
                # By category
                if log.event_category not in events_by_category:
                    events_by_category[log.event_category] = 0
                events_by_category[log.event_category] += 1
                
                # By type
                if log.event_type not in events_by_type:
                    events_by_type[log.event_type] = 0
                events_by_type[log.event_type] += 1
                
                # By user
                if log.user_id:
                    if log.user_id not in events_by_user:
                        events_by_user[log.user_id] = 0
                    events_by_user[log.user_id] += 1
                
                # Daily activity
                day = log.timestamp.date().isoformat()
                if day not in daily_activity:
                    daily_activity[day] = 0
                daily_activity[day] += 1
            
            # Security events analysis
            security_events = [log for log in logs if log.event_category == 'security']
            failed_logins = [log for log in logs if log.event_type == 'login' and not log.success]
            
            report = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary': {
                    'total_events': total_events,
                    'successful_events': successful_events,
                    'failed_events': failed_events,
                    'success_rate': (successful_events / total_events * 100) if total_events > 0 else 0
                },
                'events_by_category': events_by_category,
                'events_by_type': events_by_type,
                'events_by_user': dict(sorted(events_by_user.items(), key=lambda x: x[1], reverse=True)[:10]),
                'daily_activity': daily_activity,
                'security_analysis': {
                    'security_events_count': len(security_events),
                    'failed_login_attempts': len(failed_logins),
                    'security_incidents': [
                        {
                            'timestamp': log.timestamp.isoformat(),
                            'event_type': log.event_type,
                            'user_id': log.user_id,
                            'ip_address': log.ip_address,
                            'description': log.error_message or log.metadata.get('description', '')
                        }
                        for log in security_events
                        if not log.success or log.metadata.get('severity') in ['high', 'critical']
                    ]
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
            # Log report generation
            self.log_event(
                event_type="compliance_report_generated",
                event_category="compliance",
                action="generate_compliance_report",
                success=True,
                metadata={
                    'report_period_days': (end_date - start_date).days,
                    'total_events_analyzed': total_events,
                    'categories': categories or 'all'
                }
            )
            
            return report
            
        except Exception as e:
            self.log_event(
                event_type="compliance_report_error",
                event_category="compliance",
                action="generate_compliance_report",
                success=False,
                error_message=str(e)
            )
            raise
    
    def cleanup_expired_logs(self) -> int:
        """Clean up audit logs that have exceeded their retention period"""
        try:
            now = datetime.utcnow()
            
            # Find expired logs
            expired_logs = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.retention_until.isnot(None),
                    AuditLog.retention_until < now
                )
            ).all()
            
            expired_count = len(expired_logs)
            
            # Delete expired logs
            if expired_logs:
                for log in expired_logs:
                    self.db.delete(log)
                self.db.commit()
                
                self.log_event(
                    event_type="audit_logs_cleaned",
                    event_category="compliance",
                    action="cleanup_expired_logs",
                    success=True,
                    metadata={'deleted_logs_count': expired_count}
                )
            
            return expired_count
            
        except Exception as e:
            self.log_event(
                event_type="audit_cleanup_error",
                event_category="compliance",
                action="cleanup_expired_logs",
                success=False,
                error_message=str(e)
            )
            raise
    
    def export_user_audit_data(self, user_id: int, format: str = 'json') -> Dict[str, Any]:
        """Export all audit data for a specific user (GDPR compliance)"""
        try:
            user_logs = self.db.query(AuditLog).filter(AuditLog.user_id == user_id).all()
            
            if format == 'json':
                data = []
                for log in user_logs:
                    data.append({
                        'timestamp': log.timestamp.isoformat(),
                        'event_type': log.event_type,
                        'event_category': log.event_category,
                        'action': log.action,
                        'success': log.success,
                        'ip_address': log.ip_address,
                        'user_agent': log.user_agent,
                        'session_id': log.session_id,
                        'resource': log.resource,
                        'metadata': log.metadata
                    })
                
                result = {
                    'user_id': user_id,
                    'export_date': datetime.utcnow().isoformat(),
                    'total_events': len(data),
                    'events': data
                }
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            self.log_event(
                event_type="user_data_exported",
                event_category="gdpr",
                action="export_user_audit_data",
                user_id=user_id,
                success=True,
                metadata={'format': format, 'events_count': len(user_logs)}
            )
            
            return result
            
        except Exception as e:
            self.log_event(
                event_type="user_data_export_error",
                event_category="gdpr",
                action="export_user_audit_data",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise