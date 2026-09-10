"""Session Recovery - Automatic session restoration.

Detects session loss, performs automatic re-login, and restores
cookies, local storage, and browser storage to continue execution.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Represents a saved session state."""
    url: str
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class RecoveryMetrics:
    """Session recovery metrics."""
    total_recovery_attempts: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    total_recovery_time_ms: float = 0.0
    session_saved_count: int = 0
    session_restored_count: int = 0


class SessionRecovery:
    """Automatic session recovery for Phoenix automation.
    
    Features:
    - Session state capture (cookies, storage)
    - Automatic logout detection
    - Re-login with saved credentials
    - Storage restoration
    - Session persistence
    - Metrics tracking
    """
    
    def __init__(
        self,
        enable_auto_recovery: bool = True,
        check_logout_indicators: bool = True,
        save_session_state: bool = True,
    ):
        self.enable_auto_recovery = enable_auto_recovery
        self.check_logout_indicators = check_logout_indicators
        self.save_session_state = save_session_state
        
        self.saved_sessions: Dict[str, SessionState] = {}
        self.metrics = RecoveryMetrics()
        
        # Logout detection patterns
        self.logout_indicators = [
            "login",
            "sign in",
            "authentication",
            "unauthorized",
            "401",
            "403",
            "session expired",
        ]
        
        logger.info(
            "Session Recovery initialized: auto_recovery=%s, check_logout=%s, save_state=%s",
            enable_auto_recovery, check_logout_indicators, save_session_state
        )
    
    def save_session(
        self,
        page: Any,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> SessionState:
        """Save current session state.
        
        Args:
            page: Playwright Page object
            url: Current URL
            username: Optional username for re-login
            password: Optional password for re-login
            
        Returns:
            Saved session state
        """
        try:
            # Capture cookies
            cookies = page.context.cookies()
            
            # Capture local storage
            local_storage = {}
            try:
                local_storage = page.evaluate("""
                    () => {
                        const storage = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            storage[key] = localStorage.getItem(key);
                        }
                        return storage;
                    }
                """)
            except Exception as e:
                logger.warning("Failed to capture local storage: %s", str(e))
            
            # Capture session storage
            session_storage = {}
            try:
                session_storage = page.evaluate("""
                    () => {
                        const storage = {};
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const key = sessionStorage.key(i);
                            storage[key] = sessionStorage.getItem(key);
                        }
                        return storage;
                    }
                """)
            except Exception as e:
                logger.warning("Failed to capture session storage: %s", str(e))
            
            # Create session state
            session_state = SessionState(
                url=url,
                cookies=cookies,
                local_storage=local_storage,
                session_storage=session_storage,
                timestamp=time.time(),
                username=username,
                password=password,
            )
            
            # Save session
            session_key = self._generate_session_key(url, username)
            self.saved_sessions[session_key] = session_state
            self.metrics.session_saved_count += 1
            
            logger.info(
                "Session Recovery: Saved session for %s (cookies: %d, local_storage: %d, session_storage: %d)",
                url, len(cookies), len(local_storage), len(session_storage)
            )
            
            return session_state
            
        except Exception as e:
            logger.error("Session Recovery: Failed to save session: %s", str(e))
            raise
    
    def restore_session(self, page: Any, url: str, username: Optional[str] = None) -> bool:
        """Restore a saved session.
        
        Args:
            page: Playwright Page object
            url: Target URL
            username: Optional username for session lookup
            
        Returns:
            True if session restored successfully, False otherwise
        """
        recovery_start = time.time()
        self.metrics.total_recovery_attempts += 1
        
        try:
            session_key = self._generate_session_key(url, username)
            session_state = self.saved_sessions.get(session_key)
            
            if not session_state:
                logger.warning("Session Recovery: No saved session found for %s", session_key)
                self.metrics.failed_recoveries += 1
                return False
            
            # Restore cookies
            if session_state.cookies:
                page.context.add_cookies(session_state.cookies)
                logger.info("Session Recovery: Restored %d cookies", len(session_state.cookies))
            
            # Restore local storage
            if session_state.local_storage:
                try:
                    page.evaluate(f"""
                        () => {{
                            const storage = {session_state.local_storage};
                            for (const [key, value] of Object.entries(storage)) {{
                                localStorage.setItem(key, value);
                            }}
                        }}
                    """)
                    logger.info("Session Recovery: Restored %d local storage items", len(session_state.local_storage))
                except Exception as e:
                    logger.warning("Failed to restore local storage: %s", str(e))
            
            # Restore session storage
            if session_state.session_storage:
                try:
                    page.evaluate(f"""
                        () => {{
                            const storage = {session_state.session_storage};
                            for (const [key, value] of Object.entries(storage)) {{
                                sessionStorage.setItem(key, value);
                            }}
                        }}
                    """)
                    logger.info("Session Recovery: Restored %d session storage items", len(session_state.session_storage))
                except Exception as e:
                    logger.warning("Failed to restore session storage: %s", str(e))
            
            # Navigate to target URL
            page.goto(url)
            
            self.metrics.successful_recoveries += 1
            self.metrics.session_restored_count += 1
            self.metrics.total_recovery_time_ms += (time.time() - recovery_start) * 1000
            
            logger.info(
                "Session Recovery: Session restored successfully for %s (%.0fms)",
                url, (time.time() - recovery_start) * 1000
            )
            
            return True
            
        except Exception as e:
            logger.error("Session Recovery: Failed to restore session: %s", str(e))
            self.metrics.failed_recoveries += 1
            return False
    
    def detect_logout(self, page: Any) -> bool:
        """Detect if user has been logged out.
        
        Args:
            page: Playwright Page object
            
        Returns:
            True if logout detected, False otherwise
        """
        if not self.check_logout_indicators:
            return False
        
        try:
            # Check URL for logout indicators
            current_url = page.url.lower()
            for indicator in self.logout_indicators:
                if indicator in current_url:
                    logger.info("Session Recovery: Logout detected via URL (%s)", current_url)
                    return True
            
            # Check page content for logout indicators
            page_content = page.content().lower()
            for indicator in self.logout_indicators:
                if indicator in page_content:
                    logger.info("Session Recovery: Logout detected via page content")
                    return True
            
            # Check for login form presence
            login_forms = page.locator("form").count()
            if login_forms > 0:
                for i in range(login_forms):
                    form = page.locator("form").nth(i)
                    form_text = form.inner_text().lower()
                    if any(indicator in form_text for indicator in self.logout_indicators):
                        logger.info("Session Recovery: Logout detected via login form")
                        return True
            
            return False
            
        except Exception as e:
            logger.warning("Session Recovery: Logout detection failed: %s", str(e))
            return False
    
    def auto_recover_session(
        self,
        page: Any,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """Automatically detect and recover from session loss.
        
        Args:
            page: Playwright Page object
            url: Target URL
            username: Username for re-login
            password: Password for re-login
            
        Returns:
            True if recovery successful, False otherwise
        """
        if not self.enable_auto_recovery:
            return False
        
        # Check if logout occurred
        if not self.detect_logout(page):
            return True  # No logout needed
        
        logger.info("Session Recovery: Starting automatic session recovery")
        
        # Try to restore saved session first
        if self.restore_session(page, url, username):
            return True
        
        # If no saved session, try re-login
        if username and password:
            return self._perform_login(page, url, username, password)
        
        logger.error("Session Recovery: No credentials available for re-login")
        return False
    
    def _perform_login(self, page: Any, url: str, username: str, password: str) -> bool:
        """Perform login with provided credentials.
        
        Args:
            page: Playwright Page object
            url: Login URL
            username: Username
            password: Password
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            page.goto(url)
            
            # Fill username
            username_field = page.locator("input[name='username'], input[type='text'], input[name='user']").first
            username_field.fill(username)
            
            # Fill password
            password_field = page.locator("input[name='password'], input[type='password']").first
            password_field.fill(password)
            
            # Click login button
            login_button = page.get_by_role("button", name=re.compile(r"login|sign in|submit", re.IGNORECASE)).first
            login_button.click()
            
            # Wait for navigation
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Save the new session
            self.save_session(page, page.url(), username, password)
            
            logger.info("Session Recovery: Login successful for %s", username)
            return True
            
        except Exception as e:
            logger.error("Session Recovery: Login failed: %s", str(e))
            return False
    
    def _generate_session_key(self, url: str, username: Optional[str] = None) -> str:
        """Generate a unique key for session storage."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if username:
            return f"{base_url}:{username}"
        return base_url
    
    def get_metrics(self) -> RecoveryMetrics:
        """Get session recovery metrics."""
        return self.metrics
    
    def clear_sessions(self) -> None:
        """Clear all saved sessions."""
        self.saved_sessions.clear()
        logger.info("Session Recovery: All saved sessions cleared")