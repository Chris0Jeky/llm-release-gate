# Preserve evidence after item-processing failures

A provider may return a response with known token usage and latency before local
pricing, parsing or scoring fails. Dropping that response's measurements and
summing only the surviving items can understate consumption, particularly when
an explicit error-rate rule tolerates failures.

The runner now creates one fresh record per item and records returned text, token
counts and latency before pricing or parsing. Successfully computed cost is also
retained after later failures. Invalid token counts remain unknown; raw provider
payloads are not copied. Partial scorer results are not published as a completed
score vector. `GateConfigError` still aborts without publishing a new report.

Non-provider failures carry an optional `error_stage`: `request`, `response`,
`pricing`, `parse`, or `score`. A run with such failures also includes the optional
`n_processing_errors` summary count. Its report notices and sample descriptions
use the broader term `item-processing errors` rather than attributing every
failure to the provider. Provider-only failures retain their existing fields,
wording and answered-item aggregate scope.

If a failure occurs after a provider response, `tokens.total` and `cost.total_usd`
are unavailable with an explicit reason. The known per-item measurements remain
inspectable; they are not silently discarded or presented as a complete total.
Quality and latency aggregates retain their successful-item population. A
pre-request failure cannot inherit another item's measurements.

This deliberately conservative policy does not estimate failed-call usage or
introduce new aggregate populations. The existing `on_unavailable` policy still
applies: its default fails, but an explicit warn/skip remains warn/skip. An error
rule allowing failures no longer makes a partial cost sum available by itself.
The diagnostic `run` command retains its default exit behavior and works with
`--fail-on-errors`, preserving the same diagnostic payload in both modes.

This repairs the two findings on PR #38. Healthy runs and provider-only failure
reports keep their previous representation. Reports involving local processing
failures change content/hashes as documented here; the report schema is unchanged
and the new diagnostic fields are additive. The features are on unreleased main;
no release tag is moved by this repair.
