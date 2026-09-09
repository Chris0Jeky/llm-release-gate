# Safe Markdown rendering and bounded public reports

## Objective

Prevent dynamic dataset/config/model/metric/note/error text from breaking Markdown tables, creating unintended mentions, injecting headings/details, or producing unbounded pull-request comments.

## Escaping

```python
import re

_MENTION = re.compile(r"(?<![\w`])@(?=[A-Za-z0-9-])")


def neutralize_mentions(value: object) -> str:
    return _MENTION.sub("@\u200b", str(value))


def markdown_cell(value: object) -> str:
    text = neutralize_mentions(value)
    return (
        text.replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("\r\n", "<br>")
            .replace("\r", "<br>")
            .replace("\n", "<br>")
    )
```

Apply escaping at the renderer boundary to every dynamic table cell. Do not escape trusted static Markdown syntax globally. Backticks inside identity values should either be escaped or rendered in fenced/detail-safe form.

## Public report limits

- no raw output in the default public PR profile;
- cap listed breached rules and failing item IDs deterministically;
- report omitted counts (`showing 20 of 183 failures`);
- cap notes/details by Unicode code points or UTF-8 bytes with deterministic suffixes;
- keep JSON machine output complete only in an approved private/local profile;
- classify provider errors before rendering rather than publishing raw exception text.

## GitHub comment mechanics

- marker-scope updates to this Action's own comment only;
- comment failure remains non-fatal to the gate verdict;
- never run untrusted pull-request code in a privileged `pull_request_target` job;
- prefer job summaries/artifacts when permissions do not allow comments.

## Tests

Use dynamic values containing:

- `|`, newlines, backslashes, backticks, `<details>`, HTML, and Markdown links;
- `@owner`, `@org/team`, issue references, and email-like strings;
- right-to-left controls and unusual Unicode;
- very long item IDs and error details;
- raw output containing secrets or GitHub commands.

Assert the rendered table remains structurally valid, no automatic mention token remains, output ordering/truncation is deterministic, and HTML rendering remains escaped independently.
