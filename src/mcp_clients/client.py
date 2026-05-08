"""MCP stdio 세션 헬퍼 — 도메인 무관.

`mcp` Python SDK 가 설치돼 있으면 그걸 쓰고, 없으면 ImportError 를 호출부에서
잡아 fallback 으로 우회한다.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _open_session(launch: dict[str, Any]) -> AsyncIterator[Any]:
    """`launch={"command": ..., "args": [...], "env": {...}}` 로 stdio MCP 세션을 연다."""
    try:
        from mcp import ClientSession, StdioServerParameters  # type: ignore
        from mcp.client.stdio import stdio_client  # type: ignore
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "mcp Python SDK 미설치. requirements.txt 의 mcp>=1.0 을 설치하세요."
        ) from exc

    env = dict(os.environ)
    extra_env = launch.get("env") or {}
    env.update(extra_env)

    params = StdioServerParameters(
        command=str(launch["command"]),
        args=list(launch.get("args", [])),
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_available_tools(launch: dict[str, Any]) -> list[dict[str, Any]]:
    """`tools/list` 를 호출해 도구 목록을 반환."""
    async with _open_session(launch) as session:
        resp = await session.list_tools()
        out: list[dict[str, Any]] = []
        for tool in getattr(resp, "tools", []):
            out.append(
                {
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "inputSchema": getattr(tool, "inputSchema", None),
                }
            )
        return out


async def call_tool(
    launch: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
) -> Any:
    """단일 도구 호출 → 결과(JSON-serializable)를 반환."""
    async with _open_session(launch) as session:
        result = await session.call_tool(tool_name, args)
        # mcp SDK 의 CallToolResult.content 는 list[TextContent|...] 형태.
        contents = getattr(result, "content", None)
        if contents is None:
            return result
        merged: list[Any] = []
        for c in contents:
            text = getattr(c, "text", None)
            if text is None:
                merged.append(getattr(c, "data", str(c)))
                continue
            try:
                merged.append(json.loads(text))
            except (json.JSONDecodeError, TypeError):
                merged.append(text)
        if len(merged) == 1:
            return merged[0]
        return merged


def _print_tools(launch: dict[str, Any]) -> None:
    import asyncio

    tools = asyncio.run(list_available_tools(launch))
    json.dump(tools, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":  # pragma: no cover
    # `python -m src.mcp_clients.client --list` 로 KOREA_STOCK_MCP 도구명 출력
    import argparse

    from src.config import KOREA_STOCK_MCP

    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true")
    ns = p.parse_args()
    if ns.list:
        _print_tools(KOREA_STOCK_MCP)
