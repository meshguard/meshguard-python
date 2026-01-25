"""
MeshGuard Client

Core client for interacting with MeshGuard gateway.
"""

import os
import uuid
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .exceptions import (
    MeshGuardError,
    AuthenticationError,
    PolicyDeniedError,
    RateLimitError,
)


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""
    allowed: bool
    action: str
    decision: str
    policy: Optional[str] = None
    rule: Optional[str] = None
    reason: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class Agent:
    """MeshGuard agent identity."""
    id: str
    name: str
    trust_tier: str
    tags: List[str] = field(default_factory=list)
    org_id: Optional[str] = None


class MeshGuardClient:
    """
    Client for MeshGuard gateway.
    
    Usage:
        client = MeshGuardClient(
            gateway_url="https://dashboard.meshguard.app",
            agent_token="your-agent-token"
        )
        
        # Check if an action is allowed
        decision = client.check("read:contacts")
        if decision.allowed:
            # Proceed with action
            pass
        
        # Or use the context manager for automatic tracing
        with client.govern("read:contacts") as ctx:
            # Your code here - raises PolicyDeniedError if not allowed
            pass
    """
    
    def __init__(
        self,
        gateway_url: Optional[str] = None,
        agent_token: Optional[str] = None,
        admin_token: Optional[str] = None,
        timeout: float = 30.0,
        trace_id: Optional[str] = None,
    ):
        """
        Initialize MeshGuard client.
        
        Args:
            gateway_url: MeshGuard gateway URL (or MESHGUARD_GATEWAY_URL env var)
            agent_token: Agent JWT token (or MESHGUARD_AGENT_TOKEN env var)
            admin_token: Admin token for management APIs (or MESHGUARD_ADMIN_TOKEN env var)
            timeout: Request timeout in seconds
            trace_id: Optional trace ID for request correlation
        """
        self.gateway_url = (
            gateway_url 
            or os.environ.get("MESHGUARD_GATEWAY_URL") 
            or "http://localhost:3100"
        ).rstrip("/")
        
        self.agent_token = agent_token or os.environ.get("MESHGUARD_AGENT_TOKEN")
        self.admin_token = admin_token or os.environ.get("MESHGUARD_ADMIN_TOKEN")
        self.timeout = timeout
        self.trace_id = trace_id or str(uuid.uuid4())
        
        self._client = httpx.Client(timeout=timeout)
    
    def _headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "X-MeshGuard-Trace-ID": self.trace_id,
        }
        if include_auth and self.agent_token:
            headers["Authorization"] = f"Bearer {self.agent_token}"
        return headers
    
    def _admin_headers(self) -> Dict[str, str]:
        """Build admin request headers."""
        if not self.admin_token:
            raise AuthenticationError("Admin token required for this operation")
        return {
            "X-Admin-Token": self.admin_token,
            "X-MeshGuard-Trace-ID": self.trace_id,
        }
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired token")
        elif response.status_code == 403:
            data = response.json() if response.content else {}
            raise PolicyDeniedError(
                action=data.get("action", "unknown"),
                policy=data.get("policy"),
                rule=data.get("rule"),
                reason=data.get("message", "Access denied by policy"),
            )
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif response.status_code >= 400:
            raise MeshGuardError(f"Request failed: {response.status_code} {response.text}")
        
        return response.json() if response.content else {}
    
    # === Core Governance ===
    
    def check(self, action: str, resource: Optional[str] = None) -> PolicyDecision:
        """
        Check if an action is allowed by policy.
        
        Args:
            action: Action to check (e.g., "read:contacts", "write:email")
            resource: Optional resource identifier
            
        Returns:
            PolicyDecision with allowed status and details
        """
        headers = self._headers()
        headers["X-MeshGuard-Action"] = action
        if resource:
            headers["X-MeshGuard-Resource"] = resource
        
        try:
            response = self._client.get(
                f"{self.gateway_url}/proxy/check",
                headers=headers,
            )
            
            if response.status_code == 403:
                data = response.json() if response.content else {}
                return PolicyDecision(
                    allowed=False,
                    action=action,
                    decision="deny",
                    policy=data.get("policy"),
                    rule=data.get("rule"),
                    reason=data.get("message"),
                    trace_id=self.trace_id,
                )
            
            data = self._handle_response(response)
            return PolicyDecision(
                allowed=True,
                action=action,
                decision="allow",
                policy=data.get("policy"),
                trace_id=self.trace_id,
            )
            
        except PolicyDeniedError as e:
            return PolicyDecision(
                allowed=False,
                action=action,
                decision="deny",
                policy=e.policy,
                rule=e.rule,
                reason=e.reason,
                trace_id=self.trace_id,
            )
    
    def enforce(self, action: str, resource: Optional[str] = None) -> PolicyDecision:
        """
        Enforce policy - raises PolicyDeniedError if not allowed.
        
        Args:
            action: Action to check
            resource: Optional resource identifier
            
        Returns:
            PolicyDecision if allowed
            
        Raises:
            PolicyDeniedError: If action is denied
        """
        decision = self.check(action, resource)
        if not decision.allowed:
            raise PolicyDeniedError(
                action=action,
                policy=decision.policy,
                rule=decision.rule,
                reason=decision.reason,
            )
        return decision
    
    def govern(self, action: str, resource: Optional[str] = None):
        """
        Context manager for governed code blocks.
        
        Usage:
            with client.govern("read:contacts"):
                # This code only runs if allowed
                contacts = fetch_contacts()
        """
        return GovernedContext(self, action, resource)
    
    # === Proxy Requests ===
    
    def request(
        self,
        method: str,
        path: str,
        action: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Make a governed request through the MeshGuard proxy.
        
        Args:
            method: HTTP method
            path: Path to proxy (appended to /proxy/)
            action: MeshGuard action for policy evaluation
            **kwargs: Additional arguments passed to httpx
            
        Returns:
            httpx.Response
        """
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())
        headers["X-MeshGuard-Action"] = action
        
        response = self._client.request(
            method,
            f"{self.gateway_url}/proxy/{path.lstrip('/')}",
            headers=headers,
            **kwargs,
        )
        
        self._handle_response(response)
        return response
    
    def get(self, path: str, action: str, **kwargs) -> httpx.Response:
        """GET request through proxy."""
        return self.request("GET", path, action, **kwargs)
    
    def post(self, path: str, action: str, **kwargs) -> httpx.Response:
        """POST request through proxy."""
        return self.request("POST", path, action, **kwargs)
    
    def put(self, path: str, action: str, **kwargs) -> httpx.Response:
        """PUT request through proxy."""
        return self.request("PUT", path, action, **kwargs)
    
    def delete(self, path: str, action: str, **kwargs) -> httpx.Response:
        """DELETE request through proxy."""
        return self.request("DELETE", path, action, **kwargs)
    
    # === Health & Info ===
    
    def health(self) -> Dict[str, Any]:
        """Check gateway health."""
        response = self._client.get(f"{self.gateway_url}/health")
        return response.json()
    
    def is_healthy(self) -> bool:
        """Quick health check."""
        try:
            health = self.health()
            return health.get("status") == "healthy"
        except Exception:
            return False
    
    # === Admin Operations ===
    
    def list_agents(self) -> List[Agent]:
        """List all agents (requires admin token)."""
        response = self._client.get(
            f"{self.gateway_url}/admin/agents",
            headers=self._admin_headers(),
        )
        data = self._handle_response(response)
        return [
            Agent(
                id=a["id"],
                name=a["name"],
                trust_tier=a["trustTier"],
                tags=a.get("tags", []),
                org_id=a.get("orgId"),
            )
            for a in data.get("agents", [])
        ]
    
    def create_agent(
        self,
        name: str,
        trust_tier: str = "verified",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new agent (requires admin token)."""
        response = self._client.post(
            f"{self.gateway_url}/admin/agents",
            headers=self._admin_headers(),
            json={
                "name": name,
                "trustTier": trust_tier,
                "tags": tags or [],
            },
        )
        return self._handle_response(response)
    
    def revoke_agent(self, agent_id: str) -> None:
        """Revoke an agent (requires admin token)."""
        response = self._client.delete(
            f"{self.gateway_url}/admin/agents/{agent_id}",
            headers=self._admin_headers(),
        )
        self._handle_response(response)
    
    def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies (requires admin token)."""
        response = self._client.get(
            f"{self.gateway_url}/admin/policies",
            headers=self._admin_headers(),
        )
        data = self._handle_response(response)
        return data.get("policies", [])
    
    def get_audit_log(
        self,
        limit: int = 50,
        decision: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries (requires admin token)."""
        params = {"limit": limit}
        if decision:
            params["decision"] = decision
            
        response = self._client.get(
            f"{self.gateway_url}/admin/audit",
            headers=self._admin_headers(),
            params=params,
        )
        data = self._handle_response(response)
        return data.get("entries", [])
    
    # === Cleanup ===
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class GovernedContext:
    """Context manager for governed code blocks."""
    
    def __init__(
        self,
        client: MeshGuardClient,
        action: str,
        resource: Optional[str] = None,
    ):
        self.client = client
        self.action = action
        self.resource = resource
        self.decision: Optional[PolicyDecision] = None
    
    def __enter__(self) -> PolicyDecision:
        self.decision = self.client.enforce(self.action, self.resource)
        return self.decision
    
    def __exit__(self, *args):
        pass
