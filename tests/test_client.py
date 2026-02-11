"""
Tests for MeshGuardClient initialization and core functionality.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import httpx

from meshguard import MeshGuardClient
from meshguard.client import PolicyDecision, Agent


class TestClientInitialization:
    """Test MeshGuardClient initialization."""
    
    def test_init_with_explicit_params(self, gateway_url, agent_token, admin_token):
        """Client initializes with explicit parameters."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
            admin_token=admin_token,
            timeout=60.0,
        )
        
        assert client.gateway_url == gateway_url
        assert client.agent_token == agent_token
        assert client.admin_token == admin_token
        assert client.timeout == 60.0
        client.close()
    
    def test_init_with_env_vars(self):
        """Client initializes from environment variables."""
        with patch.dict(os.environ, {
            "MESHGUARD_GATEWAY_URL": "https://env.meshguard.app",
            "MESHGUARD_AGENT_TOKEN": "env-agent-token",
            "MESHGUARD_ADMIN_TOKEN": "env-admin-token",
        }):
            client = MeshGuardClient()
            
            assert client.gateway_url == "https://env.meshguard.app"
            assert client.agent_token == "env-agent-token"
            assert client.admin_token == "env-admin-token"
            client.close()
    
    def test_init_default_gateway_url(self):
        """Client uses default gateway URL when not specified."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear relevant env vars
            for key in ["MESHGUARD_GATEWAY_URL", "MESHGUARD_AGENT_TOKEN", "MESHGUARD_ADMIN_TOKEN"]:
                os.environ.pop(key, None)
            
            client = MeshGuardClient()
            assert client.gateway_url == "https://dashboard.meshguard.app"
            client.close()
    
    def test_init_strips_trailing_slash(self):
        """Gateway URL has trailing slash stripped."""
        client = MeshGuardClient(gateway_url="https://test.meshguard.app/")
        assert client.gateway_url == "https://test.meshguard.app"
        client.close()
    
    def test_init_generates_trace_id(self):
        """Client generates trace ID if not provided."""
        client = MeshGuardClient()
        assert client.trace_id is not None
        assert len(client.trace_id) > 0
        client.close()
    
    def test_init_uses_provided_trace_id(self):
        """Client uses provided trace ID."""
        client = MeshGuardClient(trace_id="custom-trace-123")
        assert client.trace_id == "custom-trace-123"
        client.close()


class TestHeaders:
    """Test header generation."""
    
    def test_headers_with_auth(self, gateway_url, agent_token):
        """Headers include auth token when available."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        headers = client._headers()
        
        assert headers["Authorization"] == f"Bearer {agent_token}"
        assert "X-MeshGuard-Trace-ID" in headers
        client.close()
    
    def test_headers_without_auth(self, gateway_url):
        """Headers can exclude auth when specified."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token="some-token",
        )
        
        headers = client._headers(include_auth=False)
        
        assert "Authorization" not in headers
        assert "X-MeshGuard-Trace-ID" in headers
        client.close()
    
    def test_headers_no_token(self, gateway_url):
        """Headers without token don't include Authorization."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        headers = client._headers()
        
        assert "Authorization" not in headers
        client.close()
    
    def test_admin_headers(self, gateway_url, admin_token):
        """Admin headers include admin token."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        headers = client._admin_headers()
        
        assert headers["X-Admin-Token"] == admin_token
        assert "X-MeshGuard-Trace-ID" in headers
        client.close()
    
    def test_admin_headers_raises_without_token(self, gateway_url):
        """Admin headers raise error without admin token."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        from meshguard import AuthenticationError
        with pytest.raises(AuthenticationError, match="Admin token required"):
            client._admin_headers()
        
        client.close()


class TestContextManager:
    """Test context manager functionality."""
    
    def test_context_manager_opens_and_closes(self, gateway_url):
        """Context manager properly opens and closes client."""
        with MeshGuardClient(gateway_url=gateway_url) as client:
            assert client._client is not None
    
    def test_close_method(self, gateway_url):
        """Close method closes the HTTP client."""
        client = MeshGuardClient(gateway_url=gateway_url)
        client.close()
        # Should not raise even if called multiple times
        client.close()


class TestHealthCheck:
    """Test health check functionality."""
    
    def test_health_returns_data(self, gateway_url, mock_response):
        """Health check returns gateway health data."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        mock_resp = mock_response(
            status_code=200,
            json_data={"status": "healthy", "version": "1.0.0"},
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            health = client.health()
        
        assert health["status"] == "healthy"
        assert health["version"] == "1.0.0"
        client.close()
    
    def test_is_healthy_true(self, gateway_url, mock_response):
        """is_healthy returns True when gateway is healthy."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        mock_resp = mock_response(
            status_code=200,
            json_data={"status": "healthy"},
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            assert client.is_healthy() is True
        
        client.close()
    
    def test_is_healthy_false_on_unhealthy(self, gateway_url, mock_response):
        """is_healthy returns False when gateway reports unhealthy."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        mock_resp = mock_response(
            status_code=200,
            json_data={"status": "unhealthy"},
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            assert client.is_healthy() is False
        
        client.close()
    
    def test_is_healthy_false_on_error(self, gateway_url):
        """is_healthy returns False on connection error."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        with patch.object(
            client._client, "get",
            side_effect=httpx.ConnectError("Connection failed"),
        ):
            assert client.is_healthy() is False
        
        client.close()


class TestDataclasses:
    """Test dataclass structures."""
    
    def test_policy_decision_fields(self):
        """PolicyDecision has expected fields."""
        decision = PolicyDecision(
            allowed=True,
            action="read:contacts",
            decision="allow",
            policy="default",
            rule="rule-1",
            reason="Allowed by policy",
            trace_id="trace-123",
        )
        
        assert decision.allowed is True
        assert decision.action == "read:contacts"
        assert decision.decision == "allow"
        assert decision.policy == "default"
        assert decision.rule == "rule-1"
        assert decision.reason == "Allowed by policy"
        assert decision.trace_id == "trace-123"
    
    def test_policy_decision_optional_fields(self):
        """PolicyDecision works with minimal fields."""
        decision = PolicyDecision(
            allowed=False,
            action="write:email",
            decision="deny",
        )
        
        assert decision.allowed is False
        assert decision.policy is None
        assert decision.rule is None
        assert decision.reason is None
        assert decision.trace_id is None
    
    def test_agent_fields(self):
        """Agent has expected fields."""
        agent = Agent(
            id="agent-123",
            name="test-agent",
            trust_tier="verified",
            tags=["production", "web"],
            org_id="org-456",
        )
        
        assert agent.id == "agent-123"
        assert agent.name == "test-agent"
        assert agent.trust_tier == "verified"
        assert agent.tags == ["production", "web"]
        assert agent.org_id == "org-456"
    
    def test_agent_default_tags(self):
        """Agent has empty list as default tags."""
        agent = Agent(
            id="agent-123",
            name="test-agent",
            trust_tier="verified",
        )
        
        assert agent.tags == []
        assert agent.org_id is None
