"""Export the FastAPI OpenAPI schema to openapi.json.

Usage:
    python scripts/export_openapi.py

This is used by the TypeScript type generation pipeline:
    1. python scripts/export_openapi.py          # produces openapi.json
    2. npx openapi-typescript openapi.json -o frontend-types.ts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402


def main() -> None:
    app = create_app()
    schema = app.openapi()
    out_path = Path(__file__).resolve().parent.parent / "openapi.json"
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] OpenAPI schema exported to {out_path}")
    print(f"     Paths: {len(schema.get('paths', {}))}")
    print(f"     Schemas: {len(schema.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()