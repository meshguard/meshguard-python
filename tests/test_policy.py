"""
Tests for policy evaluation functionality (check, enforce, govern).
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from meshguard import MeshGuardClient, PolicyDeniedError
from meshguard.client import PolicyDecision, GovernedContext


class TestPolicyCheck:
    """Test policy check functionality."""
    
    def test_check_allowed(self, gateway_url, agent_token, mock_response):
        """Check returns allowed=True when policy permits."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=200,
            json_data={"policy": "default"},
        )
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            decision = client.check("read:contacts")
        
        assert decision.allowed is True
        assert decision.action == "read:contacts"
        assert decision.decision == "allow"
        assert decision.policy == "default"
        
        # Verify correct headers were sent
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert headers["X-MeshGuard-Action"] == "read:contacts"
        
        client.close()
    
    def test_check_denied(self, gateway_url, agent_token, mock_response):
        """Check returns allowed=False when policy denies."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={
                "policy": "strict",
                "rule": "no-delete",
                "message": "Delete operations not allowed",
            },
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            decision = client.check("delete:database")
        
        assert decision.allowed is False
        assert decision.action == "delete:database"
        assert decision.decision == "deny"
        assert decision.policy == "strict"
        assert decision.rule == "no-delete"
        assert decision.reason == "Delete operations not allowed"
        
        client.close()
    
    def test_check_with_resource(self, gateway_url, agent_token, mock_response):
        """Check includes resource in headers."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            client.check("read:contacts", resource="contacts/123")
        
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["X-MeshGuard-Resource"] == "contacts/123"
        
        client.close()
    
    def test_check_includes_trace_id(self, gateway_url, agent_token, mock_response):
        """Check includes trace ID in response."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
            trace_id="test-trace-id",
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "get", return_value=mock_resp):
            decision = client.check("read:contacts")
        
        assert decision.trace_id == "test-trace-id"
        
        client.close()
    
    def test_check_handles_empty_response(self, gateway_url, agent_token, mock_response):
        """Check handles empty response body."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_resp.json.return_value = {}
        
        with patch.object(client._client, "get", return_value=mock_resp):
            decision = client.check("read:contacts")
        
        assert decision.allowed is True
        
        client.close()


class TestPolicyEnforce:
    """Test policy enforcement functionality."""
    
    def test_enforce_returns_decision_when_allowed(self, gateway_url, agent_token, mock_response):
        """Enforce returns PolicyDecision when allowed."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"policy": "default"})
        
        with patch.object(client._client, "get", return_value=mock_resp):
            decision = client.enforce("read:contacts")
        
        assert decision.allowed is True
        assert isinstance(decision, PolicyDecision)
        
        client.close()
    
    def test_enforce_raises_when_denied(self, gateway_url, agent_token, mock_response):
        """Enforce raises PolicyDeniedError when denied."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={
                "policy": "strict",
                "rule": "no-delete",
                "message": "Not allowed",
            },
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            with pytest.raises(PolicyDeniedError) as exc_info:
                client.enforce("delete:database")
        
        error = exc_info.value
        assert error.action == "delete:database"
        assert error.policy == "strict"
        assert error.rule == "no-delete"
        
        client.close()
    
    def test_enforce_with_resource(self, gateway_url, agent_token, mock_response):
        """Enforce passes resource to check."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            client.enforce("read:contacts", resource="contacts/456")
        
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["X-MeshGuard-Resource"] == "contacts/456"
        
        client.close()


class TestGovernContext:
    """Test governed context manager."""
    
    def test_govern_allows_execution(self, gateway_url, agent_token, mock_response):
        """Govern context allows code execution when permitted."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"policy": "default"})
        
        executed = False
        with patch.object(client._client, "get", return_value=mock_resp):
            with client.govern("read:contacts") as decision:
                executed = True
                assert decision.allowed is True
        
        assert executed is True
        client.close()
    
    def test_govern_prevents_execution_when_denied(self, gateway_url, agent_token, mock_response):
        """Govern context raises and prevents execution when denied."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"policy": "strict", "message": "Denied"},
        )
        
        executed = False
        with patch.object(client._client, "get", return_value=mock_resp):
            with pytest.raises(PolicyDeniedError):
                with client.govern("delete:database"):
                    executed = True
        
        assert executed is False
        client.close()
    
    def test_govern_with_resource(self, gateway_url, agent_token, mock_response):
        """Govern context passes resource."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            with client.govern("read:contacts", resource="contacts/789"):
                pass
        
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["X-MeshGuard-Resource"] == "contacts/789"
        
        client.close()
    
    def test_governed_context_class(self, gateway_url, agent_token):
        """GovernedContext class holds correct attributes."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        ctx = GovernedContext(client, "test:action", "test-resource")
        
        assert ctx.client is client
        assert ctx.action == "test:action"
        assert ctx.resource == "test-resource"
        assert ctx.decision is None
        
        client.close()
