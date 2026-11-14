"""Contract test (A7): fails CI when any MCP tool's name, inputs, outputs or annotations
change by accident. If the change is intended, run `make snapshot` and commit the new file."""
import asyncio
import json

from mcp_servers.describe import SNAPSHOT, collect


def test_tool_schemas_match_the_snapshot():
    live = json.loads(json.dumps(asyncio.run(collect()), sort_keys=True))
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    changed = sorted(k for k in live.keys() | saved.keys() if live.get(k) != saved.get(k))
    assert not changed, f"tool schemas changed: {changed}. If intended, run `make snapshot`."
