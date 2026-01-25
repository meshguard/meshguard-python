"""
MeshGuard LangChain Integration

Provides decorators and wrappers for governing LangChain agents and tools.
"""

import functools
from typing import Any, Callable, Optional, List, Dict, Union

from .client import MeshGuardClient
from .exceptions import PolicyDeniedError


def governed_tool(
    action: str,
    client: Optional[MeshGuardClient] = None,
    on_deny: Optional[Callable] = None,
):
    """
    Decorator to govern a LangChain tool with MeshGuard policy.
    
    Usage:
        from meshguard import MeshGuardClient
        from meshguard.langchain import governed_tool
        
        client = MeshGuardClient()
        
        @governed_tool("read:contacts", client=client)
        def fetch_contacts(query: str) -> str:
            # This only runs if policy allows
            return contacts_db.search(query)
    
    Args:
        action: MeshGuard action for policy evaluation
        client: MeshGuard client (or uses MESHGUARD_* env vars)
        on_deny: Optional callback when action is denied
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            _client = client or MeshGuardClient()
            
            try:
                decision = _client.enforce(action)
                # Optionally inject decision into kwargs
                if "meshguard_decision" in func.__code__.co_varnames:
                    kwargs["meshguard_decision"] = decision
                return func(*args, **kwargs)
                
            except PolicyDeniedError as e:
                if on_deny:
                    return on_deny(e, *args, **kwargs)
                raise
        
        # Preserve tool metadata for LangChain
        wrapper._meshguard_action = action
        return wrapper
    
    return decorator


class GovernedTool:
    """
    Wrapper to govern an existing LangChain tool.
    
    Usage:
        from langchain.tools import DuckDuckGoSearchRun
        from meshguard import MeshGuardClient
        from meshguard.langchain import GovernedTool
        
        client = MeshGuardClient()
        search = DuckDuckGoSearchRun()
        
        governed_search = GovernedTool(
            tool=search,
            action="read:web_search",
            client=client,
        )
    """
    
    def __init__(
        self,
        tool: Any,
        action: str,
        client: Optional[MeshGuardClient] = None,
        on_deny: Optional[Callable] = None,
    ):
        self.tool = tool
        self.action = action
        self.client = client or MeshGuardClient()
        self.on_deny = on_deny
        
        # Copy tool attributes
        self.name = getattr(tool, "name", tool.__class__.__name__)
        self.description = getattr(tool, "description", "")
    
    def run(self, *args, **kwargs) -> Any:
        """Run the tool with governance."""
        try:
            self.client.enforce(self.action)
            return self.tool.run(*args, **kwargs)
        except PolicyDeniedError as e:
            if self.on_deny:
                return self.on_deny(e, *args, **kwargs)
            raise
    
    async def arun(self, *args, **kwargs) -> Any:
        """Async run the tool with governance."""
        try:
            self.client.enforce(self.action)
            return await self.tool.arun(*args, **kwargs)
        except PolicyDeniedError as e:
            if self.on_deny:
                return self.on_deny(e, *args, **kwargs)
            raise
    
    def __call__(self, *args, **kwargs) -> Any:
        return self.run(*args, **kwargs)


class GovernedToolkit:
    """
    Govern multiple tools with MeshGuard policies.
    
    Usage:
        from langchain.agents import load_tools
        from meshguard import MeshGuardClient
        from meshguard.langchain import GovernedToolkit
        
        client = MeshGuardClient()
        tools = load_tools(["serpapi", "llm-math"])
        
        toolkit = GovernedToolkit(
            tools=tools,
            client=client,
            action_map={
                "serpapi": "read:web_search",
                "Calculator": "execute:math",
            },
            default_action="execute:tool",
        )
        
        governed_tools = toolkit.get_tools()
    """
    
    def __init__(
        self,
        tools: List[Any],
        client: Optional[MeshGuardClient] = None,
        action_map: Optional[Dict[str, str]] = None,
        default_action: str = "execute:tool",
        on_deny: Optional[Callable] = None,
    ):
        self.tools = tools
        self.client = client or MeshGuardClient()
        self.action_map = action_map or {}
        self.default_action = default_action
        self.on_deny = on_deny
    
    def get_action(self, tool: Any) -> str:
        """Get action for a tool."""
        name = getattr(tool, "name", tool.__class__.__name__)
        return self.action_map.get(name, self.default_action)
    
    def get_tools(self) -> List[GovernedTool]:
        """Get governed versions of all tools."""
        return [
            GovernedTool(
                tool=tool,
                action=self.get_action(tool),
                client=self.client,
                on_deny=self.on_deny,
            )
            for tool in self.tools
        ]


def create_governed_agent(
    llm: Any,
    tools: List[Any],
    client: Optional[MeshGuardClient] = None,
    action_map: Optional[Dict[str, str]] = None,
    agent_type: str = "zero-shot-react-description",
    **kwargs,
) -> Any:
    """
    Create a LangChain agent with governed tools.
    
    Usage:
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
    
    Args:
        llm: LangChain LLM
        tools: List of LangChain tools
        client: MeshGuard client
        action_map: Map of tool names to MeshGuard actions
        agent_type: Type of agent to create
        **kwargs: Additional arguments for agent initialization
    """
    try:
        from langchain.agents import initialize_agent, AgentType
    except ImportError:
        raise ImportError(
            "LangChain is required for this feature. "
            "Install it with: pip install langchain"
        )
    
    toolkit = GovernedToolkit(
        tools=tools,
        client=client,
        action_map=action_map,
    )
    
    agent_types = {
        "zero-shot-react-description": AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        "conversational-react-description": AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
        "structured-chat-zero-shot-react-description": AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    }
    
    return initialize_agent(
        tools=toolkit.get_tools(),
        llm=llm,
        agent=agent_types.get(agent_type, AgentType.ZERO_SHOT_REACT_DESCRIPTION),
        **kwargs,
    )
