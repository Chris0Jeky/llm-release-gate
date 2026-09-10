# Complete acceleration bundle archive

The complete generated artifact set is stored as nine base64 shards because it includes a self-contained interactive HTML deck and several large machine-readable catalogs.

`assemble_bundle.py` concatenates the shards in lexical order, decodes them, verifies the SHA-256 digest, and writes `llm-release-gate-acceleration-bundle.tar.xz`.

```bash
python assemble_bundle.py
python assemble_bundle.py --extract
```

Expected archive:

- decoded bytes: `62888`
- SHA-256: `45b62b48a55701a7f642e6398fb1348191874b938f082cab5448dae28abd888e`

The archive contains the original comprehensive review, interactive decision deck, decision catalog and the self-contained acceleration bundle. Extraction never overwrites an existing destination unless `--force` is supplied.
