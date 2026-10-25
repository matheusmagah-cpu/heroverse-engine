# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==2.3.0"]
# ///
"""Private stdio MCP for the owner's Pavo account; generation is limited to fresh exact zero-credit quotes."""
import logging
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from client import PavoError
from video import PavoVideoClient

mcp = MCPServer("heroverse-pavo", version="0.3.0", log_level="CRITICAL",
                instructions="Unofficial Pavo connection. Generate only with a fresh exact zero-credit quote. "
                             "Never retry an uncertain submission; check its conversation_id with pavo_job.")
client = PavoVideoClient()
read = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
local = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
write = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)


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


@mcp.tool(annotations=read)
def pavo_quote_video(seconds: int = 5, aspect_ratio: str = "9:16", first_frame: str = "", last_frame: str = "",
                     references: list[str] | None = None) -> dict:
    """Quote one Flash video, 720p, no audio, with its input images counted. Never generate or treat the quote
    as permanent pricing. Images are repository paths (PNG/JPEG): first_frame (+ optional last_frame), or up to
    5 references (same characters every time); frames and references are exclusive."""
    return safe_call(client.quote_video, seconds, aspect_ratio, first_frame, last_frame, references)


@mcp.tool(annotations=write)
def pavo_generate_video(prompt: str, seconds: int = 5, aspect_ratio: str = "9:16", first_frame: str = "",
                        last_frame: str = "", references: list[str] | None = None) -> dict:
    """Start one private Flash video only at a fresh exact zero-credit quote (input images counted). Text only,
    first_frame (+ optional last_frame) or up to 5 references, as repository image paths. Never retry
    automatically."""
    return safe_call(client.generate_video, prompt, seconds, aspect_ratio, first_frame, last_frame, references)


@mcp.tool(annotations=read)
def pavo_job(conversation_id: str) -> dict:
    """Read a previously submitted job. An uncertain submission must be checked here before any new one."""
    return safe_call(client.job, conversation_id)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    mcp.run()
