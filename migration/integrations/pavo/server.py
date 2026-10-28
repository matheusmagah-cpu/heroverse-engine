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
from image_gen import PavoImageClient
from quota import QuotaGuard, git_actions_usage

mcp = MCPServer("heroverse-pavo", version="0.6.0", log_level="CRITICAL",
                instructions="Unofficial Pavo connection. Generate only with a fresh exact zero-credit quote. "
                             "Never retry an uncertain submission; check its conversation_id with pavo_job.")
# E124/E128: one free-model budget for stills and videos, with today's shot-probe runs (their records on the local
# origin/claude/shot-probe-* refs) counted in
client = PavoImageClient(guard=QuotaGuard(actions=git_actions_usage))
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
                     references: list[str] | None = None, audios: list[str] | None = None,
                     sound: bool = False) -> dict:
    """Quote one Flash video, 720p, with its input images and audios and the sound flag counted. Never generate
    or treat the quote as permanent pricing. Images are repository paths (PNG/JPEG): first_frame (+ optional
    last_frame), or up to 5 references (same characters every time); frames and references are exclusive.
    audios: up to 3 repository .mp3/.wav paths (our narration, each and in total 2-12 s), only with references.
    sound: ask for generated sound (default false)."""
    return safe_call(client.quote_video, seconds, aspect_ratio, first_frame, last_frame, references, audios, sound)


@mcp.tool(annotations=write)
def pavo_generate_video(prompt: str, seconds: int = 5, aspect_ratio: str = "9:16", first_frame: str = "",
                        last_frame: str = "", references: list[str] | None = None, audios: list[str] | None = None,
                        sound: bool = False) -> dict:
    """Start one private Flash video only at a fresh exact zero-credit quote (input images, audios and sound
    counted). Text only, first_frame (+ optional last_frame) or up to 5 references, as repository image paths;
    audios (up to 3 .mp3/.wav, 2-12 s in total) only with references. A nonzero quote refuses and reports the
    quoted number. Counted in the shared free-model budget (E128: a video spends 2 units, a still 1; refused with
    PAVO_DAILY_CAP / PAVO_FREE_QUOTA_SUSPECTED before any request). Never retry automatically."""
    return safe_call(client.generate_video, prompt, seconds, aspect_ratio, first_frame, last_frame, references,
                     audios, sound)


@mcp.tool(annotations=read)
def pavo_job(conversation_id: str) -> dict:
    """Read a previously submitted job. An uncertain submission must be checked here before any new one."""
    return safe_call(client.job, conversation_id)


@mcp.tool(annotations=read)
def pavo_quote_image(aspect_ratio: str = "9:16", resolution: str = "sd", references: list[str] | None = None) -> dict:
    """Quote one Agnes Image 2.5 Flash still (agnes-image, the only free image model) with its reference images
    counted. Never generate or treat the quote as permanent pricing. resolution: sd (1K), hd (2K) or uhd (4K);
    references: up to 6 repository image paths (PNG/JPEG)."""
    return safe_call(client.quote_image, aspect_ratio, resolution, references)


@mcp.tool(annotations=write)
def pavo_generate_image(prompt: str, aspect_ratio: str = "9:16", resolution: str = "sd",
                        references: list[str] | None = None) -> dict:
    """Start one private Agnes Image 2.5 Flash still only at a fresh exact zero-credit quote (references counted).
    No other image model is ever used. A nonzero quote refuses and reports the quoted number. Never retry
    automatically; read the result with pavo_image_job."""
    return safe_call(client.generate_image, prompt, aspect_ratio, resolution, references)


@mcp.tool(annotations=read)
def pavo_image_job(conversation_id: str) -> dict:
    """Read a previously submitted still and its image URLs. An uncertain submission is checked here, never resent."""
    return safe_call(client.image_job, conversation_id)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    mcp.run()
