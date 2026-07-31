# P1 Reproduction Environment Authority R3

This isolated subproject supersedes only the path-dependent console-script
launcher acceptance in R2. It preserves R1 and R2's exact Python, lock,
dependency, approved-wheel, platform, and non-launcher SemanticRecordV1
authorities unchanged.

Every launcher uv generates for an installed `console_scripts` entry point
embeds the resolved absolute installation-root interpreter path. R2 hashed
those launcher bytes as ordinary RECORD payload, so its RuntimeFingerprintV2
was location-dependent for any distribution declaring a console script.

`LauncherNormalizationPolicyV2` discovers launchers only from each
distribution's own declared `console_scripts` entry points, requires an exact
one-to-one mapping between declared entries and installed launchers, and maps
the approved uv Python-shebang and shell-trampoline bootstraps to one canonical
semantic prefix before hashing. `ConsoleScriptSemanticV2` records
`launcher_type: uv_console_script` while preserving every non-bootstrap Python
payload byte. Raw template type, hash, and size are retained diagnostically.

`RuntimeFingerprintV3` retains every R2 acceptance-critical field for
non-launcher content and adds the launcher-normalization policy identity and
the console-script semantic set identity. Three fresh offline installs at
materially different absolute path lengths produce different raw launcher
bytes and byte-identical RuntimeFingerprintV3 documents.

`runtime_fingerprint.schema.json` validates only semantic console-script
fields. Raw launcher hash and size observations remain diagnostic-only in
`launcher_raw_diagnostics.json`.

The mandatory regeneration acceptance command is recorded in
`installation_recipe.json`; it supplies the runtime root directly and cannot
silently skip. General Replay Governance CI does not replace this focused R3
acceptance.

The committed package contains no database, wheel, virtual environment,
cache, interpreter, production change, or strategy result.
