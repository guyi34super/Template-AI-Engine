"""
WebSocket endpoint — real-time extraction progress (Section 6.4).

Client connects to  ws://<host>/ws/extract/{job_id}
Server pushes JSON frames:
  {"stage": "ocr", "progress": 0.35, "message": "Processing page 3/8"}
  {"stage": "complete", "progress": 1.0, "data": {...}}
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.redis_client import get_job_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Active connections keyed by job_id
_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/extract/{job_id}")
async def extraction_progress(websocket: WebSocket, job_id: str):
    """Stream extraction progress for a given job via WebSocket."""
    await websocket.accept()
    _connections.setdefault(job_id, []).append(websocket)
    logger.info("WS client connected for job %s", job_id)

    try:
        while True:
            # Poll job status from Redis every second
            status = await get_job_status(job_id)
            if status:
                await websocket.send_json(status)
                if status.get("stage") in ("complete", "failed", "error"):
                    break
            else:
                await websocket.send_json({"stage": "waiting", "progress": 0, "message": "Job not started yet"})
            # Also listen for client messages (e.g. cancel)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if data == "cancel":
                    await websocket.send_json({"stage": "cancelled", "progress": 0})
                    break
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        logger.info("WS client disconnected for job %s", job_id)
    finally:
        _connections.get(job_id, []).remove(websocket) if websocket in _connections.get(job_id, []) else None


async def broadcast_progress(job_id: str, payload: dict) -> None:
    """Push a progress update to all clients watching a job."""
    sockets = _connections.get(job_id, [])
    dead: list[WebSocket] = []
    for ws in sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)
