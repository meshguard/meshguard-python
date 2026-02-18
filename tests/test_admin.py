"""
Tests for admin operations (agents, policies, audit).
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from meshguard import MeshGuardClient, AuthenticationError
from meshguard.client import Agent


class TestListAgents:
    """Test agent listing functionality."""
    
    def test_list_agents_success(self, gateway_url, admin_token, mock_response):
        """List agents returns Agent objects."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(
            status_code=200,
            json_data={
                "agents": [
                    {
                        "id": "agent-1",
                        "name": "test-agent-1",
                        "trustTier": "verified",
                        "tags": ["prod"],
                        "orgId": "org-1",
                    },
                    {
                        "id": "agent-2",
                        "name": "test-agent-2",
                        "trustTier": "untrusted",
                        "tags": [],
                    },
                ]
            },
        )
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            agents = client.list_agents()
        
        assert len(agents) == 2
        assert all(isinstance(a, Agent) for a in agents)
        
        assert agents[0].id == "agent-1"
        assert agents[0].name == "test-agent-1"
        assert agents[0].trust_tier == "verified"
        assert agents[0].tags == ["prod"]
        assert agents[0].org_id == "org-1"
        
        assert agents[1].id == "agent-2"
        assert agents[1].trust_tier == "untrusted"
        assert agents[1].org_id is None
        
        # Verify admin headers were used
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert headers["X-Admin-Token"] == admin_token
        
        client.close()
    
    def test_list_agents_empty(self, gateway_url, admin_token, mock_response):
        """List agents handles empty list."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"agents": []})
        
        with patch.object(client._client, "get", return_value=mock_resp):
            agents = client.list_agents()
        
        assert agents == []
        client.close()
    
    def test_list_agents_requires_admin_token(self, gateway_url):
        """List agents fails without admin token."""
        client = MeshGuardClient(gateway_url=gateway_url)
        
        with pytest.raises(AuthenticationError, match="Admin token required"):
            client.list_agents()
        
        client.close()


class TestCreateAgent:
    """Test agent creation functionality."""
    
    def test_create_agent_success(self, gateway_url, admin_token, mock_response):
        """Create agent returns agent details."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(
            status_code=201,
            json_data={
                "id": "new-agent-id",
                "name": "new-agent",
                "token": "new-agent-token",
                "trustTier": "verified",
            },
        )
        
        with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
            result = client.create_agent(
                name="new-agent",
                trust_tier="verified",
                tags=["production", "api"],
            )
        
        assert result["id"] == "new-agent-id"
        assert result["token"] == "new-agent-token"
        
        # Verify request body
        call_args = mock_post.call_args
        body = call_args.kwargs["json"]
        assert body["name"] == "new-agent"
        assert body["trustTier"] == "verified"
        assert body["tags"] == ["production", "api"]
        
        client.close()
    
    def test_create_agent_defaults(self, gateway_url, admin_token, mock_response):
        """Create agent uses default values."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=201, json_data={"id": "agent"})
        
        with patch.object(client._client, "post", return_value=mock_resp) as mock_post:
            client.create_agent(name="minimal-agent")
        
        body = mock_post.call_args.kwargs["json"]
        assert body["trustTier"] == "verified"
        assert body["tags"] == []
        
        client.close()


class TestRevokeAgent:
    """Test agent revocation functionality."""
    
    def test_revoke_agent_success(self, gateway_url, admin_token, mock_response):
        """Revoke agent completes successfully."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=204)
        
        with patch.object(client._client, "delete", return_value=mock_resp) as mock_delete:
            client.revoke_agent("agent-to-revoke")
        
        # Verify correct URL
        call_args = mock_delete.call_args
        url = call_args.args[0]
        assert "/admin/agents/agent-to-revoke" in url
        
        client.close()


class TestListPolicies:
    """Test policy listing functionality."""
    
    def test_list_policies_success(self, gateway_url, admin_token, mock_response):
        """List policies returns policy data."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(
            status_code=200,
            json_data={
                "policies": [
                    {
                        "id": "policy-1",
                        "name": "default",
                        "rules": [{"action": "read:*", "effect": "allow"}],
                    },
                    {
                        "id": "policy-2",
                        "name": "strict",
                        "rules": [{"action": "*", "effect": "deny"}],
                    },
                ]
            },
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            policies = client.list_policies()
        
        assert len(policies) == 2
        assert policies[0]["name"] == "default"
        assert policies[1]["name"] == "strict"
        
        client.close()
    
    def test_list_policies_empty(self, gateway_url, admin_token, mock_response):
        """List policies handles empty list."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"policies": []})
        
        with patch.object(client._client, "get", return_value=mock_resp):
            policies = client.list_policies()
        
        assert policies == []
        client.close()


class TestGetAuditLog:
    """Test audit log retrieval functionality."""
    
    def test_get_audit_log_success(self, gateway_url, admin_token, mock_response):
        """Get audit log returns entries."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(
            status_code=200,
            json_data={
                "entries": [
                    {
                        "id": "entry-1",
                        "action": "read:contacts",
                        "decision": "allow",
                        "timestamp": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "entry-2",
                        "action": "write:email",
                        "decision": "deny",
                        "timestamp": "2024-01-01T00:01:00Z",
                    },
                ]
            },
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            entries = client.get_audit_log()
        
        assert len(entries) == 2
        assert entries[0]["decision"] == "allow"
        assert entries[1]["decision"] == "deny"
        
        client.close()
    
    def test_get_audit_log_with_params(self, gateway_url, admin_token, mock_response):
        """Get audit log passes query parameters."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"entries": []})
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            client.get_audit_log(limit=25, decision="deny")
        
        params = mock_get.call_args.kwargs["params"]
        assert params["limit"] == 25
        assert params["decision"] == "deny"
        
        client.close()
    
    def test_get_audit_log_default_limit(self, gateway_url, admin_token, mock_response):
        """Get audit log uses default limit."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            admin_token=admin_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={"entries": []})
        
        with patch.object(client._client, "get", return_value=mock_resp) as mock_get:
            client.get_audit_log()
        
        params = mock_get.call_args.kwargs["params"]
        assert params["limit"] == 50
        
        client.close()
