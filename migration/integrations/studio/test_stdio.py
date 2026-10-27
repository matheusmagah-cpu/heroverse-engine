"""Real MCP subprocess smoke test; no Studio requests and no real cookies."""
import asyncio
import json
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters

SYNTHETIC = "SID=SYNTHETIC-sid-only-for-stdio"   # no SAPISID: refused locally before any request


class Stdio(unittest.TestCase):
    def test_four_read_only_tools_and_local_refusals_without_network(self):
        async def run():
            for cookies, code in (("", "STUDIO_COOKIES_MISSING"), (SYNTHETIC, "STUDIO_COOKIES_INVALID")):
                params = StdioServerParameters(command=sys.executable,
                                               args=[str(Path(__file__).with_name("server.py"))],
                                               env={"YT_STUDIO_COOKIES": cookies})
                async with Client(params) as session:
                    listed = await session.list_tools()
                    self.assertEqual({t.name for t in listed.tools},
                                     {"studio_status", "studio_video_metrics", "studio_channel_metrics",
                                      "studio_retention"})
                    for tool in listed.tools:
                        self.assertTrue(tool.annotations.read_only_hint, tool.name)
                        self.assertFalse(tool.annotations.destructive_hint, tool.name)
                        self.assertFalse({"url", "path", "body", "endpoint"} & set(tool.input_schema["properties"]))
                    status = await session.call_tool("studio_status", {})
                    self.assertFalse(status.is_error)
                    data = json.loads(status.content[0].text)
                    self.assertEqual(data["error"], code)
                    self.assertFalse(data["session_verified"])
                    for name, args in (("studio_video_metrics", {"video_id": "abcdefghijk"}),
                                       ("studio_channel_metrics", {}), ("studio_retention", {"video_id": "abcdefghijk"})):
                        result = await session.call_tool(name, args)
                        self.assertTrue(result.is_error)
                        self.assertIn(code, result.content[0].text)
                        self.assertNotIn("SYNTHETIC", result.content[0].text)
                    bad = await session.call_tool("studio_video_metrics", {"video_id": "../x"})
                    self.assertTrue(bad.is_error)
                    self.assertIn("INVALID_VIDEO_ID", bad.content[0].text)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
