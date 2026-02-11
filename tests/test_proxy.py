"""
Tests for proxy request functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from meshguard import MeshGuardClient


class TestProxyRequests:
    """Test proxy request methods."""
    
    def test_request_method(self, gateway_url, agent_token, mock_response):
        """Generic request method works correctly."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"result": "success"})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            response = client.request(
                method="POST",
                path="/api/data",
                action="write:data",
                json={"key": "value"},
            )
        
        # Verify request parameters
        call_args = mock_req.call_args
        assert call_args.args[0] == "POST"
        assert f"{gateway_url}/proxy/api/data" in call_args.args[1]
        
        headers = call_args.kwargs["headers"]
        assert headers["X-MeshGuard-Action"] == "write:data"
        assert "Authorization" in headers
        
        client.close()
    
    def test_request_strips_leading_slash(self, gateway_url, agent_token, mock_response):
        """Request path has leading slash handled correctly."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.request("GET", "/api/test", action="read:test")
        
        url = mock_req.call_args.args[1]
        assert "/proxy/api/test" in url
        assert "/proxy//api" not in url
        
        client.close()
    
    def test_get_shorthand(self, gateway_url, agent_token, mock_response):
        """GET shorthand method works."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"items": []})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            response = client.get("/api/items", action="read:items")
        
        assert mock_req.call_args.args[0] == "GET"
        client.close()
    
    def test_post_shorthand(self, gateway_url, agent_token, mock_response):
        """POST shorthand method works."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=201, json_data={"id": "new-item"})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            response = client.post(
                "/api/items",
                action="write:items",
                json={"name": "test"},
            )
        
        assert mock_req.call_args.args[0] == "POST"
        client.close()
    
    def test_put_shorthand(self, gateway_url, agent_token, mock_response):
        """PUT shorthand method works."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"updated": True})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            response = client.put(
                "/api/items/123",
                action="write:items",
                json={"name": "updated"},
            )
        
        assert mock_req.call_args.args[0] == "PUT"
        client.close()
    
    def test_delete_shorthand(self, gateway_url, agent_token, mock_response):
        """DELETE shorthand method works."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=204)
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            response = client.delete("/api/items/123", action="delete:items")
        
        assert mock_req.call_args.args[0] == "DELETE"
        client.close()
    
    def test_request_merges_headers(self, gateway_url, agent_token, mock_response):
        """Request merges custom headers with auth headers."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.request(
                "GET",
                "/api/test",
                action="read:test",
                headers={"X-Custom-Header": "custom-value"},
            )
        
        headers = mock_req.call_args.kwargs["headers"]
        assert headers["X-Custom-Header"] == "custom-value"
        assert headers["X-MeshGuard-Action"] == "read:test"
        assert "Authorization" in headers
        
        client.close()
    
    def test_request_passes_kwargs(self, gateway_url, agent_token, mock_response):
        """Request passes additional kwargs to httpx."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.request(
                "POST",
                "/api/upload",
                action="write:upload",
                data=b"file content",
                params={"version": "2"},
            )
        
        kwargs = mock_req.call_args.kwargs
        assert kwargs["data"] == b"file content"
        assert kwargs["params"] == {"version": "2"}
        
        client.close()
