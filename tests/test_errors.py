"""
Tests for error handling and exception classes.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from meshguard import (
    MeshGuardClient,
    MeshGuardError,
    AuthenticationError,
    PolicyDeniedError,
    RateLimitError,
)


class TestExceptionClasses:
    """Test exception class structures."""
    
    def test_meshguard_error_base(self):
        """MeshGuardError is the base exception."""
        error = MeshGuardError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_authentication_error(self):
        """AuthenticationError inherits from MeshGuardError."""
        error = AuthenticationError("Invalid token")
        assert str(error) == "Invalid token"
        assert isinstance(error, MeshGuardError)
    
    def test_rate_limit_error(self):
        """RateLimitError inherits from MeshGuardError."""
        error = RateLimitError("Too many requests")
        assert str(error) == "Too many requests"
        assert isinstance(error, MeshGuardError)
    
    def test_policy_denied_error_minimal(self):
        """PolicyDeniedError with minimal args."""
        error = PolicyDeniedError(action="read:contacts")
        
        assert error.action == "read:contacts"
        assert error.policy is None
        assert error.rule is None
        assert error.reason == "Access denied by policy"
        assert "Action 'read:contacts' denied" in str(error)
    
    def test_policy_denied_error_full(self):
        """PolicyDeniedError with all args."""
        error = PolicyDeniedError(
            action="delete:database",
            policy="strict-policy",
            rule="no-delete-rule",
            reason="Delete operations are prohibited",
        )
        
        assert error.action == "delete:database"
        assert error.policy == "strict-policy"
        assert error.rule == "no-delete-rule"
        assert error.reason == "Delete operations are prohibited"
        
        message = str(error)
        assert "Action 'delete:database' denied" in message
        assert "policy 'strict-policy'" in message
        assert "rule: no-delete-rule" in message
        assert "Delete operations are prohibited" in message
    
    def test_policy_denied_error_is_meshguard_error(self):
        """PolicyDeniedError inherits from MeshGuardError."""
        error = PolicyDeniedError(action="test")
        assert isinstance(error, MeshGuardError)


class TestResponseErrorHandling:
    """Test error handling from HTTP responses."""
    
    def test_401_raises_authentication_error(self, gateway_url, agent_token):
        """401 response raises AuthenticationError."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.content = b"{}"
        
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            client._handle_response(mock_resp)
        
        client.close()
    
    def test_403_raises_policy_denied_error(self, gateway_url, agent_token):
        """403 response raises PolicyDeniedError."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 403
        mock_resp.content = b'{"action": "write:email", "policy": "read-only", "message": "Write denied"}'
        mock_resp.json.return_value = {
            "action": "write:email",
            "policy": "read-only",
            "message": "Write denied",
        }
        
        with pytest.raises(PolicyDeniedError) as exc_info:
            client._handle_response(mock_resp)
        
        error = exc_info.value
        assert error.action == "write:email"
        assert error.policy == "read-only"
        assert error.reason == "Write denied"
        
        client.close()
    
    def test_403_with_empty_body(self, gateway_url, agent_token):
        """403 response with empty body uses defaults."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 403
        mock_resp.content = b""
        
        with pytest.raises(PolicyDeniedError) as exc_info:
            client._handle_response(mock_resp)
        
        error = exc_info.value
        assert error.action == "unknown"
        assert error.reason == "Access denied by policy"
        
        client.close()
    
    def test_429_raises_rate_limit_error(self, gateway_url, agent_token):
        """429 response raises RateLimitError."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 429
        
        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            client._handle_response(mock_resp)
        
        client.close()
    
    def test_500_raises_meshguard_error(self, gateway_url, agent_token):
        """500 response raises generic MeshGuardError."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        
        with pytest.raises(MeshGuardError, match="Request failed: 500"):
            client._handle_response(mock_resp)
        
        client.close()
    
    def test_400_raises_meshguard_error(self, gateway_url, agent_token):
        """400 response raises generic MeshGuardError."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        
        with pytest.raises(MeshGuardError, match="Request failed: 400"):
            client._handle_response(mock_resp)
        
        client.close()
    
    def test_200_returns_json(self, gateway_url, agent_token):
        """200 response returns parsed JSON."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b'{"key": "value"}'
        mock_resp.json.return_value = {"key": "value"}
        
        result = client._handle_response(mock_resp)
        assert result == {"key": "value"}
        
        client.close()
    
    def test_200_empty_body_returns_empty_dict(self, gateway_url, agent_token):
        """200 response with empty body returns empty dict."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b""
        
        result = client._handle_response(mock_resp)
        assert result == {}
        
        client.close()
    
    def test_204_no_content(self, gateway_url, agent_token):
        """204 response returns empty dict."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 204
        mock_resp.content = b""
        
        result = client._handle_response(mock_resp)
        assert result == {}
        
        client.close()
