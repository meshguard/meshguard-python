# Using AGT With meshguard-python

MeshGuard supports both direct Python SDK governance and AGT-native governance. AGT is an additional policy enforcement path for teams that already use Microsoft Agent Governance Toolkit or want AGT instrumentation in selected agents.

## Direct SDK Pattern

```python
from meshguard import MeshGuardClient

client = MeshGuardClient(agent_token="...")
decision = client.check("read:contacts")
```

## AGT Adapter Pattern

```python
from meshguard_agt import configure_agt_with_meshguard

kernel = configure_agt_with_meshguard(
    gateway_url="https://gateway.meshguard.app",
    tenant_id="acme-corp",
    agent_token=os.environ["MESHGUARD_AGENT_TOKEN"],
)
```

## How To Use Both

1. Keep existing `meshguard-python` integrations in place.
2. Add AGT instrumentation where it fits a new or existing agent workflow.
3. Point both paths at the same MeshGuard tenant, policies, audit log, and operator console.
4. Use audit history to compare behavior when running both paths side by side.
5. Choose the enforcement path per agent, framework, and deployment architecture.
