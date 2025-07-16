"""
NovaSuite-AI Main Application
Flask application with 2FA authentication, API key rotation, audit logging, and GDPR compliance
"""

from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import os
from functools import wraps
import threading

# Import our authentication modules
from core.auth import (
    TwoFactorAuth, APIKeyManager, AuditLogger, GDPRCompliance,
    User, APIKey, AuditLog, GDPRRecord, Base
)

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///novasuite.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # Email configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USER = os.environ.get('SMTP_USER') or 'noreply@novasuite.ai'
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or 'password'
    
    # GDPR Data Controller Information
    DATA_CONTROLLER = {
        'name': 'NovaSuite-AI',
        'address': 'Spain',
        'email': 'privacy@novasuite.ai',
        'dpo_email': 'dpo@novasuite.ai'
    }

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

# Create database tables
with app.app_context():
    Base.metadata.create_all(db.engine)

# Initialize our authentication services
email_config = {
    'smtp_server': app.config['SMTP_SERVER'],
    'smtp_port': app.config['SMTP_PORT'],
    'smtp_user': app.config['SMTP_USER'],
    'smtp_password': app.config['SMTP_PASSWORD']
}

audit_logger = AuditLogger(db.session)
two_factor_auth = TwoFactorAuth(db.session, email_config, audit_logger)
api_key_manager = APIKeyManager(db.session, audit_logger)
gdpr_compliance = GDPRCompliance(
    db.session, 
    audit_logger, 
    email_config, 
    app.config['DATA_CONTROLLER']
)

# Start automatic API key rotation
api_key_manager.start_automatic_rotation()

# Helper decorators
def api_key_required(scopes=None):
    """Decorator to require valid API key"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return jsonify({'error': 'API key required'}), 401
            
            client_ip = get_remote_address()
            verified_key = api_key_manager.verify_api_key(
                api_key, 
                required_scopes=scopes,
                client_ip=client_ip
            )
            
            if not verified_key:
                return jsonify({'error': 'Invalid API key'}), 401
            
            request.api_key = verified_key
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_request_info():
    """Get request information for logging"""
    return {
        'ip_address': get_remote_address(),
        'user_agent': request.headers.get('User-Agent'),
        'session_id': session.get('session_id')
    }

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """User registration with GDPR consent"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        gdpr_consent = data.get('gdpr_consent', False)
        
        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password required'}), 400
        
        if not gdpr_consent:
            return jsonify({'error': 'GDPR consent required'}), 400
        
        # Check if user exists
        if db.session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first():
            return jsonify({'error': 'User already exists'}), 409
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        user.gdpr_consent = True
        user.gdpr_consent_date = datetime.utcnow()
        
        db.session.add(user)
        db.session.commit()
        
        # Record GDPR consent
        gdpr_compliance.record_consent(
            user_id=user.id,
            consent_type='registration',
            given=True,
            mechanism='web_form',
            data_categories=['personal_identifiers', 'authentication_data'],
            processing_purposes=['authentication', 'service_provision']
        )
        
        audit_logger.log_authentication_event(
            user_id=user.id,
            event_type='registration',
            success=True,
            **get_request_info()
        )
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user.id
        }), 201
        
    except Exception as e:
        audit_logger.log_authentication_event(
            user_id=None,
            event_type='registration',
            success=False,
            **get_request_info(),
            additional_data={'error': str(e)}
        )
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """User login with optional 2FA"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        totp_token = data.get('totp_token')
        backup_code = data.get('backup_code')
        email_code = data.get('email_code')
        token_id = data.get('token_id')
        
        if not all([username, password]):
            return jsonify({'error': 'Username and password required'}), 400
        
        # Find user
        user = db.session.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not user.check_password(password):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.lock_account()
                db.session.commit()
                
                audit_logger.log_authentication_event(
                    user_id=user.id,
                    event_type='login_failed',
                    success=False,
                    **get_request_info(),
                    additional_data={'reason': 'invalid_credentials'}
                )
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if account is locked
        if user.is_locked():
            audit_logger.log_authentication_event(
                user_id=user.id,
                event_type='login_blocked',
                success=False,
                **get_request_info(),
                additional_data={'reason': 'account_locked'}
            )
            return jsonify({'error': 'Account locked due to failed attempts'}), 423
        
        # Handle 2FA if enabled
        if user.two_factor_enabled:
            if totp_token:
                if not two_factor_auth.verify_2fa_login(user.id, totp_token, 'totp'):
                    return jsonify({'error': 'Invalid 2FA token'}), 401
            elif backup_code:
                if not two_factor_auth.verify_2fa_login(user.id, backup_code, 'backup'):
                    return jsonify({'error': 'Invalid backup code'}), 401
            elif email_code and token_id:
                email_token = f"{token_id}:{email_code}"
                if not two_factor_auth.verify_2fa_login(user.id, email_token, 'email'):
                    return jsonify({'error': 'Invalid email code'}), 401
            else:
                # Send email verification code
                token_id = two_factor_auth.send_email_verification_code(user.id)
                return jsonify({
                    'requires_2fa': True,
                    'methods': ['totp', 'backup_code', 'email'],
                    'email_token_id': token_id
                }), 200
        
        # Successful login
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(
            identity=user.id,
            additional_claims={'username': user.username}
        )
        
        session['session_id'] = f"sess_{user.id}_{datetime.utcnow().timestamp()}"
        
        audit_logger.log_authentication_event(
            user_id=user.id,
            event_type='login_success',
            success=True,
            **get_request_info()
        )
        
        return jsonify({
            'access_token': access_token,
            'user_id': user.id,
            'username': user.username,
            'has_2fa': user.two_factor_enabled
        }), 200
        
    except Exception as e:
        audit_logger.log_authentication_event(
            user_id=None,
            event_type='login_error',
            success=False,
            **get_request_info(),
            additional_data={'error': str(e)}
        )
        return jsonify({'error': 'Login failed'}), 500

# 2FA Management Routes
@app.route('/api/auth/2fa/setup', methods=['POST'])
@jwt_required()
def setup_2fa():
    """Setup TOTP-based 2FA"""
    try:
        user_id = get_jwt_identity()
        
        secret, qr_code, backup_codes = two_factor_auth.enable_2fa_totp(user_id)
        
        return jsonify({
            'secret': secret,
            'qr_code': qr_code,
            'backup_codes': backup_codes,
            'message': 'Scan QR code with authenticator app and verify with a token'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/2fa/verify', methods=['POST'])
@jwt_required()
def verify_2fa_setup():
    """Verify and enable 2FA"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token required'}), 400
        
        if two_factor_auth.verify_and_enable_2fa(user_id, token):
            return jsonify({'message': '2FA enabled successfully'}), 200
        else:
            return jsonify({'error': 'Invalid token'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/2fa/disable', methods=['POST'])
@jwt_required()
def disable_2fa():
    """Disable 2FA"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Verification token required'}), 400
        
        if two_factor_auth.disable_2fa(user_id, token):
            return jsonify({'message': '2FA disabled successfully'}), 200
        else:
            return jsonify({'error': 'Invalid verification token'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API Key Management Routes
@app.route('/api/keys', methods=['POST'])
@jwt_required()
def create_api_key():
    """Create new API key"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        name = data.get('name')
        scopes = data.get('scopes', [])
        expires_days = data.get('expires_days', 30)
        rate_limit = data.get('rate_limit', 1000)
        ip_whitelist = data.get('ip_whitelist', [])
        
        if not name:
            return jsonify({'error': 'API key name required'}), 400
        
        api_key_string, api_key = api_key_manager.create_api_key(
            user_id=user_id,
            name=name,
            scopes=scopes,
            expires_days=expires_days,
            rate_limit=rate_limit,
            ip_whitelist=ip_whitelist
        )
        
        return jsonify({
            'api_key': api_key_string,
            'api_key_id': api_key.id,
            'expires_at': api_key.expires_at.isoformat(),
            'warning': 'Store this key securely. It will not be shown again.'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys', methods=['GET'])
@jwt_required()
def list_api_keys():
    """List user's API keys"""
    try:
        user_id = get_jwt_identity()
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        keys = api_key_manager.list_user_api_keys(user_id, include_inactive)
        
        return jsonify({'api_keys': keys}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/keys/<int:key_id>/rotate', methods=['POST'])
@jwt_required()
def rotate_api_key(key_id):
    """Rotate API key"""
    try:
        user_id = get_jwt_identity()
        
        # Verify key belongs to user
        api_key = db.session.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()
        
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        new_key_string, updated_key = api_key_manager.rotate_api_key(key_id)
        
        return jsonify({
            'new_api_key': new_key_string,
            'expires_at': updated_key.expires_at.isoformat(),
            'warning': 'Update your applications with the new key. Old key is now invalid.'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GDPR Compliance Routes
@app.route('/api/gdpr/consent', methods=['POST'])
@jwt_required()
def record_gdpr_consent():
    """Record GDPR consent"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        consent_given = data.get('consent_given', True)
        data_categories = data.get('data_categories', [])
        processing_purposes = data.get('processing_purposes', [])
        
        gdpr_record = gdpr_compliance.record_consent(
            user_id=user_id,
            consent_type='explicit_consent',
            given=consent_given,
            mechanism='api_request',
            data_categories=data_categories,
            processing_purposes=processing_purposes
        )
        
        return jsonify({
            'message': 'Consent recorded successfully',
            'gdpr_record_id': gdpr_record.id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/data-access', methods=['POST'])
@jwt_required()
def request_data_access():
    """Request data access (Article 15)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        requested_categories = data.get('categories')
        response_format = data.get('format', 'json')
        
        gdpr_record, user_data = gdpr_compliance.process_access_request(
            user_id=user_id,
            requested_categories=requested_categories,
            response_format=response_format
        )
        
        return jsonify({
            'message': 'Data access request processed',
            'gdpr_record_id': gdpr_record.id,
            'data': user_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/data-portability', methods=['POST'])
@jwt_required()
def request_data_portability():
    """Request data portability (Article 20)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        export_format = data.get('format', 'json')
        
        gdpr_record, export_path = gdpr_compliance.process_portability_request(
            user_id=user_id,
            export_format=export_format
        )
        
        return jsonify({
            'message': 'Data export prepared',
            'gdpr_record_id': gdpr_record.id,
            'download_info': 'Export file created - contact support for download'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/erasure', methods=['POST'])
@jwt_required()
def request_data_erasure():
    """Request data erasure (Article 17)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        reason = data.get('reason', 'User request')
        immediate = data.get('immediate', False)
        
        gdpr_record = gdpr_compliance.process_erasure_request(
            user_id=user_id,
            reason=reason,
            immediate=immediate
        )
        
        return jsonify({
            'message': 'Data erasure request processed',
            'gdpr_record_id': gdpr_record.id,
            'status': gdpr_record.status
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin Routes
@app.route('/api/admin/audit/logs')
@api_key_required(['admin', 'audit'])
def search_audit_logs():
    """Search audit logs (Admin only)"""
    try:
        filters = {}
        
        # Extract filters from query parameters
        if request.args.get('user_id'):
            filters['user_id'] = int(request.args.get('user_id'))
        if request.args.get('event_category'):
            filters['event_category'] = request.args.get('event_category')
        if request.args.get('start_date'):
            filters['start_date'] = datetime.fromisoformat(request.args.get('start_date'))
        if request.args.get('end_date'):
            filters['end_date'] = datetime.fromisoformat(request.args.get('end_date'))
        
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        results = audit_logger.search_audit_logs(filters, limit, offset)
        
        return jsonify(results), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/compliance/report')
@api_key_required(['admin', 'compliance'])
def generate_compliance_report():
    """Generate compliance report (Admin only)"""
    try:
        start_date = datetime.fromisoformat(request.args.get('start_date'))
        end_date = datetime.fromisoformat(request.args.get('end_date'))
        categories = request.args.getlist('categories')
        
        report = audit_logger.generate_compliance_report(
            start_date=start_date,
            end_date=end_date,
            categories=categories if categories else None
        )
        
        return jsonify(report), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/legal/changes', methods=['POST'])
@api_key_required(['admin', 'legal'])
def log_legal_change():
    """Log important legal change"""
    try:
        data = request.get_json()
        
        change_type = data.get('change_type')
        title = data.get('title')
        description = data.get('description')
        jurisdiction = data.get('jurisdiction', 'EU')
        regulation = data.get('regulation', 'GDPR')
        compliance_deadline = None
        
        if data.get('compliance_deadline'):
            compliance_deadline = datetime.fromisoformat(data.get('compliance_deadline'))
        
        legal_change = gdpr_compliance.log_legal_change(
            change_type=change_type,
            title=title,
            description=description,
            jurisdiction=jurisdiction,
            regulation=regulation,
            compliance_deadline=compliance_deadline,
            created_by=f"api_key_{request.api_key.id}"
        )
        
        return jsonify({
            'message': 'Legal change logged successfully',
            'change_id': legal_change.id,
            'version': legal_change.version
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Dashboard Route
@app.route('/api/dashboard/gdpr')
@jwt_required()
def gdpr_dashboard():
    """Get GDPR compliance dashboard"""
    try:
        user_id = get_jwt_identity()
        dashboard_data = gdpr_compliance.get_gdpr_dashboard(user_id)
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Health check
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'database': 'up',
            'audit_logging': 'up',
            'api_key_rotation': 'up'
        }
    }), 200

# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    audit_logger.log_security_event(
        event_type='rate_limit_exceeded',
        description='Rate limit exceeded',
        severity='medium',
        ip_address=get_remote_address()
    )
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    audit_logger.log_security_event(
        event_type='internal_server_error',
        description='Internal server error occurred',
        severity='high',
        additional_data={'error': str(e)}
    )
    return jsonify({'error': 'Internal server error'}), 500

# Cleanup scheduled task
def cleanup_task():
    """Background task for cleanup operations"""
    with app.app_context():
        try:
            # Cleanup expired audit logs
            audit_logger.cleanup_expired_logs()
            
            # Process scheduled GDPR deletions
            gdpr_compliance.process_scheduled_deletions()
            
        except Exception as e:
            audit_logger.log_event(
                event_type='cleanup_task_error',
                event_category='system',
                action='background_cleanup',
                success=False,
                error_message=str(e)
            )

# Schedule cleanup task to run daily
cleanup_thread = threading.Timer(86400, cleanup_task)  # 24 hours
cleanup_thread.daemon = True
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)