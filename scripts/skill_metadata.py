"""Shared version metadata for the robust preview workflow."""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
SKILL_VERSION = (_ROOT / "VERSION").read_text(encoding="utf-8-sig").strip() or "v0.4.0"
COLLECTOR_VERSION = "inapp-v049-hotfix1-answer-rescue-segments"
REPORT_VERSION = "weekly-dashboard-v049-hotfix2-display-cleanup"
