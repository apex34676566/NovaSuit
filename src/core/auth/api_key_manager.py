"""
API Key Management with Automatic Rotation
Handles API key lifecycle, rotation every 30 days, and security monitoring
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import threading
import time
from cryptography.fernet import Fernet
import base64

from .models import User, APIKey, AuditLog
from .audit_logger import AuditLogger


class APIKeyManager:
    """API Key management with automatic rotation"""
    
    def __init__(self, db_session: Session, audit_logger: AuditLogger, encryption_key: str = None):
        self.db = db_session
        self.audit_logger = audit_logger
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)
        self._rotation_thread = None
        self._stop_rotation = False
    
    def create_api_key(self, user_id: int, name: str, scopes: List[str] = None, 
                      expires_days: int = 30, rate_limit: int = 1000,
                      ip_whitelist: List[str] = None) -> Tuple[str, APIKey]:
        """
        Create new API key for user
        Returns: (api_key_string, api_key_object)
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Generate secure API key
            api_key_string = self._generate_secure_key()
            
            # Create API key object
            api_key = APIKey(
                user_id=user_id,
                name=name,
                scopes=scopes or [],
                expires_days=expires_days
            )
            api_key.rate_limit = rate_limit
            api_key.ip_whitelist = ip_whitelist or []
            
            # Store encrypted key hash
            api_key.key_hash = self._encrypt_key(api_key_string)
            
            self.db.add(api_key)
            self.db.commit()
            
            self.audit_logger.log_event(
                event_type="api_key_created",
                event_category="api",
                action="create_api_key",
                user_id=user_id,
                success=True,
                metadata={
                    "api_key_id": api_key.id,
                    "name": name,
                    "scopes": scopes,
                    "expires_at": api_key.expires_at.isoformat(),
                    "rate_limit": rate_limit
                }
            )
            
            return api_key_string, api_key
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_creation_failed",
                event_category="api",
                action="create_api_key",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def rotate_api_key(self, api_key_id: int, extend_expiration: bool = True) -> Tuple[str, APIKey]:
        """
        Rotate existing API key
        Returns: (new_api_key_string, updated_api_key_object)
        """
        try:
            api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
            if not api_key:
                raise ValueError("API key not found")
            
            old_key_hash = api_key.key_hash
            
            # Generate new key
            new_api_key_string = self._generate_secure_key()
            api_key.key_hash = self._encrypt_key(new_api_key_string)
            
            # Extend expiration if requested
            if extend_expiration:
                api_key.expires_at = datetime.utcnow() + timedelta(days=30)
            
            # Reset usage statistics
            api_key.usage_count = 0
            api_key.last_used = None
            
            self.db.commit()
            
            self.audit_logger.log_event(
                event_type="api_key_rotated",
                event_category="api",
                action="rotate_api_key",
                user_id=api_key.user_id,
                success=True,
                metadata={
                    "api_key_id": api_key_id,
                    "name": api_key.name,
                    "old_key_hash": old_key_hash[:10] + "...",  # Log only partial hash
                    "new_expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None
                }
            )
            
            return new_api_key_string, api_key
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_rotation_failed",
                event_category="api",
                action="rotate_api_key",
                success=False,
                error_message=str(e),
                metadata={"api_key_id": api_key_id}
            )
            raise
    
    def verify_api_key(self, api_key_string: str, required_scopes: List[str] = None,
                      client_ip: str = None) -> Optional[APIKey]:
        """
        Verify API key and check permissions
        Returns API key object if valid, None otherwise
        """
        try:
            # Try to find matching key by checking all active keys
            active_keys = self.db.query(APIKey).filter(
                and_(
                    APIKey.is_active == True,
                    or_(
                        APIKey.expires_at.is_(None),
                        APIKey.expires_at > datetime.utcnow()
                    )
                )
            ).all()
            
            api_key = None
            for key in active_keys:
                try:
                    decrypted_key = self._decrypt_key(key.key_hash)
                    if secrets.compare_digest(decrypted_key, api_key_string):
                        api_key = key
                        break
                except:
                    continue  # Invalid encrypted key, skip
            
            if not api_key:
                self.audit_logger.log_event(
                    event_type="api_key_verification_failed",
                    event_category="api",
                    action="verify_api_key",
                    success=False,
                    error_message="Invalid API key",
                    metadata={"client_ip": client_ip}
                )
                return None
            
            # Check if key is still valid
            if not api_key.is_valid():
                self.audit_logger.log_event(
                    event_type="api_key_expired",
                    event_category="api",
                    action="verify_api_key",
                    user_id=api_key.user_id,
                    success=False,
                    error_message="API key expired or inactive",
                    metadata={"api_key_id": api_key.id, "client_ip": client_ip}
                )
                return None
            
            # Check IP whitelist
            if api_key.ip_whitelist and client_ip:
                if client_ip not in api_key.ip_whitelist:
                    self.audit_logger.log_event(
                        event_type="api_key_ip_blocked",
                        event_category="security",
                        action="verify_api_key",
                        user_id=api_key.user_id,
                        success=False,
                        error_message="IP not in whitelist",
                        metadata={"api_key_id": api_key.id, "client_ip": client_ip}
                    )
                    return None
            
            # Check required scopes
            if required_scopes:
                if not all(scope in api_key.scopes for scope in required_scopes):
                    self.audit_logger.log_event(
                        event_type="api_key_insufficient_scope",
                        event_category="security",
                        action="verify_api_key",
                        user_id=api_key.user_id,
                        success=False,
                        error_message="Insufficient API key scope",
                        metadata={
                            "api_key_id": api_key.id,
                            "required_scopes": required_scopes,
                            "available_scopes": api_key.scopes
                        }
                    )
                    return None
            
            # Record successful usage
            api_key.record_usage()
            self.db.commit()
            
            self.audit_logger.log_event(
                event_type="api_key_used",
                event_category="api",
                action="verify_api_key",
                user_id=api_key.user_id,
                success=True,
                metadata={
                    "api_key_id": api_key.id,
                    "usage_count": api_key.usage_count,
                    "client_ip": client_ip
                }
            )
            
            return api_key
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_verification_error",
                event_category="api",
                action="verify_api_key",
                success=False,
                error_message=str(e),
                metadata={"client_ip": client_ip}
            )
            raise
    
    def revoke_api_key(self, api_key_id: int, reason: str = "Manual revocation") -> bool:
        """Revoke API key"""
        try:
            api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
            if not api_key:
                raise ValueError("API key not found")
            
            api_key.is_active = False
            self.db.commit()
            
            self.audit_logger.log_event(
                event_type="api_key_revoked",
                event_category="api",
                action="revoke_api_key",
                user_id=api_key.user_id,
                success=True,
                metadata={
                    "api_key_id": api_key_id,
                    "name": api_key.name,
                    "reason": reason
                }
            )
            
            return True
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_revocation_failed",
                event_category="api",
                action="revoke_api_key",
                success=False,
                error_message=str(e),
                metadata={"api_key_id": api_key_id}
            )
            raise
    
    def list_user_api_keys(self, user_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List API keys for user"""
        try:
            query = self.db.query(APIKey).filter(APIKey.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(APIKey.is_active == True)
            
            api_keys = query.all()
            
            result = []
            for key in api_keys:
                result.append({
                    'id': key.id,
                    'name': key.name,
                    'scopes': key.scopes,
                    'created_at': key.created_at.isoformat(),
                    'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                    'last_used': key.last_used.isoformat() if key.last_used else None,
                    'usage_count': key.usage_count,
                    'is_active': key.is_active,
                    'is_expired': key.is_expired(),
                    'rate_limit': key.rate_limit,
                    'ip_whitelist': key.ip_whitelist
                })
            
            return result
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_list_error",
                event_category="api",
                action="list_user_api_keys",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def start_automatic_rotation(self, check_interval_hours: int = 24):
        """Start automatic API key rotation background process"""
        if self._rotation_thread and self._rotation_thread.is_alive():
            return  # Already running
        
        self._stop_rotation = False
        self._rotation_thread = threading.Thread(
            target=self._rotation_worker,
            args=(check_interval_hours,),
            daemon=True
        )
        self._rotation_thread.start()
        
        self.audit_logger.log_event(
            event_type="auto_rotation_started",
            event_category="api",
            action="start_automatic_rotation",
            success=True,
            metadata={"check_interval_hours": check_interval_hours}
        )
    
    def stop_automatic_rotation(self):
        """Stop automatic API key rotation"""
        self._stop_rotation = True
        if self._rotation_thread:
            self._rotation_thread.join(timeout=5)
        
        self.audit_logger.log_event(
            event_type="auto_rotation_stopped",
            event_category="api",
            action="stop_automatic_rotation",
            success=True
        )
    
    def rotate_expiring_keys(self, days_before_expiry: int = 7) -> List[Dict[str, Any]]:
        """
        Rotate API keys that are expiring soon
        Returns list of rotated keys
        """
        try:
            expiring_date = datetime.utcnow() + timedelta(days=days_before_expiry)
            
            expiring_keys = self.db.query(APIKey).filter(
                and_(
                    APIKey.is_active == True,
                    APIKey.expires_at <= expiring_date,
                    APIKey.expires_at > datetime.utcnow()
                )
            ).all()
            
            rotated_keys = []
            
            for api_key in expiring_keys:
                try:
                    new_key_string, updated_key = self.rotate_api_key(api_key.id)
                    
                    rotated_keys.append({
                        'api_key_id': api_key.id,
                        'user_id': api_key.user_id,
                        'name': api_key.name,
                        'old_expires_at': api_key.expires_at.isoformat(),
                        'new_expires_at': updated_key.expires_at.isoformat(),
                        'new_key': new_key_string  # In production, send via secure channel
                    })
                    
                except Exception as e:
                    self.audit_logger.log_event(
                        event_type="auto_rotation_failed",
                        event_category="api",
                        action="rotate_expiring_keys",
                        user_id=api_key.user_id,
                        success=False,
                        error_message=str(e),
                        metadata={"api_key_id": api_key.id}
                    )
            
            if rotated_keys:
                self.audit_logger.log_event(
                    event_type="bulk_rotation_completed",
                    event_category="api",
                    action="rotate_expiring_keys",
                    success=True,
                    metadata={
                        "rotated_count": len(rotated_keys),
                        "days_before_expiry": days_before_expiry
                    }
                )
            
            return rotated_keys
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="bulk_rotation_error",
                event_category="api",
                action="rotate_expiring_keys",
                success=False,
                error_message=str(e)
            )
            raise
    
    def _generate_secure_key(self) -> str:
        """Generate cryptographically secure API key"""
        # Generate 32 bytes of random data and encode as hex
        random_bytes = secrets.token_bytes(32)
        return f"nsa_{base64.urlsafe_b64encode(random_bytes).decode().rstrip('=')}"
    
    def _encrypt_key(self, key: str) -> str:
        """Encrypt API key for storage"""
        return self.cipher_suite.encrypt(key.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt stored API key"""
        return self.cipher_suite.decrypt(encrypted_key.encode()).decode()
    
    def _rotation_worker(self, check_interval_hours: int):
        """Background worker for automatic rotation"""
        while not self._stop_rotation:
            try:
                # Check every hour but only rotate based on configured interval
                time.sleep(3600)  # 1 hour
                
                if not self._stop_rotation:
                    # Rotate keys expiring in the next 7 days
                    rotated = self.rotate_expiring_keys(days_before_expiry=7)
                    
                    if rotated:
                        # In production, notify users about rotated keys
                        self._notify_users_about_rotation(rotated)
                        
            except Exception as e:
                self.audit_logger.log_event(
                    event_type="rotation_worker_error",
                    event_category="api",
                    action="automatic_rotation",
                    success=False,
                    error_message=str(e)
                )
                # Continue running despite errors
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _notify_users_about_rotation(self, rotated_keys: List[Dict[str, Any]]):
        """Notify users about rotated API keys"""
        # Group by user
        user_rotations = {}
        for key_info in rotated_keys:
            user_id = key_info['user_id']
            if user_id not in user_rotations:
                user_rotations[user_id] = []
            user_rotations[user_id].append(key_info)
        
        # Log notification events (in production, send actual emails/notifications)
        for user_id, keys in user_rotations.items():
            self.audit_logger.log_event(
                event_type="key_rotation_notification",
                event_category="api",
                action="notify_user_rotation",
                user_id=user_id,
                success=True,
                metadata={
                    "rotated_keys_count": len(keys),
                    "rotated_keys": [k['name'] for k in keys]
                }
            )
    
    def get_api_key_stats(self, user_id: int = None) -> Dict[str, Any]:
        """Get API key usage statistics"""
        try:
            query = self.db.query(APIKey)
            if user_id:
                query = query.filter(APIKey.user_id == user_id)
            
            all_keys = query.all()
            
            now = datetime.utcnow()
            stats = {
                'total_keys': len(all_keys),
                'active_keys': len([k for k in all_keys if k.is_active]),
                'expired_keys': len([k for k in all_keys if k.is_expired()]),
                'expiring_soon': len([k for k in all_keys if k.expires_at and k.expires_at <= now + timedelta(days=7)]),
                'total_usage': sum(k.usage_count for k in all_keys),
                'keys_by_scope': {}
            }
            
            # Count keys by scope
            for key in all_keys:
                for scope in key.scopes or []:
                    if scope not in stats['keys_by_scope']:
                        stats['keys_by_scope'][scope] = 0
                    stats['keys_by_scope'][scope] += 1
            
            return stats
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="api_key_stats_error",
                event_category="api",
                action="get_api_key_stats",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise