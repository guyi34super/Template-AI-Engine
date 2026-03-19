"""
Export Engine API routes.
Download results as XLSX/CSV/JSON/TXT or push to external databases.
Generates real files in output/api/ and streams them via FileResponse.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
import csv
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])

OUTPUT_DIR = Path("output/api")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store (mirrors to Redis when available)
_export_jobs: Dict[str, dict] = {}


# ===== Models =====
class DownloadRequest(BaseModel):
    document_id: str
    format: str = "xlsx"  # xlsx, csv, json, txt
    data: Optional[Dict[str, Any]] = None  # inline data override


class DatabasePushRequest(BaseModel):
    document_id: str
    db_type: str = "postgresql"
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    schema: str = "public"
    table: str


# ===== File generators =====
def _get_document_data(document_id: str, inline: dict | None) -> dict:
    """Try to load extraction data from the DB, fall back to inline or stub."""
    if inline:
        return inline
    # Try PostgreSQL
    try:
        from core.db import is_async_db, get_sync_session
        if is_async_db():
            from core.models import Document
            with get_sync_session() as session:
                doc = session.query(Document).filter(Document.id == document_id).first()
                if doc and doc.extracted_json:
                    return doc.extracted_json
    except Exception:
        pass
    # Try local file cache
    path = Path(f"output/json/{document_id}.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"_note": "no data found", "document_id": document_id}


def _generate_json(data: dict, dest: Path) -> None:
    dest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _generate_csv(data: dict, dest: Path) -> None:
    buf = io.StringIO()
    fields = list(data.keys()) if isinstance(data, dict) else ["key", "value"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    if isinstance(data, dict):
        writer.writerow({k: str(v) for k, v in data.items()})
    elif isinstance(data, list):
        for row in data:
            writer.writerow({k: str(v) for k, v in row.items()} if isinstance(row, dict) else {"key": str(row)})
    dest.write_text(buf.getvalue(), encoding="utf-8")


def _generate_txt(data: dict, dest: Path) -> None:
    lines = [f"{k}: {v}" for k, v in data.items()]
    dest.write_text("\n".join(lines), encoding="utf-8")


def _generate_xlsx(data: dict, dest: Path) -> None:
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Export"
        headers = list(data.keys()) if isinstance(data, dict) else ["key", "value"]
        ws.append(headers)
        if isinstance(data, dict):
            ws.append([str(v) for v in data.values()])
        elif isinstance(data, list):
            for row in data:
                ws.append([str(row.get(h, "")) for h in headers] if isinstance(row, dict) else [str(row)])
        wb.save(str(dest))
    except ImportError:
        # Fallback to CSV if openpyxl not available
        _generate_csv(data, dest.with_suffix(".csv"))


def _generate_pdf(data: dict, dest: Path) -> None:
    """Generate PDF export using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        doc = SimpleDocTemplate(str(dest), pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("AI-RAG Export Report", styles["Title"]))
        elements.append(Spacer(1, 12))

        # Data table
        if isinstance(data, dict):
            table_data = [["Field", "Value"]]
            for k, v in data.items():
                table_data.append([str(k), str(v)[:200]])  # Truncate long values
        elif isinstance(data, list) and data:
            headers = list(data[0].keys()) if isinstance(data[0], dict) else ["Value"]
            table_data = [headers]
            for row in data[:100]:  # Limit rows
                if isinstance(row, dict):
                    table_data.append([str(row.get(h, ""))[:100] for h in headers])
                else:
                    table_data.append([str(row)[:100]])
        else:
            table_data = [["Key", "Value"], ["data", str(data)[:500]]]

        table = Table(table_data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Footer
        from datetime import datetime, timezone
        elements.append(Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | AI-RAG Engine",
            styles["Italic"],
        ))

        doc.build(elements)
    except ImportError:
        # Fallback: generate a text file if reportlab is not installed
        logger.warning("reportlab not installed — falling back to TXT for PDF export")
        _generate_txt(data, dest.with_suffix(".txt"))


GENERATORS = {
    "json": (_generate_json, ".json", "application/json"),
    "csv": (_generate_csv, ".csv", "text/csv"),
    "txt": (_generate_txt, ".txt", "text/plain"),
    "xlsx": (_generate_xlsx, ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": (_generate_pdf, ".pdf", "application/pdf"),
}


# ===== Endpoints =====
@router.post("/download")
async def export_download(req: DownloadRequest):
    """Export validated data as XLSX / CSV / JSON / TXT — returns real file."""
    fmt = req.format.lower()
    if fmt not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}. Use: {list(GENERATORS.keys())}")

    job_id = str(uuid.uuid4())
    data = _get_document_data(req.document_id, req.data)
    gen_fn, ext, media = GENERATORS[fmt]
    dest = OUTPUT_DIR / f"{job_id}{ext}"

    try:
        gen_fn(data, dest)
    except Exception as exc:
        logger.error("Export generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"File generation failed: {exc}")

    _export_jobs[job_id] = {
        "id": job_id,
        "document_id": req.document_id,
        "format": fmt,
        "status": "complete",
        "file_path": str(dest),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Cache in Redis
    try:
        from core.redis_client import set_job_status
        import asyncio
        await set_job_status(job_id, _export_jobs[job_id])
    except Exception:
        pass

    return {
        "job_id": job_id,
        "status": "complete",
        "format": fmt,
        "message": f"Export ready in {fmt.upper()} format",
        "download_url": f"/export/jobs/{job_id}/file",
    }


@router.get("/jobs/{job_id}/file")
async def download_file(job_id: str):
    """Stream the generated export file."""
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    fpath = Path(job.get("file_path", ""))
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Export file missing")
    _, _, media = GENERATORS.get(job["format"], (None, None, "application/octet-stream"))
    return FileResponse(str(fpath), media_type=media, filename=fpath.name)


@router.post("/database", status_code=202)
async def export_to_database(req: DatabasePushRequest, background_tasks: BackgroundTasks):
    """Push validated data to a connected database (async background task)."""
    job_id = str(uuid.uuid4())
    _export_jobs[job_id] = {
        "id": job_id,
        "document_id": req.document_id,
        "format": "database",
        "status": "processing",
        "target": f"{req.db_type}://{req.host}:{req.port}/{req.database}",
        "table": req.table,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(_push_to_database, job_id, req)
    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"Pushing data to {req.db_type}://{req.host}:{req.port}/{req.database}.{req.table}",
    }


async def _push_to_database(job_id: str, req: DatabasePushRequest) -> None:
    """Background task — push data to external database."""
    import asyncio
    try:
        data = _get_document_data(req.document_id, None)
        # Build connection string and push
        if req.db_type == "postgresql":
            try:
                import asyncpg
                conn = await asyncpg.connect(
                    host=req.host, port=req.port, database=req.database,
                    user=req.username, password=req.password,
                )
                # Auto-create table with text columns
                cols = list(data.keys())
                create_sql = f'CREATE TABLE IF NOT EXISTS "{req.schema}"."{req.table}" (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")"
                await conn.execute(create_sql)
                placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
                insert_sql = f'INSERT INTO "{req.schema}"."{req.table}" ({", ".join(f"{c}" for c in cols)}) VALUES ({placeholders})'
                await conn.execute(insert_sql, *[str(data.get(c, "")) for c in cols])
                await conn.close()
            except ImportError:
                raise RuntimeError("asyncpg not installed")

        _export_jobs[job_id]["status"] = "complete"
        _export_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.error("Database push failed for job %s: %s", job_id, exc)
        _export_jobs[job_id]["status"] = "failed"
        _export_jobs[job_id]["error"] = str(exc)


@router.get("/jobs/{job_id}")
async def get_export_job(job_id: str):
    """Poll export job status."""
    job = _export_jobs.get(job_id)
    if not job:
        # Try Redis
        try:
            from core.redis_client import get_job_status
            job = await get_job_status(job_id)
        except Exception:
            pass
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job
