#!/usr/bin/env python3
"""Generate a minimal CycloneDX SBOM (JSON) from pip list JSON (sbom/pip-sbom.json).

Writes output to `sbom/cyclonedx-bom.json`.
"""
import json
import os
from datetime import datetime


def main():
    sbom_dir = os.path.join(os.path.dirname(__file__), '..', 'sbom')
    pip_sbom_path = os.path.join(sbom_dir, 'pip-sbom.json')
    out_path = os.path.join(sbom_dir, 'cyclonedx-bom.json')

    if not os.path.exists(pip_sbom_path):
        print(f"Input SBOM not found: {pip_sbom_path}")
        return 1

    with open(pip_sbom_path, 'r', encoding='utf-8') as f:
        pkgs = json.load(f)

    components = []
    for p in pkgs:
        comp = {
            "type": "library",
            "name": p.get('name'),
            "version": p.get('version')
        }
        components.append(comp)

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{datetime.utcnow().isoformat()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tools": [{"vendor": "local", "name": "generate_cyclonedx_sbom.py", "version": "1"}]
        },
        "components": components,
    }

    os.makedirs(sbom_dir, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(bom, f, indent=2, ensure_ascii=False)

    print(f"Wrote CycloneDX SBOM to {out_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
