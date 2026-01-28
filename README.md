# MeshGuard Python SDK

[![PyPI version](https://badge.fury.io/py/meshguard.svg)](https://pypi.org/project/meshguard/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for [MeshGuard](https://meshguard.app) — Governance Control Plane for AI Agents.

## Installation

```bash
pip install meshguard
```

With LangChain support:

```bash
pip install meshguard[langchain]
```

## Quick Start

```python
from meshguard import MeshGuardClient

# Connect to MeshGuard (free tier available at meshguard.app)
client = MeshGuardClient(
    agent_token="your-agent-token",  # Get your token at meshguard.app
)

# Check if an action is allowed
decision = client.check("read:contacts")
if decision.allowed:
    print("Access granted!")
else:
    print(f"Denied: {decision.reason}")

# Enforce policy (raises PolicyDeniedError if denied)
client.enforce("read:contacts")

# Use context manager for governed code blocks
with client.govern("write:email") as decision:
    # This code only runs if allowed
    send_email(to="user@example.com", body="Hello!")
```

> **Pro tip:** Need advanced features like SSO, custom policies, or dedicated support? Check out [MeshGuard Pro and Enterprise](https://meshguard.app/pricing).

## Environment Variables

You can configure the client using environment variables:

```bash
export MESHGUARD_AGENT_TOKEN="your-agent-token"
export MESHGUARD_ADMIN_TOKEN="your-admin-token"  # For admin operations

# Optional: Override gateway URL (defaults to https://dashboard.meshguard.app)
# export MESHGUARD_GATEWAY_URL="https://meshguard.yourcompany.com"  # Enterprise self-hosted only
```

Then simply:

```python
from meshguard import MeshGuardClient

client = MeshGuardClient()  # Uses env vars, connects to MeshGuard SaaS
```

## LangChain Integration

### Govern Individual Tools

```python
from meshguard import MeshGuardClient
from meshguard.langchain import governed_tool

client = MeshGuardClient()

@governed_tool("read:contacts", client=client)
def fetch_contacts(query: str) -> str:
    """Fetch contacts matching query."""
    return contacts_db.search(query)

# The tool only runs if policy allows "read:contacts"
result = fetch_contacts("John")
```

### Wrap Existing Tools

```python
from langchain.tools import DuckDuckGoSearchRun
from meshguard import MeshGuardClient
from meshguard.langchain import GovernedTool

client = MeshGuardClient()
search = DuckDuckGoSearchRun()

# Wrap the tool with governance
governed_search = GovernedTool(
    tool=search,
    action="read:web_search",
    client=client,
)

result = governed_search.run("MeshGuard AI governance")
```

### Create Governed Agent

```python
from langchain.llms import OpenAI
from langchain.agents import load_tools
from meshguard import MeshGuardClient
from meshguard.langchain import create_governed_agent

client = MeshGuardClient()
llm = OpenAI()
tools = load_tools(["serpapi", "llm-math"], llm=llm)

agent = create_governed_agent(
    llm=llm,
    tools=tools,
    client=client,
    action_map={
        "serpapi": "read:web_search",
        "Calculator": "execute:math",
    },
)

result = agent.run("What is 25 * 4?")
```

### Handle Denied Actions

```python
from meshguard import MeshGuardClient, PolicyDeniedError
from meshguard.langchain import governed_tool

client = MeshGuardClient()

def handle_denial(error, *args, **kwargs):
    return f"Sorry, I can't do that: {error.reason}"

@governed_tool("write:email", client=client, on_deny=handle_denial)
def send_email(to: str, body: str) -> str:
    # Send email...
    return "Email sent!"

# If denied, returns the denial message instead of raising
result = send_email("user@example.com", "Hello!")
```

## Admin Operations

```python
from meshguard import MeshGuardClient

client = MeshGuardClient(admin_token="your-admin-token")

# List agents
agents = client.list_agents()
for agent in agents:
    print(f"{agent.name} ({agent.trust_tier})")

# Create agent
result = client.create_agent(
    name="my-agent",
    trust_tier="verified",
    tags=["production"],
)
print(f"Created agent: {result['id']}")
print(f"Token: {result['token']}")

# List policies
policies = client.list_policies()

# Get audit log
entries = client.get_audit_log(limit=10, decision="deny")
```

## Proxy Requests

Route requests through MeshGuard for automatic governance:

```python
from meshguard import MeshGuardClient

client = MeshGuardClient()

# GET request
response = client.get("/api/contacts", action="read:contacts")

# POST request
response = client.post(
    "/api/emails",
    action="write:email",
    json={"to": "user@example.com", "body": "Hello!"},
)
```

## Error Handling

```python
from meshguard import (
    MeshGuardClient,
    MeshGuardError,
    AuthenticationError,
    PolicyDeniedError,
    RateLimitError,
)

client = MeshGuardClient()

try:
    client.enforce("delete:database")
except PolicyDeniedError as e:
    print(f"Action denied: {e.action}")
    print(f"Policy: {e.policy}")
    print(f"Reason: {e.reason}")
except AuthenticationError:
    print("Invalid or expired token")
except RateLimitError:
    print("Rate limit exceeded")
except MeshGuardError as e:
    print(f"MeshGuard error: {e}")
```

## API Reference

### MeshGuardClient

| Method | Description |
|--------|-------------|
| `check(action)` | Check if action is allowed (returns PolicyDecision) |
| `enforce(action)` | Enforce policy (raises PolicyDeniedError if denied) |
| `govern(action)` | Context manager for governed code blocks |
| `health()` | Check gateway health |
| `list_agents()` | List all agents (admin) |
| `create_agent(name, trust_tier, tags)` | Create agent (admin) |
| `revoke_agent(agent_id)` | Revoke agent (admin) |
| `list_policies()` | List policies (admin) |
| `get_audit_log(limit, decision)` | Get audit entries (admin) |

### LangChain Integration

| Function/Class | Description |
|----------------|-------------|
| `@governed_tool(action)` | Decorator for governed tools |
| `GovernedTool(tool, action)` | Wrapper for existing tools |
| `GovernedToolkit(tools, action_map)` | Govern multiple tools |
| `create_governed_agent(llm, tools)` | Create governed agent |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- **Website:** https://meshguard.app
- **Dashboard:** https://dashboard.meshguard.app
- **Documentation:** https://github.com/meshguard/meshguard
- **Issues:** https://github.com/meshguard/meshguard-python/issues
