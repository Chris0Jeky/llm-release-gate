# Field-match scorer v3

The field-match scorer now checks key presence independently of value equality.
Previously, looking up an absent key returned the string `<missing>`; an expected
value with that exact spelling therefore passed even when the field was absent.
The reproduced end-to-end extraction gate now fails instead of returning green.

An absent key is reported as `KEY: field is <missing>`, not as a received JSON
string. A present field whose value really is `<missing>` still passes when that
is expected. Explicit null is distinct from absence, and recursive JSON-strict
boolean/number comparisons are unchanged. Missing fields are scoring failures,
not provider failures; the sample counts and `errors.error_rate` retain that
meaning. Empty and Unicode key names use the same presence check.

This semantic repair increments the scorer identity from version `2` to `3`.
Consequently, reports that include field-match have new content hashes, even when
their verdict is unchanged. The current extraction demo still passes; its new
result hash is:

`sha256:7fae5b8813cd6a91bb900eba7dbde3d59a507bf89bddda0a1ff1ac41760fa024`

The rag, deliberate-regression and request-bound examples do not use field-match;
their report hashes and verdicts remain unchanged. Historical hashes in dated
release receipts describe those releases and must not be rewritten. This repair
is on unreleased main and does not move any release tag or change the report
schema, threshold policy, runtime dependencies or provider support.

`tests/test_field_presence.py` covers literal-marker presence/absence, empty and
Unicode keys, null/type distinctions, plain and fenced built-in extraction paths,
and the scorer version. Six tests failed on the prior implementation, with seven
compatibility controls passing. The full integrated suite passed 669 tests and
all four demo/bundle checks after the repair.
