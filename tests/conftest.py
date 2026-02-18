"""
Pytest configuration and fixtures for MeshGuard tests.
"""

import pytest
import httpx
from unittest.mock import MagicMock


@pytest.fixture
def mock_client():
    """Create a mock httpx client for testing."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def gateway_url():
    """Default gateway URL for tests."""
    return "https://test.meshguard.app"


@pytest.fixture
def agent_token():
    """Test agent token."""
    return "test-agent-token-12345"


@pytest.fixture
def admin_token():
    """Test admin token."""
    return "test-admin-token-67890"


@pytest.fixture
def mock_response():
    """Factory for creating mock responses."""
    def _make_response(
        status_code: int = 200,
        json_data: dict = None,
        content: bytes = None,
    ):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.content = content or (json_data and b"{}") or b""
        response.text = str(json_data) if json_data else ""
        
        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON content")
        
        return response
    
    return _make_response
