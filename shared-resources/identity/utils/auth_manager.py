"""
Authentication Manager for Keycloak SSO Integration
Handles user authentication, session management, and token validation
"""
from datetime import datetime, timedelta
from functools import wraps
from typing import Any
import os, uuid, logging
import requests as http_requests
from flask import request, jsonify, session, redirect, url_for, current_app
from authlib.integrations.flask_client import OAuth
from authlib.common.errors import AuthlibBaseError
from config.app_config import AppConfig
from urllib.parse import quote
from global_utils.redis.constants import identity_session_key

config = AppConfig.get_instance()

logger = logging.getLogger('auth_manager')



class AuthManager:
    def __init__(self, app=None, redis_store=None):
        self.app = app
        self.oauth = None
        self.keycloak_client = None
        self.redis_store = redis_store
        self.backend_env = config.get('backend_env', 'development')
        if app is not None:
            self.init_app(app, redis_store)
    
    def init_app(self, app, redis_store):
        """Initialize the auth manager with Flask app"""
        self.app = app
        
        # Set up secret key for sessions (required for secure session management)
        # The secret_key should be configured in app_config for both dev and production
        if not app.secret_key:
            app.secret_key = config.get('secret_key', os.urandom(24))
        
        # Configure OAuth
        self.oauth = OAuth(app)
        
        # Register Keycloak client
        self._setup_keycloak()
        
        # Set up Redis
        self._setup_redis(redis_store)
        
        # Register auth routes
        self._register_auth_routes()
        
        # Set up session configuration
        self._setup_session_configuration(app)

    def _setup_keycloak(self):
        if config.local_auth_enabled:
            from utils.dev_oauth_client import DevOAuthClient
            self.keycloak_client = DevOAuthClient()
            logger.info("Local auth mode -- using DevOAuthClient (Keycloak bypassed)")
            return

        keycloak_base_url = config.keycloak_base_url
        client_id = config.client_id
        client_secret = config.client_secret
        realm = config.get('keycloak_realm', 'master')
        if not all([keycloak_base_url, client_id, client_secret]):
            raise ValueError("Missing required Keycloak configuration")
        try:
            self.keycloak_client = self.oauth.register(
                name='keycloak',
                client_id=client_id,
                client_secret=client_secret,
                server_metadata_url=f"{keycloak_base_url}/realms/{realm}/.well-known/openid-configuration",
                client_kwargs={
                    'scope': 'openid email profile',
                }
            )
        except Exception as e:
            logger.error(f"Failed to setup Keycloak client: {e}")
            raise e
        else:
            logger.info("Keycloak client setup successfully")

    def _setup_redis(self, redis_store):
        self.redis_store = redis_store
        if not self.redis_store.ping():
            raise ValueError("Failed to connect to Redis")
        else:
            logger.info("Connected to Redis")

    def _setup_session_configuration(self, app):
        app.config.update({
            'SESSION_COOKIE_SECURE': config.session_cookie_secure,
            'SESSION_COOKIE_HTTPONLY': config.session_cookie_http_only,
            'SESSION_COOKIE_SAMESITE': config.session_cookie_samesite,
            'PERMANENT_SESSION_LIFETIME': timedelta(hours=config.permanent_session_lifetime)
        })

    def _get_server_session(self):
        """Server-side session dict for current cookie session_id, or None."""
        sid = session.get('session_id')
        if not sid:
            return None
        return self.redis_store.hget(identity_session_key(sid))

    def _ttl_seconds_until_session_expires(self, session_expires_at) -> int:
        """
        Redis EXPIRE seconds until session_expires_at (unix seconds).
        Aligns key TTL with absolute app session end (not access-token lifetime).
        """
        if session_expires_at is None:
            return 0
        remaining = float(session_expires_at) - datetime.now().timestamp()
        return max(0, int(remaining))
    
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

                # Calculate session expiration (configurable via the config for permanent session lifetime)
                session_created_at = datetime.now()
                session_expires_at = session_created_at + timedelta(hours=config.permanent_session_lifetime)
                
                # Store session_id in session cookie and user info in redis
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
                session.permanent = True

                session_data = {
                    'username': userinfo.get('preferred_username'),
                    'email': userinfo.get('email'),
                    'name': userinfo.get('name'),
                    'sub': userinfo.get('sub'),
                    'session_created_at': session_created_at.timestamp(),
                    'session_expires_at': session_expires_at.timestamp(),
                    'token_expires_at': token.get('expires_at', 0),
                    'access_token': token.get('access_token'),
                    'refresh_token': token.get('refresh_token')
                }

                ttl_seconds = self._ttl_seconds_until_session_expires(
                    session_expires_at.timestamp()
                )
                self.redis_store.hset(identity_session_key(session_id), session_data, ttl_seconds=ttl_seconds)

                logger.info(
                    "User %s authenticated successfully",
                    userinfo.get('preferred_username'),
                )
                svc = current_app.extensions.get('team_service')
                if svc:
                    svc.cache_user_groups(
                        userinfo.get('preferred_username'),
                        token.get('access_token'),
                    )
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
            """Logout user and clear session (revokes refresh token at Keycloak when available)."""
            session_data = self._get_server_session()
            username = (session_data or {}).get('username', 'Unknown')  
            if session.get('session_id'):      
                self.redis_store.delete(identity_session_key(session.get('session_id')))
            refresh_token_val = (session_data or {}).get('refresh_token') if session_data else None
            if refresh_token_val and not config.local_auth_enabled:
                try:
                    keycloak_base_url = config.keycloak_base_url
                    realm = config.get('keycloak_realm', 'master')
                    logout_url = f"{keycloak_base_url}/realms/{realm}/protocol/openid-connect/logout"
                    resp = http_requests.post(
                        logout_url,
                        data={
                            'client_id': config.client_id,
                            'client_secret': config.client_secret,
                            'refresh_token': refresh_token_val,
                        },
                        timeout=10,
                    )
                    if resp.ok:
                        logger.info(f"Keycloak session revoked for user {username}")
                    else:
                        body_preview = (resp.text or '')[:500]
                        logger.warning(
                            f"Keycloak logout returned {resp.status_code} for {username}; "
                            f"local session cleared but server may still accept the refresh token. "
                            f"Body: {body_preview}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to revoke Keycloak session for {username}: {e}")
          
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
                if session.get('session_id'):
                    self.redis_store.delete(identity_session_key(session.get('session_id')))
                    session.clear()
                    return jsonify({'error': 'Session expired'}), 401
            
            # Check if access token needs refresh (but session is still valid)
            if self._should_refresh_token():
                if not self._refresh_access_token():
                    # Don't clear session - token refresh failure doesn't mean session expired
                    return jsonify({'error': 'Token refresh failed'}), 401
            
            # Get user and add permissions

            user = self.get_user_info()
            if not user:
                return jsonify({'error': 'No user information available'}), 401
            
            # Add admin permission based on config (checks admin_allowed_users)
            user['is_admin'] = self._check_admin_permission(user)

            session_data = self._get_server_session() or {}
            return jsonify({
                'user': user,
                'authenticated': True,
                'access_token': session_data.get('access_token'),
            })
        
        @self.app.route('/api/auth/user/groups')
        def get_user_groups():
            """Return the logged-in user's ROVER/directory groups (cached in Redis).

            Query ``fresh=1`` (or ``true``) skips the Redis cache and re-fetches
            from the directory so UI reloads reflect Rover membership changes.

            On every call, also syncs ``group_members`` on teams in
            MongoDB so the effective member count stays accurate.
            """
            if not self.is_authenticated():
                return jsonify({'error': 'Not authenticated'}), 401

            session_data = self._get_server_session() or {}
            username = session_data.get('username')
            if not username:
                return jsonify({'groups': []}), 200

            fresh = request.args.get('fresh', '').lower() in ('1', 'true', 'yes')
            groups = None
            cache = current_app.extensions.get('user_groups_cache')
            if cache and not fresh:
                groups = cache.get_groups(username)

            if groups is None:
                access_token = session_data.get('access_token')
                svc = current_app.extensions.get('team_service')
                if svc:
                    groups = svc.fetch_user_groups_as_dicts(username, access_token)
                    if cache:
                        cache.set_groups(username, groups)

            if groups:
                try:
                    svc = current_app.extensions.get('team_service')
                    if svc:
                        svc.refresh_group_members(groups)
                except Exception:
                    logger.debug("group-member refresh skipped", exc_info=True)

            return jsonify({'groups': [g['group_id'] for g in (groups or [])]
                            }), 200

        @self.app.route('/api/auth/refresh', methods=['POST'])
        def refresh_token():
            """Refresh access token"""
            session_data = self._get_server_session()
            if not session_data or not session_data.get('refresh_token'):
                return jsonify({'error': 'No refresh token available'}), 401
            
            # Check if session has expired first
            if self._is_session_expired():
                if session.get('session_id'):
                    self.redis_store.delete(identity_session_key(session.get('session_id')))
                    session.clear()
                    return jsonify({'error': 'Session expired'}), 401
            
            if self._refresh_access_token():
                return jsonify({'message': 'Token refreshed successfully'})
            else:
                return jsonify({'error': 'Failed to refresh token'}), 401

        @self.app.route('/api/auth/config')
        def auth_config():
            """Return auth configuration for the login page."""
            return jsonify({'local_auth': config.local_auth_enabled})

    def is_authenticated(self):
        """Check if user is authenticated and session is valid"""
        session_data = self._get_server_session()
        if not session_data or 'username' not in session_data or 'access_token' not in session_data:
            return False
        
        # Check if session has expired
        if self._is_session_expired():
            return False

        return True
    
    def get_user_info(self):
        """Get current user from session"""
        user = {}
        session_data = self._get_server_session()
        if not session_data:
            return None
        user['username'] = session_data.get('username')
        user['email'] = session_data.get('email')
        user['name'] = session_data.get('name')
        user['sub'] = session_data.get('sub')
        user['session_created_at'] = session_data.get('session_created_at')
        user['session_expires_at'] = session_data.get('session_expires_at')
        user['token_expires_at'] = session_data.get('token_expires_at')
        return user
    
    def _is_session_expired(self):
        """Check if the user session has expired (requires re-authentication)"""
        session_data = self._get_server_session()
        session_expires_at = (session_data or {}).get('session_expires_at', 0)
        if not session_expires_at:
            return True # No expiration time means session is invalid
        
        current_time = datetime.now().timestamp()
        is_expired = current_time >= float(session_expires_at)
        
        if is_expired:
            logger.info(f"Session expired at {datetime.fromtimestamp(float(session_expires_at)).strftime('%Y-%m-%d %H:%M:%S')}")
        
        return is_expired
    
    def _should_refresh_token(self):
        """Check if access token should be refreshed (expires in next 1 minute)"""
        session_data = self._get_server_session()
        token_expires_at = (session_data or {}).get('token_expires_at', 0)
        if not token_expires_at:
            return True # No token expiration means we should try to refresh
        
        current_time = datetime.now().timestamp()
        
        # Refresh if token expires in the next minute
        should_refresh = current_time >= (float(token_expires_at) - 60)  # 1 minute buffer
        return should_refresh
    
    def _refresh_access_token(self):
        """Refresh the access token using refresh token"""

        session_data = self._get_server_session()
        refresh_token = (session_data or {}).get('refresh_token')
        if not refresh_token:
            logger.error("No refresh token available")
            return False
        
        try:
            # Use the OAuth client to refresh token
            token = self.keycloak_client.fetch_access_token(
                refresh_token=refresh_token
            )
            
            # Update session with new token info
            session_data['access_token'] = token.get('access_token')
            if token.get('refresh_token'):
                session_data['refresh_token'] = token.get('refresh_token')
            
            # Update token expiration (but keep session expiration unchanged)
            session_data['token_expires_at'] = token.get('expires_at', 0)
            ttl_seconds = self._ttl_seconds_until_session_expires(
                session_data.get('session_expires_at')
            )
            self.redis_store.hset(
                identity_session_key(session.get('session_id')), session_data, ttl_seconds=ttl_seconds
            )
            logger.info("Access token refreshed successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            return False

    
    def _check_admin_permission(self, user: dict) -> bool:
        """
        Check if user has admin permission (can access analytics and other admin features)
        Based on admin_allowed_users configuration in app_config.py
        
        Checks user by username or user_id (sub) only.
        """
        if not user:
            return False
        
        # Get allowed users from config
        allowed_users = config.get('admin_allowed_users', [])
        
        if not allowed_users:
            return False
        
        # Get username or user_id (sub)
        username = user.get('username') or user.get('sub')
        
        # Check if username/user_id is in allowed list
        if username and username in allowed_users:
            return True
        
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
        return auth_manager.get_user_info()
    return None