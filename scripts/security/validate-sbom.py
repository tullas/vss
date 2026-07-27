#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("sbom", type=Path)
args = parser.parse_args()
try:
    value = json.loads(args.sbom.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit("SBOM is not valid JSON")
if value.get("bomFormat") != "CycloneDX" or value.get("specVersion") != "1.6":
    raise SystemExit("SBOM is not CycloneDX 1.6")
components = value.get("components")
if not isinstance(components, list) or not components:
    raise SystemExit("SBOM has no components")
ecosystems = {prop["value"] for item in components for prop in item.get("properties", []) if prop.get("name") == "vss:ecosystem"}
if not {"github-action", "oci", "opentofu-provider", "apt"}.issubset(ecosystems):
    raise SystemExit("SBOM omits a required external-input class")
if not any(str(item.get("purl", "")).startswith("pkg:pypi/") for item in components):
    raise SystemExit("SBOM omits Python packages")
encoded = json.dumps(value)
if re.search(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,}]+", encoded):
    raise SystemExit("SBOM contains sensitive-looking content")
print(json.dumps({"status": "valid", "format": "CycloneDX", "components": len(components)}, sort_keys=True))
