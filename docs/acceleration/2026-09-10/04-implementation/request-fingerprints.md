# Request fingerprints and fixture/snapshot v2

## Objective

Prevent a stale response fixture from being accepted as evidence for a changed prompt, system message, parameter set, document rendering, model, or adapter convention.

## Canonical request payload

```python
from dataclasses import asdict, dataclass

from .hashing import content_hash


@dataclass(frozen=True)
class RequestIdentity:
    schema_version: str
    adapter: dict[str, str]
    item_id: str
    model: str
    system: str
    prompt: str
    params: dict


def request_identity(request, adapter_info: dict[str, str]) -> dict:
    return {
        "schema_version": "1",
        "adapter": adapter_info,
        "item_id": request.item_id,
        "model": request.model,
        "system": request.system,
        "prompt": request.prompt,
        "params": request.params,
    }


def request_sha256(request, adapter_info: dict[str, str]) -> str:
    return content_hash(request_identity(request, adapter_info))
```

The payload must contain only semantic request inputs. Do not include paths, timestamps, CI URLs, retry counts, or fixture filenames.

## Fixture v2 shape

```json
{
  "schema_version": "2",
  "plan_sha256": "sha256:...",
  "responses": {
    "demo-pro-1": {
      "item-1": {
        "request_sha256": "sha256:...",
        "status": "ok",
        "text": "...",
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "latency_ms": 410.2
      }
    }
  }
}
```

At lookup, require exact agreement between the freshly rendered request hash and stored evidence hash. A mismatch raises a configuration/evidence error. Do not silently fall back to `(model, item_id)`.

## Migration

- Fixture v1 can be read only behind an explicit `legacy_unbound` mode.
- The report must disclose unbound evidence and may use a distinct verdict class or exit 2 in strict mode.
- A migration utility may add schema markers and reorganize fields, but must never manufacture request hashes from current prompts and claim they produced historical outputs.
- Re-record examples to create genuine bound fixtures.

## Tests

- system, prompt, rendered document order/text, params, model, adapter version, and item ID each change the hash;
- dict key order does not change the hash;
- non-finite params are rejected;
- stale fixture mismatch exits 2 before scoring;
- path and checkout location do not affect the hash;
- LF/CRLF source layout does not affect a request built from equivalent parsed JSON;
- duplicate evidence entries are rejected;
- successful and provider-error evidence are both request-bound.
