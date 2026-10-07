# Numerical reproducibility

The runner uses `math.fsum` explicitly for item-cost totals and latency sums
(before dividing to obtain the mean). It does not delegate floating-point
accumulation to the interpreter's built-in `sum`, whose algorithm changed in
Python 3.12. Token and sample counts retain exact integer arithmetic.

This fixes issue #69 without rounding costs to a currency unit or changing
per-item pricing. Missing cost still makes the complete cost total unavailable;
a non-representable sum also stays unavailable and cannot become a fabricated
zero or partial total. Existing unavailable-metric threshold policy is unchanged.

Corrected aggregate values and derived deltas can differ in the last floating-point
bits from older reports, so affected result hashes change. Comparisons exactly on
a floating-point boundary can therefore differ; this is not a guarantee of
identical historical verdicts for every possible threshold. The committed green
and deliberately red demos retain their verdicts. No release tag is moved by
this fix, and historical release measurements are not rewritten.

`tests/test_stable_aggregation.py` exercises both the native interpreter and an
emulation of pre-3.12 built-in summation, pins public fixture cost values, and
checks overflow/unavailable behavior. The CI `report-reproducibility` job compares
all four demos' JSON, Markdown, and HTML report bytes plus the request plan
and synthetic binding-check receipt from the actual Python
3.11 and 3.13 jobs. Manifests are intentionally excluded because they contain
paths and timestamps. Missing artifacts fail the comparison.

This is evidence for the supported CI matrix, not a promise across every hardware
floating-point implementation: the Python documentation notes that some builds
can double-round an intermediate `math.fsum` addition. A new platform should run
the same report comparison before its hashes are treated as interchangeable.

References: [Python 3.12 sum change](https://docs.python.org/3.12/library/functions.html#sum)
and [math.fsum guarantees](https://docs.python.org/3.12/library/math.html#math.fsum).
