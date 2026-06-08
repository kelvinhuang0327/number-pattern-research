"""Read-only research subpackage (non-production).

Modules here are research scaffolding only. They must never be imported by the
production app at startup, must never write the DB, and must never enter
recommendation / registry / controlled_apply / deployment paths.
"""
