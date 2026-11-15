"""Write the API's OpenAPI schema to apps/web/openapi.json, the input of the generated TypeScript client.

    uv run python -m apps.api.openapi        then, in apps/web:  npm run gen:api
"""
import json
from pathlib import Path

from apps.api.main import app

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "web" / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=1) + "\n", encoding="utf-8")
    print("wrote", out)
