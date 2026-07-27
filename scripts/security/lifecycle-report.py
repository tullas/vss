#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
today = dt.datetime.now(dt.timezone.utc).date()
components = json.loads((root / "security/components.yml").read_text(encoding="utf-8"))["components"]
exceptions = json.loads((root / "security/exceptions.yml").read_text(encoding="utf-8"))["exceptions"]
stale = []
for item in components:
    reviewed = dt.date.fromisoformat(item["review_date"])
    if (today - reviewed).days > 180:
        stale.append({"component": item["id"], "days_since_review": (today - reviewed).days})
expiring = []
for item in exceptions:
    expiry = dt.date.fromisoformat(item["expiry_date"])
    if (expiry - today).days <= 30:
        expiring.append({"exception": item["id"], "days_to_expiry": (expiry - today).days})
print(json.dumps({"schema_version": "1.0", "generated_date": today.isoformat(), "stale_component_reviews": stale, "expiring_exceptions": expiring, "external_reports": ["pip-audit results", "GitHub security workflow conclusions", "Dependabot security/update PR queue"]}, indent=2, sort_keys=True))
