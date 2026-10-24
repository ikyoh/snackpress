"""Short-lived preview inputs and isolated, replaceable render generations."""

import asyncio
import json
import os
import shutil
from contextlib import suppress
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from snackpress_imposition.geometry import Settings
from snackpress_tools.catalog import CATALOG, MODELS, ToolResult
from sqlalchemy.orm import Session

from .database import Job
from .tools import service, stage_files

router = APIRouter(tags=["previews"])
PREVIEW_TTL = timedelta(minutes=30)


class PreviewSession(BaseModel):
    id: str


class PreviewSettings(BaseModel):
    settings: dict = Field(default_factory=dict)


class PreviewResult(ToolResult):
    generation: str
    notice: str


def preview_job(preview_id: str):
    svc = service()
    with Session(svc.engine) as db:
        job = db.get(Job, preview_id)
        if not job or job.created_at < datetime.now() - PREVIEW_TTL:
            raise HTTPException(404, "Aperçu expiré. Actualisez l’aperçu pour le recréer.")
        info = json.loads(job.info)
        if not info.get("preview"):
            raise HTTPException(404, "Aperçu introuvable.")
        return info


async def disconnected_worker(request: Request, action: str, folder):
    svc = service()
    task = asyncio.create_task(svc.worker(action, folder))

    async def watch():
        while not await request.is_disconnected():
            await asyncio.sleep(0.15)

    watcher = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait([task, watcher], return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return task.result()
        raise HTTPException(499, "Actualisation de l’aperçu annulée.")
    finally:
        for pending in (task, watcher):
            if not pending.done():
                pending.cancel()
            with suppress(asyncio.CancelledError, HTTPException):
                await pending


@router.post("/api/tools/{tool_id}/previews", response_model=PreviewSession, status_code=201)
async def create_preview(
    tool_id: str,
    request: Request,
    files: list[UploadFile] = File(default=[]),
    source_job_id: str = Form(""),
):
    svc = service()
    if tool_id not in CATALOG and tool_id != "imposition":
        raise HTTPException(404, "Outil inconnu.")
    definition = CATALOG.get(tool_id)
    min_files, max_files = (definition.min_files, definition.max_files) if definition else (1, 1)
    count = 1 if tool_id == "imposition" and source_job_id else len(files)
    if not min_files <= count <= max_files:
        raise HTTPException(422, "Importez les fichiers requis pour afficher l’aperçu.")
    svc.purge()
    if sum(p.is_dir() and p.name != "mail-outbox" for p in svc.DATA.iterdir()) >= 100:
        raise HTTPException(429, "Limite de travaux atteinte. Supprimez des travaux.")
    preview_id = uuid4().hex
    folder = svc.DATA / preview_id
    folder.mkdir(mode=0o700)
    svc.busy.add(preview_id)
    try:
        if tool_id == "imposition" and source_job_id:
            svc.get_job(source_job_id)
            inputs = ["input-0.pdf"]
            os.link(svc.DATA / source_job_id / "source.pdf", folder / inputs[0])
        else:
            inputs = await stage_files(folder, files, tool_id)
        if await request.is_disconnected():
            raise HTTPException(499, "Import de l’aperçu annulé.")
        with Session(svc.engine) as db:
            db.add(
                Job(
                    id=preview_id,
                    name="Aperçu",
                    created_at=datetime.now(),
                    status="preview",
                    info=json.dumps({"tool": tool_id, "preview": True, "inputs": inputs}),
                )
            )
            db.commit()
        return PreviewSession(id=preview_id)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        svc.busy.discard(preview_id)
        for upload in files:
            await upload.close()


@router.post("/api/tool-previews/{preview_id}/render", response_model=PreviewResult)
async def render_preview(preview_id: str, data: PreviewSettings, request: Request):
    svc = service()
    info = preview_job(preview_id)
    if preview_id in svc.busy:
        raise HTTPException(409, "L’aperçu précédent se termine. Réessayez dans un instant.")
    limit = 2 * 1024 * 1024 if info["tool"] == "fortune-cookie" else 65536
    if len(json.dumps(data.settings, ensure_ascii=False).encode("utf-8")) > limit:
        raise HTTPException(413, "Réglages trop volumineux.")
    try:
        model = Settings if info["tool"] == "imposition" else MODELS[info["tool"]]
        params = model.model_validate(data.settings)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(e["msg"] for e in exc.errors())) from None
    svc.busy.add(preview_id)
    generation = uuid4().hex
    root = svc.DATA / preview_id
    folder = root / generation
    folder.mkdir(mode=0o700)
    try:
        (folder / "tool-request.json").write_text(
            json.dumps(
                {
                    "tool": info["tool"],
                    "settings": params.model_dump(),
                    "files": [str(root / name) for name in info["inputs"]],
                }
            )
        )
        result = ToolResult.model_validate(
            await disconnected_worker(request, "tool-preview", folder)
        )
        result.id = preview_id
        result.artifacts = [
            a for a in result.artifacts if a.media_type in {"application/pdf", "image/png"}
        ]
        result_path = folder / "result.json"
        result_path.write_text(result.model_dump_json())
        # Keep the previous renders long enough for in-flight PDF.js reads.
        generations = sorted(
            (p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for old in generations[3:]:
            shutil.rmtree(old, ignore_errors=True)
        with Session(svc.engine) as db:
            db.get(Job, preview_id).created_at = datetime.now()
            db.commit()
        notices = {
            "imposition": (
                "Aperçu PDF de contrôle ; le format reste à confirmer avant l’export final."
            ),
            "fortune-cookie": (
                "Aperçu limité aux deux premiers exemplaires. "
                "Affichage au format fini, sans fonds perdus. "
                "Le fichier final contient toute la série avec les fonds perdus."
            ),
        }
        notice = notices.get(
            info["tool"], "Aperçu de contrôle. Générez le fichier final pour le télécharger."
        )
        if info["tool"] == "fortune-cookie":
            if params.layer_template:
                notice += " L’imposition en souches est générée uniquement pour le téléchargement."
            if params.pizza_template:
                notice += " Les repères Pizza sont visibles uniquement dans l’aperçu de placement."
        if info["tool"] in {"donut", "tiramisu", "poke"}:
            notice = (
                "Aperçu réduit : deux premières pages, 96 dpi maximum. "
                "Les mesures de cet aperçu ne remplacent pas le contrôle du fichier final."
            )
        return PreviewResult(**result.model_dump(), generation=generation, notice=notice)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        svc.busy.discard(preview_id)


@router.get("/api/tool-previews/{preview_id}/{generation}/files/{name}")
def preview_file(preview_id: str, generation: str, name: str):
    preview_job(preview_id)
    # Only server-issued generation IDs and artifact allowlists can select a file.
    if len(generation) != 32 or any(c not in "0123456789abcdef" for c in generation):
        raise HTTPException(404, "Aperçu introuvable.")
    folder = service().DATA / preview_id / generation
    path = folder / "result.json"
    if not path.is_file():
        raise HTTPException(404, "Aperçu remplacé. Actualisez l’aperçu.")
    result = ToolResult.model_validate_json(path.read_text())
    item = next((a for a in result.artifacts if a.name == name), None)
    if item is None:
        raise HTTPException(404, "Fichier d’aperçu introuvable.")
    return FileResponse(
        folder / item.name,
        media_type=item.media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/api/tool-previews/{preview_id}", status_code=204)
def delete_preview(preview_id: str):
    preview_job(preview_id)
    svc = service()
    if preview_id in svc.busy:
        raise HTTPException(409, "Attendez la fin de l’aperçu avant sa suppression.")
    with Session(svc.engine) as db:
        db.delete(db.get(Job, preview_id))
        db.commit()
    shutil.rmtree(svc.DATA / preview_id, ignore_errors=True)
