"""llm-release-gate: block unsafe LLM app changes at review time.

Runs a baseline and a candidate configuration over a versioned golden dataset,
compares quality, abstention behavior, citation validity, schema validity,
latency, token use and cost, and fails the CI check on a material regression.
"""

__version__ = "0.2.0"

TOOL_NAME = "llm-release-gate"

# Version of the JSON report / manifest schema this build emits.
REPORT_SCHEMA_VERSION = "1"
