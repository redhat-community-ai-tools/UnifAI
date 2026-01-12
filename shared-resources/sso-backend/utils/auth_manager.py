"""
Authentication Manager for Keycloak SSO Integration
Handles user authentication, session management, and token validation
"""
from datetime import datetime, timedelta
from functools import wraps
import os
from flask import request, jsonify, session, redirect, url_for, current_app
from authlib.integrations.flask_client import OAuth
from authlib.common.errors import AuthlibBaseError
from shared.logger import logger
from config.app_config import AppConfig
from urllib.parse import quote

config = AppConfig.get_instance()

class AuthManager:
    def __init__(self, app=None):
        self.app = app
        self.oauth = None
        self.keycloak_client = None
        self.backend_env = config.get('backend_env', 'development')
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the auth manager with Flask app"""
        self.app = app
        
        # Set up secret key for sessions (required for secure session management)
        # The secret_key should be configured in app_config for both dev and production
        if not app.secret_key:
            app.secret_key = config.get('secret_key', os.urandom(24))
        
        # Configure OAuth
        self.oauth = OAuth(app)
        
        # Register Keycloak client
        keycloak_base_url = config.keycloak_base_url
        client_id = config.client_id
        client_secret = config.client_secret
        realm = config.get('keycloak_realm', 'master')
        
        if not all([keycloak_base_url, client_id, client_secret]):
            raise ValueError("Missing required Keycloak configuration")
        
        self.keycloak_client = self.oauth.register(
            name='keycloak',
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=f"{keycloak_base_url}/realms/{realm}/.well-known/openid-configuration",
            client_kwargs={
                'scope': 'openid email profile',
            }
        )
        
        # Register auth routes
        self._register_auth_routes()
        
        # Set up session configuration
        app.config.update({
            'SESSION_COOKIE_SECURE': True,  # Required for SameSite=None
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'None',  # Must be 'None' for cross-origin
            'PERMANENT_SESSION_LIFETIME': timedelta(hours=10)  # 10 hour sessions to match OIDC
        })
    
    def _register_auth_routes(self):
        """Register authentication routes"""
        
        @self.app.route('/api/auth/login')
        def login():
            """Initiate OAuth login flow"""
            # Get the state parameter from frontend (contains original URL encoded by client)
            # State is required by our protocol - frontend must always provide it
            client_state = request.args.get('state')
            
            if not client_state:
                return jsonify({'error': 'State parameter is required'}), 400
            
            # Get the OAuth callback redirect URI
            redirect_uri = config.get(
                'redirect_url',
                url_for('auth_callback', _external=True, _scheme='https') 
                if config.backend_env == "production" 
                else f"http://{config.hostname_local}:{config.port}/api/auth/callback"
            )
            
            # Pass the client-provided state through to Keycloak
            # Keycloak will echo it back in the callback
            return self.keycloak_client.authorize_redirect(redirect_uri, state=client_state)

        @self.app.route('/api/auth/callback')
        def auth_callback():
            """Handle OAuth callback"""
            # Get the state parameter that Keycloak echoed back
            # This contains the original URL encoded by the frontend
            request_state = request.args.get('state', '')
            
            try:
                # Process the OAuth callback - exchange authorization code for tokens
                token = self.keycloak_client.authorize_access_token()
                userinfo = self.keycloak_client.userinfo()
                
                # Calculate session expiration (10 hours from now)
                session_created_at = datetime.now()
                session_expires_at = session_created_at + timedelta(hours=10)
                
                # Store user info in session
                session.permanent = True
                session['user'] = {
                    'username': userinfo.get('preferred_username'),
                    'email': userinfo.get('email'),
                    'name': userinfo.get('name'),
                    'sub': userinfo.get('sub'),
                    'session_created_at': session_created_at.timestamp(),
                    'session_expires_at': session_expires_at.timestamp(),
                    'token_expires_at': token.get('expires_at', 0)
                }
                session['access_token'] = token.get('access_token')
                session['refresh_token'] = token.get('refresh_token')
                session['token_expires_at'] = token.get('expires_at', 0)
                
                logger.info(f"User {userinfo.get('preferred_username')} authenticated successfully")
                
                # Redirect to frontend with auth status and state parameter
                # Frontend will extract the original URL from state and restore it
                state_param = f"&state={quote(request_state, safe='')}" if request_state else ""
                final_url = f"{config.frontend_url}/?auth=success{state_param}"
                return redirect(final_url)
                
            except AuthlibBaseError as e:
                logger.error(f"Authentication error: {str(e)}")
                
                # On error, return state back to frontend so it can retry with preserved URL
                state_param = f"&state={quote(request_state, safe='')}" if request_state else ""
                redirect_url = f"{config.frontend_url}/?auth=error{state_param}"
                return redirect(redirect_url)
        
        @self.app.route('/api/auth/logout', methods=['POST'])
        def logout():
            """Logout user and clear session"""
            username = session.get('user', {}).get('username', 'Unknown')
            session.clear()
            logger.info(f"User {username} logged out")
            return jsonify({'message': 'Logged out successfully'})
        
        @self.app.route('/api/auth/user')
        def get_current_user():
            """Get current user information"""
            if not self.is_authenticated():
                return jsonify({'error': 'Not authenticated'}), 401
            
            # Check if session has expired (requires re-authentication)
            if self._is_session_expired():
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
            
            # Check if access token needs refresh (but session is still valid)
            if self._should_refresh_token():
                if not self._refresh_access_token():
                    # Don't clear session - token refresh failure doesn't mean session expired
                    return jsonify({'error': 'Token refresh failed'}), 401
            
            return jsonify({
                'user': session.get('user'),
                'authenticated': True
            })
        
        @self.app.route('/api/auth/refresh', methods=['POST'])
        def refresh_token():
            """Refresh access token"""
            if not session.get('refresh_token'):
                return jsonify({'error': 'No refresh token available'}), 401
            
            # Check if session has expired first
            if self._is_session_expired():
                session.clear()
                return jsonify({'error': 'Session expired'}), 401
            
            if self._refresh_access_token():
                return jsonify({'message': 'Token refreshed successfully'})
            else:
                return jsonify({'error': 'Failed to refresh token'}), 401
    
    def is_authenticated(self):
        """Check if user is authenticated and session is valid"""
        has_session = 'user' in session and 'access_token' in session
        if not has_session:
            return False
        
        # Check if session has expired
        if self._is_session_expired():
            return False

        return True
    
    def get_current_user(self):
        """Get current user from session"""
        return session.get('user')
    
    def _is_session_expired(self):
        """Check if the user session has expired (requires re-authentication)"""
        session_expires_at = session.get('user', {}).get('session_expires_at', 0)
        if not session_expires_at:
            return True # No expiration time means session is invalid
        
        current_time = datetime.now().timestamp()
        is_expired = current_time >= session_expires_at
        
        if is_expired:
            logger.info(f"Session expired at {datetime.fromtimestamp(session_expires_at).strftime('%Y-%m-%d %H:%M:%S')}")
        
        return is_expired
    
    def _should_refresh_token(self):
        """Check if access token should be refreshed (expires in next 5 minutes)"""
        token_expires_at = session.get('token_expires_at', 0)
        if not token_expires_at:
            return True # No token expiration means we should try to refresh
        
        current_time = datetime.now().timestamp()
        
        # Refresh if token expires in the next minute
        should_refresh = current_time >= (token_expires_at - 60)  # 1 minute buffer
        return should_refresh
    
    def _refresh_access_token(self):
        """Refresh the access token using refresh token"""
        refresh_token = session.get('refresh_token')
        if not refresh_token:
            logger.error("No refresh token available")
            return False
        
        try:
            # Use the OAuth client to refresh token
            token = self.keycloak_client.fetch_access_token(
                refresh_token=refresh_token
            )
            
            # Update session with new token info
            session['access_token'] = token.get('access_token')
            if token.get('refresh_token'):
                session['refresh_token'] = token.get('refresh_token')
            
            # Update token expiration (but keep session expiration unchanged)
            session['token_expires_at'] = token.get('expires_at', 0)
            session['user']['token_expires_at'] = token.get('expires_at', 0)
            logger.info("Access token refreshed successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return False

def require_auth(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_manager = current_app.extensions.get('auth_manager')
        if not auth_manager or not auth_manager.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check if access token needs refresh (but don't fail if session is still valid)
        if auth_manager._should_refresh_token():
            if not auth_manager._refresh_access_token():
                logger.warning("Token refresh failed, but continuing with existing token")
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Helper function to get current user"""
    auth_manager = current_app.extensions.get('auth_manager')
    if auth_manager and auth_manager.is_authenticated():
        return auth_manager.get_current_user()
    return None