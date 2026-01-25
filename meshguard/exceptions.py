"""
MeshGuard Exceptions
"""

from typing import Optional


class MeshGuardError(Exception):
    """Base exception for MeshGuard errors."""
    pass


class AuthenticationError(MeshGuardError):
    """Raised when authentication fails."""
    pass


class PolicyDeniedError(MeshGuardError):
    """Raised when an action is denied by policy."""
    
    def __init__(
        self,
        action: str,
        policy: Optional[str] = None,
        rule: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        self.action = action
        self.policy = policy
        self.rule = rule
        self.reason = reason or "Access denied by policy"
        
        message = f"Action '{action}' denied"
        if policy:
            message += f" by policy '{policy}'"
        if rule:
            message += f" (rule: {rule})"
        message += f": {self.reason}"
        
        super().__init__(message)


class RateLimitError(MeshGuardError):
    """Raised when rate limit is exceeded."""
    pass
