# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==2.3.0"]
# ///
"""Private stdio MCP that READS the owner's YouTube Studio analytics with the owner's Studio session cookies.

Unofficial and read-only by construction: studio_client.guard() allows only fixed read endpoints on
studio.youtube.com; there is no raw-request tool. The cookies come only from the host environment (YT_STUDIO_COOKIES).
"""
import logging
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from studio_client import StudioClient, StudioError

mcp = MCPServer("heroverse-studio", version="0.1.0", log_level="CRITICAL",
                instructions="Unofficial, read-only YouTube Studio analytics of the owner's channel. Paced (>= 2.5 s "
                             "between requests, 40 per session). Responses are private: never copy them into public "
                             "logs, receipts or evidence. Dates are YYYY-MM-DD (UTC days) or start='lifetime'.")
client = StudioClient()
read = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)


def safe_call(method, *args):
    message = "STUDIO_INTERNAL_ERROR"
    try:
        return method(*args)
    except StudioError as exc:
        message = client.scrub(str(exc))
    except Exception:
        pass
    raise ToolError(message)   # outside the except block: the original exception is not chained


@mcp.tool(annotations=read)
def studio_status(verify: bool = True) -> dict:
    """Is YT_STUDIO_COOKIES present and parseable, and (verify=true, 2 paced requests on first use) does it open
    Studio: channel id, title, subscribers. Never returns any cookie value."""
    return safe_call(client.status, verify)


@mcp.tool(annotations=read)
def studio_video_metrics(video_id: str, start: str = "", end: str = "") -> dict:
    """One video's Studio analytics for a period: impressions, impressions CTR, views, unique viewers, average view
    duration and percentage, subscribers gained, watch time, traffic sources (4 paced requests). start/end are
    YYYY-MM-DD (inclusive, at most 366 days; both empty = the last 28 full days) or start='lifetime'."""
    return safe_call(client.video_metrics, video_id, start, end)


@mcp.tool(annotations=read)
def studio_channel_metrics(start: str = "", end: str = "", limit: int = 10, per_video: int = 3) -> dict:
    """Channel totals for a period (overview + reach), traffic sources, and a ranked table of the latest `limit`
    uploads (1-50) with the period's reach metrics for the top `per_video` (0-5, one request each)."""
    return safe_call(client.channel_metrics, start, end, limit, per_video)


@mcp.tool(annotations=read)
def studio_retention(video_id: str, start: str = "lifetime", end: str = "") -> dict:
    """A video's audience-retention curve and engagement key metrics (1 paced request)."""
    return safe_call(client.retention, video_id, start, end)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    mcp.run()
