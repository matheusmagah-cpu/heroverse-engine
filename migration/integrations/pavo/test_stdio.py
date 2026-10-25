"""Real MCP subprocess smoke test; no Pavo requests and no real credentials."""
import asyncio
import json
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters


class Stdio(unittest.TestCase):
    def test_protocol_tools_and_local_brief_without_network(self):
        async def run():
            params = StdioServerParameters(command=sys.executable,
                                           args=[str(Path(__file__).with_name("server.py"))],
                                           env={"PAVO_TOKEN": ""})
            async with Client(params) as session:
                listed = await session.list_tools()
                self.assertEqual({t.name for t in listed.tools},
                                 {"pavo_status", "pavo_account", "pavo_models", "pavo_prepare_video",
                                  "pavo_quote_video", "pavo_generate_video", "pavo_job"})
                for tool in listed.tools:
                    self.assertEqual(tool.annotations.read_only_hint, tool.name != "pavo_generate_video")
                generator = next(t for t in listed.tools if t.name == "pavo_generate_video")
                self.assertFalse(generator.annotations.idempotent_hint)
                status = await session.call_tool("pavo_status", {})
                self.assertFalse(status.is_error)
                status_data = json.loads(status.content[0].text)
                self.assertFalse(status_data["credential_configured"])
                self.assertFalse(status_data["generation_enabled"])
                account = await session.call_tool("pavo_account", {})
                self.assertTrue(account.is_error)
                self.assertIn("PAVO_CREDENTIAL_REQUIRED", account.content[0].text)
                quote = await session.call_tool("pavo_quote_video", {})
                self.assertTrue(quote.is_error)
                self.assertIn("PAVO_CREDENTIAL_REQUIRED", quote.content[0].text)
                brief = await session.call_tool("pavo_prepare_video", {"prompt": "Sunlight over a river."})
                brief_data = json.loads(brief.content[0].text)
                self.assertTrue(brief_data["prepared"])
                self.assertFalse(brief_data["submitted"])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
