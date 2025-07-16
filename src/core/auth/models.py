"""
Database models for authentication, audit logging, and GDPR compliance
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import pyotp
import qrcode
from io import BytesIO
import base64

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128))
    
    # 2FA Settings
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(32))
    backup_codes = Column(JSON)  # Array of backup codes
    
    # Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # GDPR
    gdpr_consent = Column(Boolean, default=False)
    gdpr_consent_date = Column(DateTime)
    data_retention_until = Column(DateTime)
    
    # Relationships
    api_keys = relationship("APIKey", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    gdpr_records = relationship("GDPRRecord", back_populates="user")
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_2fa_secret(self):
        """Generate new 2FA secret"""
        self.two_factor_secret = pyotp.random_base32()
        return self.two_factor_secret
    
    def get_2fa_uri(self, issuer_name="NovaSuite-AI"):
        """Get 2FA URI for QR code"""
        if not self.two_factor_secret:
            self.generate_2fa_secret()
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.provisioning_uri(
            name=self.email,
            issuer_name=issuer_name
        )
    
    def verify_2fa_token(self, token):
        """Verify 2FA token"""
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token, valid_window=1)
    
    def verify_backup_code(self, code):
        """Verify and consume backup code"""
        if not self.backup_codes or code not in self.backup_codes:
            return False
        
        self.backup_codes.remove(code)
        return True
    
    def generate_backup_codes(self, count=10):
        """Generate new backup codes"""
        self.backup_codes = [str(uuid.uuid4())[:8] for _ in range(count)]
        return self.backup_codes
    
    def is_locked(self):
        """Check if account is locked"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration"""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    def unlock_account(self):
        """Unlock account"""
        self.locked_until = None
        self.failed_login_attempts = 0


class APIKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    key_hash = Column(String(128), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    
    # Permissions and Scope
    scopes = Column(JSON)  # Array of allowed scopes
    rate_limit = Column(Integer, default=1000)  # Requests per hour
    
    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_used = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Security
    ip_whitelist = Column(JSON)  # Array of allowed IPs
    usage_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    def __init__(self, user_id, name, scopes=None, expires_days=30):
        self.user_id = user_id
        self.name = name
        self.scopes = scopes or []
        self.expires_at = datetime.utcnow() + timedelta(days=expires_days)
        self.key_hash = self.generate_key()
    
    def generate_key(self):
        """Generate new API key"""
        key = str(uuid.uuid4()) + str(uuid.uuid4()).replace('-', '')
        self.key_hash = generate_password_hash(key)
        return key
    
    def verify_key(self, key):
        """Verify API key"""
        return check_password_hash(self.key_hash, key)
    
    def is_expired(self):
        """Check if API key is expired"""
        return self.expires_at and self.expires_at < datetime.utcnow()
    
    def is_valid(self):
        """Check if API key is valid"""
        return self.is_active and not self.is_expired()
    
    def record_usage(self):
        """Record API key usage"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Event Details
    event_type = Column(String(50), nullable=False)  # login, logout, 2fa_enable, api_key_create, etc.
    event_category = Column(String(30), nullable=False)  # auth, security, gdpr, api, etc.
    action = Column(String(100), nullable=False)
    resource = Column(String(100))
    
    # Context
    ip_address = Column(String(45))
    user_agent = Column(Text)
    session_id = Column(String(100))
    api_key_id = Column(Integer, ForeignKey('api_keys.id'), nullable=True)
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Metadata
    metadata = Column(JSON)  # Additional event-specific data
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # GDPR
    retention_until = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __init__(self, event_type, event_category, action, user_id=None, **kwargs):
        self.event_type = event_type
        self.event_category = event_category
        self.action = action
        self.user_id = user_id
        
        # Set retention period (7 years for financial data, 3 years for general logs)
        if event_category in ['financial', 'compliance']:
            self.retention_until = datetime.utcnow() + timedelta(days=2555)  # 7 years
        else:
            self.retention_until = datetime.utcnow() + timedelta(days=1095)  # 3 years
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class GDPRRecord(Base):
    __tablename__ = 'gdpr_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Request Details
    request_type = Column(String(30), nullable=False)  # consent, access, rectification, erasure, portability
    request_date = Column(DateTime, default=datetime.utcnow)
    processed_date = Column(DateTime)
    status = Column(String(20), default='pending')  # pending, processing, completed, rejected
    
    # Legal Basis
    legal_basis = Column(String(50))  # consent, contract, legal_obligation, vital_interests, public_task, legitimate_interests
    
    # Processing Details
    data_categories = Column(JSON)  # Array of data categories involved
    processing_purposes = Column(JSON)  # Array of processing purposes
    third_parties = Column(JSON)  # Array of third parties data is shared with
    
    # Consent Details
    consent_given = Column(Boolean)
    consent_withdrawn = Column(Boolean, default=False)
    consent_mechanism = Column(String(100))  # how consent was obtained
    
    # Data Subject Rights
    access_provided = Column(Boolean, default=False)
    rectification_completed = Column(Boolean, default=False)
    erasure_completed = Column(Boolean, default=False)
    portability_provided = Column(Boolean, default=False)
    
    # Response Details
    response_data = Column(JSON)
    response_format = Column(String(20))  # json, xml, csv, pdf
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="gdpr_records")
    
    def __init__(self, user_id, request_type, **kwargs):
        self.user_id = user_id
        self.request_type = request_type
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class LegalChangeLog(Base):
    __tablename__ = 'legal_change_logs'
    
    id = Column(Integer, primary_key=True)
    
    # Change Details
    change_type = Column(String(50), nullable=False)  # privacy_policy, terms_of_service, gdpr_update, etc.
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    
    # Legal Context
    jurisdiction = Column(String(100))  # EU, US, UK, etc.
    regulation = Column(String(100))  # GDPR, CCPA, etc.
    compliance_deadline = Column(DateTime)
    
    # Implementation
    implementation_status = Column(String(20), default='pending')  # pending, in_progress, completed
    implementation_date = Column(DateTime)
    impact_assessment = Column(Text)
    
    # Notification
    users_notified = Column(Boolean, default=False)
    notification_date = Column(DateTime)
    notification_method = Column(String(50))  # email, in_app, website_banner
    
    # Metadata
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Version Control
    version = Column(String(20))
    previous_version_id = Column(Integer, ForeignKey('legal_change_logs.id'))
    
    def __init__(self, change_type, title, description, **kwargs):
        self.change_type = change_type
        self.title = title
        self.description = description
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)