"""
Tests for LangChain integration.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from meshguard import MeshGuardClient, PolicyDeniedError
from meshguard.langchain import (
    governed_tool,
    GovernedTool,
    GovernedToolkit,
)


class TestGovernedToolDecorator:
    """Test the @governed_tool decorator."""
    
    def test_governed_tool_allows_execution(self, gateway_url, agent_token, mock_response):
        """Decorated function executes when policy allows."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        @governed_tool("read:contacts", client=client)
        def fetch_contacts(query: str) -> str:
            return f"Found contacts for: {query}"
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = fetch_contacts("John")
        
        assert result == "Found contacts for: John"
        client.close()
    
    def test_governed_tool_denies_execution(self, gateway_url, agent_token, mock_response):
        """Decorated function raises when policy denies."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"policy": "strict", "message": "Not allowed"},
        )
        
        @governed_tool("delete:contacts", client=client)
        def delete_contacts() -> str:
            return "Deleted"
        
        with patch.object(client._client, "get", return_value=mock_resp):
            with pytest.raises(PolicyDeniedError):
                delete_contacts()
        
        client.close()
    
    def test_governed_tool_on_deny_callback(self, gateway_url, agent_token, mock_response):
        """on_deny callback is called when policy denies."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"message": "Denied"},
        )
        
        def handle_denial(error, *args, **kwargs):
            return f"Denied: {error.reason}"
        
        @governed_tool("write:email", client=client, on_deny=handle_denial)
        def send_email(to: str) -> str:
            return f"Sent to {to}"
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = send_email("test@example.com")
        
        assert "Denied" in result
        client.close()
    
    def test_governed_tool_preserves_metadata(self, gateway_url, agent_token):
        """Decorator preserves function metadata."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        @governed_tool("read:data", client=client)
        def my_function():
            """My docstring."""
            pass
        
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."
        assert my_function._meshguard_action == "read:data"
        
        client.close()
    
    def test_governed_tool_creates_client_if_not_provided(self, mock_response):
        """Decorator creates client from env vars if not provided."""
        @governed_tool("read:test")
        def test_func():
            return "executed"
        
        # Mock the MeshGuardClient that gets created inside
        with patch("meshguard.langchain.MeshGuardClient") as MockClient:
            mock_client = MagicMock()
            mock_decision = MagicMock()
            mock_decision.allowed = True
            mock_client.enforce.return_value = mock_decision
            MockClient.return_value = mock_client
            
            result = test_func()
        
        assert result == "executed"
        MockClient.assert_called_once()


class TestGovernedTool:
    """Test the GovernedTool wrapper class."""
    
    def test_governed_tool_run(self, gateway_url, agent_token, mock_response):
        """GovernedTool.run() works correctly."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        # Create a mock tool
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Search the web"
        mock_tool.run.return_value = "Search results"
        
        governed = GovernedTool(
            tool=mock_tool,
            action="read:search",
            client=client,
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = governed.run("test query")
        
        assert result == "Search results"
        mock_tool.run.assert_called_once_with("test query")
        client.close()
    
    def test_governed_tool_run_denied(self, gateway_url, agent_token, mock_response):
        """GovernedTool.run() raises when denied."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"message": "Denied"},
        )
        
        mock_tool = MagicMock()
        governed = GovernedTool(
            tool=mock_tool,
            action="write:dangerous",
            client=client,
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            with pytest.raises(PolicyDeniedError):
                governed.run("dangerous operation")
        
        mock_tool.run.assert_not_called()
        client.close()
    
    def test_governed_tool_on_deny(self, gateway_url, agent_token, mock_response):
        """GovernedTool uses on_deny callback."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"message": "Denied"},
        )
        
        mock_tool = MagicMock()
        
        def deny_handler(error, *args, **kwargs):
            return "Access denied"
        
        governed = GovernedTool(
            tool=mock_tool,
            action="write:test",
            client=client,
            on_deny=deny_handler,
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = governed.run("test")
        
        assert result == "Access denied"
        client.close()
    
    def test_governed_tool_callable(self, gateway_url, agent_token, mock_response):
        """GovernedTool is callable."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        mock_tool = MagicMock()
        mock_tool.run.return_value = "result"
        
        governed = GovernedTool(
            tool=mock_tool,
            action="read:test",
            client=client,
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = governed("test arg")
        
        assert result == "result"
        client.close()
    
    def test_governed_tool_copies_attributes(self, gateway_url, agent_token):
        """GovernedTool copies name and description from wrapped tool."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_tool = MagicMock()
        mock_tool.name = "custom_tool"
        mock_tool.description = "A custom tool description"
        
        governed = GovernedTool(
            tool=mock_tool,
            action="read:custom",
            client=client,
        )
        
        assert governed.name == "custom_tool"
        assert governed.description == "A custom tool description"
        client.close()
    
    @pytest.mark.asyncio
    async def test_governed_tool_arun(self, gateway_url, agent_token, mock_response):
        """GovernedTool.arun() works correctly."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(status_code=200, json_data={})
        
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value="async result")
        
        governed = GovernedTool(
            tool=mock_tool,
            action="read:async",
            client=client,
        )
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = await governed.arun("async query")
        
        assert result == "async result"
        mock_tool.arun.assert_called_once_with("async query")
        client.close()


class TestGovernedToolkit:
    """Test the GovernedToolkit class."""
    
    def test_toolkit_get_tools(self, gateway_url, agent_token):
        """Toolkit returns governed tools."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        tool1 = MagicMock()
        tool1.name = "search"
        
        tool2 = MagicMock()
        tool2.name = "calculator"
        
        toolkit = GovernedToolkit(
            tools=[tool1, tool2],
            client=client,
            action_map={
                "search": "read:web_search",
                "calculator": "execute:math",
            },
        )
        
        governed_tools = toolkit.get_tools()
        
        assert len(governed_tools) == 2
        assert all(isinstance(t, GovernedTool) for t in governed_tools)
        
        client.close()
    
    def test_toolkit_action_map(self, gateway_url, agent_token):
        """Toolkit uses action_map for tool actions."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        tool = MagicMock()
        tool.name = "search"
        
        toolkit = GovernedToolkit(
            tools=[tool],
            client=client,
            action_map={"search": "custom:action"},
        )
        
        governed_tools = toolkit.get_tools()
        assert governed_tools[0].action == "custom:action"
        
        client.close()
    
    def test_toolkit_default_action(self, gateway_url, agent_token):
        """Toolkit uses default_action for unmapped tools."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        tool = MagicMock()
        tool.name = "unknown_tool"
        
        toolkit = GovernedToolkit(
            tools=[tool],
            client=client,
            action_map={},
            default_action="execute:unknown",
        )
        
        governed_tools = toolkit.get_tools()
        assert governed_tools[0].action == "execute:unknown"
        
        client.close()
    
    def test_toolkit_get_action(self, gateway_url, agent_token):
        """Toolkit.get_action returns correct action."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        toolkit = GovernedToolkit(
            tools=[],
            client=client,
            action_map={"search": "read:search"},
            default_action="execute:default",
        )
        
        tool_with_name = MagicMock()
        tool_with_name.name = "search"
        
        tool_without_name = MagicMock()
        tool_without_name.name = "other"
        
        assert toolkit.get_action(tool_with_name) == "read:search"
        assert toolkit.get_action(tool_without_name) == "execute:default"
        
        client.close()
    
    def test_toolkit_on_deny_propagates(self, gateway_url, agent_token, mock_response):
        """Toolkit propagates on_deny to governed tools."""
        client = MeshGuardClient(
            gateway_url=gateway_url,
            agent_token=agent_token,
        )
        
        mock_resp = mock_response(
            status_code=403,
            json_data={"message": "Denied"},
        )
        
        tool = MagicMock()
        tool.name = "test"
        
        def deny_handler(error, *args, **kwargs):
            return "Handled denial"
        
        toolkit = GovernedToolkit(
            tools=[tool],
            client=client,
            on_deny=deny_handler,
        )
        
        governed_tools = toolkit.get_tools()
        
        with patch.object(client._client, "get", return_value=mock_resp):
            result = governed_tools[0].run()
        
        assert result == "Handled denial"
        client.close()
