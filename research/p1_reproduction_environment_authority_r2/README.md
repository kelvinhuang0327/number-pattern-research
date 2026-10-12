# P1 Reproduction Environment Authority R2

This isolated subproject supersedes only the nondeterministic raw `RECORD`
equality gate in R1. It preserves the exact R1 Python, lock, dependency,
approved-wheel, and platform authorities.

`RuntimeFingerprintV2` validates every installed `RECORD` as strict CSV,
normalizes every path within the target installation, rejects malformed or
escaping paths, verifies every declared included file hash and size, and
hashes canonical semantic rows. It excludes exactly the distribution's own
`RECORD` row and exact `.dist-info/uv_cache.json` row. No wildcard or package
payload exclusion exists.

The raw `RECORD` SHA-256 remains in the aggregate artifact as diagnostic
evidence. Environment equality is decided by exact Python/platform/lock
identity, expected distributions, approved wheel receipt hashes, `METADATA`
hashes, semantic `RECORD` hashes, and normalization-policy identity.

The committed package contains no database, wheel, virtual environment,
cache, interpreter, production change, or strategy result.
