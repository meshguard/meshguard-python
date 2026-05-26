# Migrating From meshguard-python To AGT + MeshGuard

The Python SDK remains supported for existing integrations. The forward path for new in-process policy enforcement is Microsoft AGT with the MeshGuard control-plane adapter.

## Current SDK Pattern

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

## Migration Steps

1. Keep existing `meshguard-python` calls in place.
2. Add AGT instrumentation to one agent path.
3. Configure `meshguard-agt` against the same tenant.
4. Dry-run decisions against production audit history.
5. Move new policy features to AGT + MeshGuard first.

