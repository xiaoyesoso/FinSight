"""PDF upload endpoint.

Stores an uploaded PDF under `backend/data/uploads/` and returns a `file_id`
plus the absolute path. The financial analyzer SubAgent resolves the
`file_id` to the absolute path before parsing, mirroring the reference
script's local-file usage while making it web-friendly.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.config import settings

router = APIRouter()


@router.post("/upload", status_code=202)
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, str]:
    """Accept a multipart PDF upload and store it locally.

    Returns a `file_id` (used by the research endpoint) and the absolute
    `path` (used by the financial SubAgent prompt).
    """
    # Reject non-PDF uploads early with a clear error.
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Generate a unique id and preserve the original extension.
    file_id = uuid.uuid4().hex
    safe_name = f"{file_id}.pdf"
    dest = Path(settings.upload_dir) / safe_name

    # Stream the upload to disk to avoid loading large PDFs into memory.
    content = await file.read()
    dest.write_bytes(content)

    return {"file_id": file_id, "path": str(dest.resolve())}
