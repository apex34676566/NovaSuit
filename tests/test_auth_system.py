"""
Tests básicos para el sistema de autenticación NovaSuite-AI
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.auth import TwoFactorAuth, APIKeyManager, AuditLogger, GDPRCompliance
from core.auth.models import User, APIKey, AuditLog, GDPRRecord, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestAuthenticationSystem:
    """Test suite for the authentication system"""
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory database for testing"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def audit_logger(self, db_session):
        """Create audit logger instance"""
        return AuditLogger(db_session, log_directory="./test_logs")
    
    @pytest.fixture
    def email_config(self):
        """Email configuration for tests"""
        return {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_user': 'test@example.com',
            'smtp_password': 'test_password'
        }
    
    @pytest.fixture
    def user(self, db_session):
        """Create test user"""
        user = User(username="testuser", email="test@example.com")
        user.set_password("test_password")
        user.gdpr_consent = True
        user.gdpr_consent_date = datetime.utcnow()
        
        db_session.add(user)
        db_session.commit()
        return user
    
    def test_user_creation_and_authentication(self, db_session):
        """Test user creation and password verification"""
        # Create user
        user = User(username="newuser", email="new@example.com")
        user.set_password("secure_password")
        
        db_session.add(user)
        db_session.commit()
        
        # Test password verification
        assert user.check_password("secure_password")
        assert not user.check_password("wrong_password")
        
        # Test user attributes
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert not user.two_factor_enabled
        assert user.failed_login_attempts == 0
    
    def test_2fa_setup_and_verification(self, db_session, audit_logger, email_config, user):
        """Test 2FA setup process"""
        two_factor_auth = TwoFactorAuth(db_session, email_config, audit_logger)
        
        # Setup 2FA
        secret, qr_code, backup_codes = two_factor_auth.enable_2fa_totp(user.id)
        
        assert secret is not None
        assert qr_code.startswith("data:image/png;base64,")
        assert len(backup_codes) == 10
        assert user.two_factor_secret is not None
        assert not user.two_factor_enabled  # Not enabled until verified
        
        # Verify and enable 2FA (mock TOTP verification)
        with patch.object(user, 'verify_2fa_token', return_value=True):
            result = two_factor_auth.verify_and_enable_2fa(user.id, "123456")
            assert result is True
            
        db_session.refresh(user)
        assert user.two_factor_enabled
    
    def test_api_key_management(self, db_session, audit_logger, user):
        """Test API key creation, rotation, and verification"""
        api_key_manager = APIKeyManager(db_session, audit_logger)
        
        # Create API key
        api_key_string, api_key = api_key_manager.create_api_key(
            user_id=user.id,
            name="Test API Key",
            scopes=["read", "write"],
            expires_days=30
        )
        
        assert api_key_string.startswith("nsa_")
        assert api_key.name == "Test API Key"
        assert api_key.scopes == ["read", "write"]
        assert api_key.is_valid()
        
        # Verify API key
        verified_key = api_key_manager.verify_api_key(api_key_string)
        assert verified_key is not None
        assert verified_key.id == api_key.id
        
        # Test wrong API key
        wrong_verified = api_key_manager.verify_api_key("wrong_key")
        assert wrong_verified is None
        
        # Rotate API key
        new_key_string, updated_key = api_key_manager.rotate_api_key(api_key.id)
        
        assert new_key_string != api_key_string
        assert new_key_string.startswith("nsa_")
        
        # Old key should no longer work
        old_verified = api_key_manager.verify_api_key(api_key_string)
        assert old_verified is None
        
        # New key should work
        new_verified = api_key_manager.verify_api_key(new_key_string)
        assert new_verified is not None
    
    def test_audit_logging(self, db_session, audit_logger, user):
        """Test audit logging functionality"""
        # Log an event
        audit_logger.log_event(
            event_type="test_event",
            event_category="test",
            action="test_action",
            user_id=user.id,
            success=True,
            ip_address="192.168.1.100",
            metadata={"test_data": "test_value"}
        )
        
        # Search for the logged event
        results = audit_logger.search_audit_logs(
            filters={"user_id": user.id, "event_category": "test"},
            limit=10
        )
        
        assert results["total_count"] == 1
        assert len(results["logs"]) == 1
        
        log_entry = results["logs"][0]
        assert log_entry["event_type"] == "test_event"
        assert log_entry["action"] == "test_action"
        assert log_entry["user_id"] == user.id
        assert log_entry["success"] is True
        assert log_entry["ip_address"] == "192.168.1.100"
        assert log_entry["metadata"]["test_data"] == "test_value"
    
    def test_gdpr_consent_management(self, db_session, audit_logger, email_config, user):
        """Test GDPR consent management"""
        data_controller = {
            'name': 'Test Company',
            'address': 'Test Address',
            'email': 'privacy@test.com',
            'dpo_email': 'dpo@test.com'
        }
        
        gdpr_compliance = GDPRCompliance(
            db_session, audit_logger, email_config, data_controller
        )
        
        # Record consent
        gdpr_record = gdpr_compliance.record_consent(
            user_id=user.id,
            consent_type="explicit_consent",
            given=True,
            mechanism="web_form",
            data_categories=["personal_identifiers"],
            processing_purposes=["authentication"]
        )
        
        assert gdpr_record.user_id == user.id
        assert gdpr_record.request_type == "consent"
        assert gdpr_record.consent_given is True
        assert gdpr_record.status == "completed"
        
        # Test data access request
        gdpr_record, user_data = gdpr_compliance.process_access_request(
            user_id=user.id,
            requested_categories=["personal_identifiers"]
        )
        
        assert gdpr_record.request_type == "access"
        assert gdpr_record.access_provided is True
        assert "categories" in user_data
        assert "personal_identifiers" in user_data["categories"]
    
    def test_account_lockout(self, db_session, user):
        """Test account lockout mechanism"""
        # Simulate failed login attempts
        for i in range(5):
            user.failed_login_attempts += 1
        
        user.lock_account()
        db_session.commit()
        
        assert user.is_locked()
        assert user.failed_login_attempts == 5
        
        # Unlock account
        user.unlock_account()
        db_session.commit()
        
        assert not user.is_locked()
        assert user.failed_login_attempts == 0
    
    def test_gdpr_data_erasure(self, db_session, audit_logger, email_config, user):
        """Test GDPR data erasure functionality"""
        data_controller = {
            'name': 'Test Company',
            'address': 'Test Address', 
            'email': 'privacy@test.com',
            'dpo_email': 'dpo@test.com'
        }
        
        gdpr_compliance = GDPRCompliance(
            db_session, audit_logger, email_config, data_controller
        )
        
        original_username = user.username
        original_email = user.email
        
        # Request data erasure
        gdpr_record = gdpr_compliance.process_erasure_request(
            user_id=user.id,
            reason="User request",
            immediate=True
        )
        
        assert gdpr_record.request_type == "erasure"
        assert gdpr_record.status == "completed"
        assert gdpr_record.erasure_completed is True
        
        # Check that user data has been anonymized
        db_session.refresh(user)
        assert user.username != original_username
        assert user.email != original_email
        assert user.username.startswith("deleted_user_")
        assert user.password_hash is None
    
    def test_api_key_expiration(self, db_session, audit_logger, user):
        """Test API key expiration logic"""
        api_key_manager = APIKeyManager(db_session, audit_logger)
        
        # Create API key with short expiration
        api_key_string, api_key = api_key_manager.create_api_key(
            user_id=user.id,
            name="Short-lived Key",
            expires_days=0  # Already expired
        )
        
        # Set expiration to past
        api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.commit()
        
        assert api_key.is_expired()
        assert not api_key.is_valid()
        
        # Verification should fail for expired key
        verified_key = api_key_manager.verify_api_key(api_key_string)
        assert verified_key is None
    
    def test_compliance_report_generation(self, db_session, audit_logger, user):
        """Test compliance report generation"""
        # Generate some audit events
        events = [
            ("login", "auth", "user_login"),
            ("logout", "auth", "user_logout"),
            ("api_access", "api", "api_request"),
            ("consent_given", "gdpr", "record_consent")
        ]
        
        for event_type, category, action in events:
            audit_logger.log_event(
                event_type=event_type,
                event_category=category,
                action=action,
                user_id=user.id,
                success=True
            )
        
        # Generate compliance report
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)
        
        report = audit_logger.generate_compliance_report(
            start_date=start_date,
            end_date=end_date
        )
        
        assert "summary" in report
        assert "events_by_category" in report
        assert "events_by_type" in report
        assert report["summary"]["total_events"] == 4
        assert report["events_by_category"]["auth"] == 2
        assert report["events_by_category"]["api"] == 1
        assert report["events_by_category"]["gdpr"] == 1


def test_system_integration():
    """Integration test to verify the complete system works together"""
    # This would be a more comprehensive test in a real scenario
    # For now, just verify imports work
    from core.auth import (
        TwoFactorAuth, APIKeyManager, AuditLogger, GDPRCompliance,
        User, APIKey, AuditLog, GDPRRecord
    )
    
    assert TwoFactorAuth is not None
    assert APIKeyManager is not None
    assert AuditLogger is not None
    assert GDPRCompliance is not None
    assert User is not None
    assert APIKey is not None
    assert AuditLog is not None
    assert GDPRRecord is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])