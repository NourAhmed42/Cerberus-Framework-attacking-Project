# Cerberus AI — Examples

## Running an OSINT scan
```python
from osint_framework.core.engine import OSINTEngine
engine = OSINTEngine()
await engine.initialize()
report = await engine.run_intelligence_cycle("example.com", modules=["cybint"])
print(report.executive_summary)
```

## Creating an engagement
```bash
curl -X POST http://localhost:8000/api/v1/engagements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_name": "Q3 Assessment", "organization_name": "Acme Corp"}'
```

## Running an attack module (Pentest Framework)
```python
from app.ai_engine.pentest import (
    ExecutionEngine, PentestContext, ScopeConfig, default_registry,
)

registry = default_registry()          # auto-discovered modules
engine = ExecutionEngine(registry)
context = PentestContext(
    target="https://example.com/api/users?id=1",
    scope=ScopeConfig(allowed_targets=["example.com"]),
)
findings = await engine.execute("sqli_probe", context)
for finding in findings:
    print(finding.severity.value, finding.title)
```
