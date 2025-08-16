"""
Two-Factor Authentication Service
Supports TOTP (Time-based One-Time Passwords) and email-based verification
"""

import pyotp
import qrcode
import smtplib
import uuid
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from io import BytesIO
import base64
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from .models import User, AuditLog
from .audit_logger import AuditLogger


class TwoFactorAuth:
    """Two-Factor Authentication service"""
    
    def __init__(self, db_session: Session, email_config: Dict[str, Any], audit_logger: AuditLogger):
        self.db = db_session
        self.email_config = email_config
        self.audit_logger = audit_logger
        self.email_tokens = {}  # In production, use Redis or database
    
    def enable_2fa_totp(self, user_id: int, issuer_name: str = "NovaSuite-AI") -> Tuple[str, str, list]:
        """
        Enable TOTP-based 2FA for user
        Returns: (secret, qr_code_data_uri, backup_codes)
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Generate secret and backup codes
            secret = user.generate_2fa_secret()
            backup_codes = user.generate_backup_codes()
            
            # Generate QR code
            qr_code_uri = self._generate_qr_code(user, issuer_name)
            
            # Save changes
            self.db.commit()
            
            # Log the event
            self.audit_logger.log_event(
                event_type="2fa_setup_initiated",
                event_category="security",
                action="enable_2fa_totp",
                user_id=user_id,
                success=True,
                metadata={"method": "totp", "issuer": issuer_name}
            )
            
            return secret, qr_code_uri, backup_codes
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="2fa_setup_failed",
                event_category="security",
                action="enable_2fa_totp",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def verify_and_enable_2fa(self, user_id: int, token: str) -> bool:
        """
        Verify TOTP token and fully enable 2FA
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            if user.verify_2fa_token(token):
                user.two_factor_enabled = True
                self.db.commit()
                
                self.audit_logger.log_event(
                    event_type="2fa_enabled",
                    event_category="security",
                    action="enable_2fa_totp_confirmed",
                    user_id=user_id,
                    success=True,
                    metadata={"method": "totp"}
                )
                
                return True
            else:
                self.audit_logger.log_event(
                    event_type="2fa_verification_failed",
                    event_category="security",
                    action="enable_2fa_totp_confirmed",
                    user_id=user_id,
                    success=False,
                    error_message="Invalid token"
                )
                
                return False
                
        except Exception as e:
            self.audit_logger.log_event(
                event_type="2fa_enable_error",
                event_category="security",
                action="enable_2fa_totp_confirmed",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def disable_2fa(self, user_id: int, verification_token: str) -> bool:
        """
        Disable 2FA after verification
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Verify token or backup code
            if user.verify_2fa_token(verification_token) or user.verify_backup_code(verification_token):
                user.two_factor_enabled = False
                user.two_factor_secret = None
                user.backup_codes = None
                self.db.commit()
                
                self.audit_logger.log_event(
                    event_type="2fa_disabled",
                    event_category="security",
                    action="disable_2fa",
                    user_id=user_id,
                    success=True
                )
                
                return True
            else:
                self.audit_logger.log_event(
                    event_type="2fa_disable_failed",
                    event_category="security",
                    action="disable_2fa",
                    user_id=user_id,
                    success=False,
                    error_message="Invalid verification token"
                )
                
                return False
                
        except Exception as e:
            self.audit_logger.log_event(
                event_type="2fa_disable_error",
                event_category="security",
                action="disable_2fa",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def send_email_verification_code(self, user_id: int) -> str:
        """
        Send verification code via email
        Returns: token_id for verification
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Generate 6-digit code
            code = f"{secrets.randbelow(1000000):06d}"
            token_id = str(uuid.uuid4())
            
            # Store token (in production, use Redis with expiration)
            self.email_tokens[token_id] = {
                'user_id': user_id,
                'code': code,
                'expires_at': datetime.utcnow() + timedelta(minutes=10),
                'attempts': 0
            }
            
            # Send email
            self._send_verification_email(user.email, code)
            
            self.audit_logger.log_event(
                event_type="email_2fa_sent",
                event_category="security",
                action="send_email_verification",
                user_id=user_id,
                success=True,
                metadata={"token_id": token_id}
            )
            
            return token_id
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="email_2fa_error",
                event_category="security",
                action="send_email_verification",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def verify_email_code(self, token_id: str, code: str) -> bool:
        """
        Verify email verification code
        """
        try:
            if token_id not in self.email_tokens:
                return False
            
            token_data = self.email_tokens[token_id]
            
            # Check expiration
            if datetime.utcnow() > token_data['expires_at']:
                del self.email_tokens[token_id]
                return False
            
            # Check attempts limit
            if token_data['attempts'] >= 3:
                del self.email_tokens[token_id]
                return False
            
            token_data['attempts'] += 1
            
            # Verify code
            if token_data['code'] == code:
                user_id = token_data['user_id']
                del self.email_tokens[token_id]
                
                self.audit_logger.log_event(
                    event_type="email_2fa_verified",
                    event_category="security",
                    action="verify_email_code",
                    user_id=user_id,
                    success=True
                )
                
                return True
            else:
                self.audit_logger.log_event(
                    event_type="email_2fa_failed",
                    event_category="security",
                    action="verify_email_code",
                    user_id=token_data['user_id'],
                    success=False,
                    error_message="Invalid code"
                )
                
                return False
                
        except Exception as e:
            self.audit_logger.log_event(
                event_type="email_2fa_verify_error",
                event_category="security",
                action="verify_email_code",
                success=False,
                error_message=str(e)
            )
            raise
    
    def verify_2fa_login(self, user_id: int, token: str, token_type: str = "totp") -> bool:
        """
        Verify 2FA during login
        Supports TOTP tokens, backup codes, and email codes
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.two_factor_enabled:
                return False
            
            verified = False
            method_used = token_type
            
            if token_type == "totp":
                verified = user.verify_2fa_token(token)
            elif token_type == "backup":
                verified = user.verify_backup_code(token)
                if verified:
                    self.db.commit()  # Save backup code consumption
            elif token_type == "email":
                # For email, token should be token_id:code format
                if ':' in token:
                    token_id, code = token.split(':', 1)
                    verified = self.verify_email_code(token_id, code)
            
            self.audit_logger.log_event(
                event_type="2fa_login_verification",
                event_category="auth",
                action="verify_2fa_login",
                user_id=user_id,
                success=verified,
                metadata={"method": method_used},
                error_message=None if verified else "Invalid 2FA token"
            )
            
            return verified
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="2fa_login_error",
                event_category="auth",
                action="verify_2fa_login",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def regenerate_backup_codes(self, user_id: int, verification_token: str) -> Optional[list]:
        """
        Regenerate backup codes after verification
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Verify current 2FA token
            if user.verify_2fa_token(verification_token):
                backup_codes = user.generate_backup_codes()
                self.db.commit()
                
                self.audit_logger.log_event(
                    event_type="backup_codes_regenerated",
                    event_category="security",
                    action="regenerate_backup_codes",
                    user_id=user_id,
                    success=True
                )
                
                return backup_codes
            else:
                self.audit_logger.log_event(
                    event_type="backup_codes_regen_failed",
                    event_category="security",
                    action="regenerate_backup_codes",
                    user_id=user_id,
                    success=False,
                    error_message="Invalid verification token"
                )
                
                return None
                
        except Exception as e:
            self.audit_logger.log_event(
                event_type="backup_codes_regen_error",
                event_category="security",
                action="regenerate_backup_codes",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def _generate_qr_code(self, user: User, issuer_name: str) -> str:
        """Generate QR code data URI for 2FA setup"""
        uri = user.get_2fa_uri(issuer_name)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to data URI
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_data}"
    
    def _send_verification_email(self, email: str, code: str):
        """Send verification code via email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['smtp_user']
            msg['To'] = email
            msg['Subject'] = "NovaSuite-AI - Código de verificación 2FA"
            
            body = f"""
            <html>
            <body>
                <h2>Código de verificación de NovaSuite-AI</h2>
                <p>Su código de verificación de dos factores es:</p>
                <h1 style="color: #007bff; font-family: monospace; letter-spacing: 3px;">{code}</h1>
                <p>Este código expira en 10 minutos.</p>
                <p>Si no solicitó este código, ignore este mensaje.</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    Este es un mensaje automático, no responda a este correo.
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['smtp_user'], self.email_config['smtp_password'])
                server.send_message(msg)
                
        except Exception as e:
            raise Exception(f"Failed to send verification email: {str(e)}")
    
    def get_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """Get current 2FA status for user"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            return {
                'enabled': user.two_factor_enabled,
                'has_secret': bool(user.two_factor_secret),
                'backup_codes_count': len(user.backup_codes) if user.backup_codes else 0,
                'setup_complete': user.two_factor_enabled and bool(user.two_factor_secret)
            }
            
        except Exception as e:
            self.audit_logger.log_event(
                event_type="2fa_status_error",
                event_category="security",
                action="get_2fa_status",
                user_id=user_id,
                success=False,
                error_message=str(e)
            )
            raise