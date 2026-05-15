# System Knowledge Entry — Single Source of Truth

This is the ONLY knowledge entry point for the system.

All reasoning must start here.

====================================================
【ALLOWED KNOWLEDGE SOURCES】
====================================================

Primary (Always allowed)
- wiki/*
- memory/* (secondary validation only)

Approved Docs
- docs/decision_layer_v3_report.md

Data (when required)
- strategy_states_*.json
- active system code

====================================================
【BLOCKED BY DEFAULT】
====================================================

- root/*.md
- archive/*
- legacy/*
- *_report.md
- any file not explicitly listed above

====================================================
【KNOWLEDGE ROUTER】
====================================================

Use this mapping:

Strategy / validation / ranking
→ validation_gates.md

Decision / UI / display logic
→ governance.md

Stability / regime / pause-run decisions
→ stability_audit.md

Learning / feedback / rule weighting
→ feedback_loop.md

If task is unclear:
→ stay within README.md only

====================================================
【SOURCE OF TRUTH PRIORITY】
====================================================

1. governance.md
2. validation_gates.md
3. stability_audit.md
4. feedback_loop.md
5. approved docs

Anything else = NOT TRUSTED

====================================================
【CRITICAL RULE】
====================================================

Do NOT:
- search entire repo
- use historical reports
- rely on archive

If required info not found:
→ return "INSUFFICIENT TRUSTED DATA"

====================================================
【GOAL】
====================================================

Accuracy > completeness

The system must prefer correct partial answers
over complete incorrect answers.