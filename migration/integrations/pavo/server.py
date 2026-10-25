# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==2.3.0"]
# ///
"""Private stdio MCP for the owner's Pavo account; generation remains unqualified."""
import logging
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from client import PavoClient, PavoError

mcp = MCPServer("heroverse-pavo", version="0.1.0", log_level="CRITICAL",
                instructions="Unofficial Pavo connection. Video briefs are never submitted. "
                             "Do not treat a free label or paid subscription as a verified generation price.")
client = PavoClient()
read = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
local = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def safe_call(method, *args):
    try:
        return method(*args)
    except PavoError as exc:
        raise ToolError(str(exc)) from None
    except Exception:
        raise ToolError("PAVO_INTERNAL_ERROR") from None


@mcp.tool(annotations=local)
def pavo_status() -> dict:
    """Inspect configuration without network access. Configured does not mean authenticated."""
    return client.status()


@mcp.tool(annotations=read)
def pavo_account() -> dict:
    """Read the existing subscription label and credits. Never buy, renew or upgrade."""
    return safe_call(client.account)


@mcp.tool(annotations=read)
def pavo_models() -> dict:
    """Read the public video model catalog. Free labels do not verify the current request price."""
    return safe_call(client.models)


@mcp.tool(annotations=local)
def pavo_prepare_video(prompt: str, seconds: int = 5, aspect_ratio: str = "9:16") -> dict:
    """Prepare a local creative brief only. No video is submitted, generated, scheduled or published."""
    return safe_call(client.prepare_video, prompt, seconds, aspect_ratio)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    mcp.run()
