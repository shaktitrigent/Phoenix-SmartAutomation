"""Sensitive Data Protection - Protects sensitive values in generated automation.

This module implements sensitive data protection to ensure automation never
exposes passwords, API keys, tokens, secrets, or private credentials.

Priority 24: Universal Autonomous Test Automation Generation
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SensitiveDataProtection:
    """Sensitive data protection for generated automation.
    
    This protection:
    - Detects sensitive values in automation
    - Never exposes secrets to logs
    - Uses environment variables or secure configuration
    - Prevents hardcoded credentials
    - Masks sensitive data in output
    """
    
    def __init__(self):
        # Sensitive data patterns
        self.sensitive_patterns = {
            "password": [
                r"password\s*=\s*['\"]([^'\"]+)['\"]",
                r"passwd\s*=\s*['\"]([^'\"]+)['\"]",
                r"pwd\s*=\s*['\"]([^'\"]+)['\"]",
            ],
            "api_key": [
                r"api_key\s*=\s*['\"]([^'\"]+)['\"]",
                r"apikey\s*=\s*['\"]([^'\"]+)['\"]",
                r"api-key\s*=\s*['\"]([^'\"]+)['\"]",
            ],
            "secret": [
                r"secret\s*=\s*['\"]([^'\"]+)['\"]",
                r"secret_key\s*=\s*['\"]([^'\"]+)['\"]",
            ],
            "token": [
                r"token\s*=\s*['\"]([^'\"]+)['\"]",
                r"access_token\s*=\s*['\"]([^'\"]+)['\"]",
                r"auth_token\s*=\s*['\"]([^'\"]+)['\"]",
            ],
            "credential": [
                r"credential\s*=\s*['\"]([^'\"]+)['\"]",
                r"credentials\s*=\s*['\"]([^'\"]+)['\"]",
            ],
        }
        
        # Sensitive field names
        self.sensitive_fields = {
            "password", "passwd", "pwd", "secret", "token", "api_key",
            "apikey", "access_token", "auth_token", "credential", "credentials",
            "private_key", "private_key", "session_id", "session_key",
        }
        
        logger.info("SensitiveDataProtection initialized")
    
    def detect_sensitive_data(self, code: str) -> List[Dict[str, Any]]:
        """Detect sensitive data in code.
        
        Args:
            code: Code to analyze
            
        Returns:
            List of detected sensitive data instances
        """
        detections = []
        
        for data_type, patterns in self.sensitive_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    detections.append({
                        "type": data_type,
                        "line": line_num,
                        "match": match.group(),
                        "value": match.group(1) if len(match.groups()) > 0 else "",
                        "start": match.start(),
                        "end": match.end(),
                    })
        
        return detections
    
    def mask_sensitive_data(self, code: str) -> str:
        """Mask sensitive data in code.
        
        Args:
            code: Code to mask
            
        Returns:
            Code with sensitive data masked
        """
        masked_code = code
        
        for data_type, patterns in self.sensitive_patterns.items():
            for pattern in patterns:
                # Replace with environment variable reference
                masked_code = re.sub(
                    pattern,
                    f'os.environ.get("{data_type.upper()}_ENV", "")',
                    masked_code,
                    flags=re.IGNORECASE,
                )
        
        return masked_code
    
    def protect_automation_code(self, code: str) -> str:
        """Protect automation code by replacing sensitive data with env vars.
        
        Args:
            code: Original automation code
            
        Returns:
            Protected code with environment variable references
        """
        # Add os import if not present
        if "import os" not in code:
            code = "import os\n" + code
        
        # Mask sensitive data
        protected_code = self.mask_sensitive_data(code)
        
        # Add comment about environment variables
        if protected_code != code:
            env_comment = (
                "# Sensitive data protection: "
                "Set environment variables for sensitive values\n"
            )
            protected_code = env_comment + protected_code
        
        return protected_code
    
    def check_for_hardcoded_secrets(self, code: str) -> List[str]:
        """Check for hardcoded secrets and return warnings.
        
        Args:
            code: Code to check
            
        Returns:
            List of warning messages
        """
        warnings = []
        detections = self.detect_sensitive_data(code)
        
        for detection in detections:
            warning = (
                f"Hardcoded {detection['type']} found at line {detection['line']}: "
                f"'{detection['match']}'"
            )
            warnings.append(warning)
        
        return warnings
    
    def is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name is sensitive.
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field is sensitive
        """
        return field_name.lower() in self.sensitive_fields
    
    def get_safe_value(self, field_name: str, value: Any) -> str:
        """Get a safe representation of a value for logging.
        
        Args:
            field_name: Name of the field
            value: Value to sanitize
            
        Returns:
            Safe string representation
        """
        if self.is_sensitive_field(field_name):
            return "***REDACTED***"
        
        value_str = str(value)
        
        # Check if value looks like a secret
        if len(value_str) > 20 and any(c.isalnum() for c in value_str):
            # Might be a token or key
            return "***REDACTED***"
        
        return value_str
    
    def sanitize_log_message(self, message: str) -> str:
        """Sanitize a log message to remove sensitive data.
        
        Args:
            message: Log message to sanitize
            
        Returns:
            Sanitized message
        """
        sanitized = message
        
        # Mask common patterns
        for data_type, patterns in self.sensitive_patterns.items():
            for pattern in patterns:
                sanitized = re.sub(
                    pattern,
                    f"{data_type}=***REDACTED***",
                    sanitized,
                    flags=re.IGNORECASE,
                )
        
        return sanitized
    
    def validate_environment_variables(
        self,
        required_vars: List[str],
    ) -> Dict[str, bool]:
        """Validate that required environment variables are set.
        
        Args:
            required_vars: List of required environment variable names
            
        Returns:
            Dictionary mapping var names to availability status
        """
        status = {}
        for var in required_vars:
            status[var] = os.environ.get(var) is not None
        
        missing = [var for var, available in status.items() if not available]
        if missing:
            logger.warning(f"Missing environment variables: {', '.join(missing)}")
        
        return status
    
    def generate_env_var_template(
        self,
        sensitive_fields: List[str],
    ) -> str:
        """Generate an environment variable template file.
        
        Args:
            sensitive_fields: List of sensitive field names
            
        Returns:
            Template file content
        """
        lines = ["# Phoenix Automation - Sensitive Data Environment Variables", ""]
        
        for field in sensitive_fields:
            env_var_name = field.upper()
            lines.append(f"{env_var_name}=")
        
        return "\n".join(lines)
