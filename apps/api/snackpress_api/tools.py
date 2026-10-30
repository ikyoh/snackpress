import json
import shutil
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from snackpress_tools.catalog import CATALOG, DEFINITIONS, MODELS, ToolDefinition, ToolResult
from sqlalchemy.orm import Session

from .database import Job

router = APIRouter()


@router.get("/api/tools", response_model=list[ToolDefinition])
def catalog():
    return DEFINITIONS


def service():
    # Resolve at request time so app factories/tests can replace the data directory safely.
    from . import main

    return main


async def stage_files(folder, files, tool_id):
    svc = service()
    total = 0
    inputs = []
    for index, upload in enumerate(files):
        size = 0
        tmp = folder / f"input-{index}.tmp"
        with tmp.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                size += len(chunk)
                if size > svc.MAX_BYTES or total > 50 * 1024 * 1024:
                    raise HTTPException(413, "Limite : 25 Mo par fichier, 50 Mo au total.")
                output.write(chunk)
        with tmp.open("rb") as source:
            head = source.read(1024).lstrip()
        if head.startswith(b"%PDF-"):
            suffix = ".pdf"
        elif tool_id in {"donut", "granola", "biscuit"} and head.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix = ".png"
        elif tool_id in {"donut", "granola", "biscuit"} and head.startswith(b"\xff\xd8\xff"):
            suffix = ".jpg"
        elif tool_id == "biscuit" and (head.startswith(b"<svg") or head.startswith(b"<?xml")):
            suffix = ".svg"
        else:
            raise HTTPException(
                422,
                "Fichier non reconnu. Importez un PDF, PNG, JPEG ou SVG."
                if tool_id == "biscuit" else "Fichier non reconnu. Importez un PDF"
                + (", PNG ou JPEG." if tool_id in {"donut", "granola"} else "."),
            )
        target = folder / f"input-{index}{suffix}"
        tmp.replace(target)
        inputs.append(target.name)
    return inputs


@router.post("/api/tools/{tool_id}/run", response_model=ToolResult, status_code=201)
async def run_tool(
    tool_id: str, settings: str = Form("{}"), files: list[UploadFile] = File(default=[])
):
    return await process_tool(tool_id, settings, files)


@router.post("/api/tools/burger/example", response_model=ToolResult, status_code=201)
async def burger_example(settings: str = Form("{}"), files: list[UploadFile] = File(default=[])):
    return await process_tool("burger", settings, files, example=True)


async def process_tool(tool_id, settings, files, *, example=False):
    svc = service()
    if tool_id not in CATALOG:
        raise HTTPException(404, "Outil inconnu.")
    definition = CATALOG[tool_id]
    if tool_id == "fortune-cookie" and len(settings.encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(413, "Réglages Fortune Cookie trop volumineux (2 Mo maximum).")
    if not example and not definition.min_files <= len(files) <= definition.max_files:
        raise HTTPException(
            422, f"Importez de {definition.min_files} à {definition.max_files} fichier(s)."
        )
    try:
        params = MODELS[tool_id].model_validate_json(settings)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(e["msg"] for e in exc.errors())) from exc
    if example and len(files) != int(params.template_tool == "pdf"):
        raise HTTPException(
            422, "Importez le gabarit PDF avant de charger un exemple à son format."
        )
    svc.purge()
    if sum(p.is_dir() and p.name != "mail-outbox" for p in svc.DATA.iterdir()) >= 100:
        raise HTTPException(429, "Limite de 100 travaux atteinte. Supprimez des travaux.")
    job_id = uuid4().hex
    folder = svc.DATA / job_id
    folder.mkdir(mode=0o700)
    svc.busy.add(job_id)
    try:
        inputs = await stage_files(folder, files, tool_id)
        (folder / "tool-request.json").write_text(
            json.dumps({"tool": tool_id, "files": inputs, "settings": params.model_dump()})
        )
        response = ToolResult.model_validate(
            await svc.worker("tool-example" if example else "tools", folder)
        )
        response.id = job_id
        (folder / "result.json").write_text(response.model_dump_json(indent=2))
        with Session(svc.engine) as db:
            db.add(
                Job(
                    id=job_id,
                    name=definition.name,
                    created_at=datetime.now(),
                    info=json.dumps({"tool": tool_id}),
                    status="ready",
                )
            )
            db.commit()
        return response
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        svc.busy.discard(job_id)
        for upload in files:
            await upload.close()


def get_result(job_id: str):
    svc = service()
    with Session(svc.engine) as db:
        job = db.get(Job, job_id)
        if not job or job.created_at < datetime.now() - timedelta(hours=24):
            raise HTTPException(404, "Résultat expiré ou supprimé. Relancez l’outil.")
        if "tool" not in json.loads(job.info):
            raise HTTPException(404, "Résultat introuvable.")
    path = svc.DATA / job_id / "result.json"
    if not path.is_file():
        raise HTTPException(404, "Résultat introuvable.")
    return ToolResult.model_validate_json(path.read_text())


@router.get("/api/tool-jobs/{job_id}", response_model=ToolResult)
def get_tool_result(job_id: str):
    return get_result(job_id)


@router.get("/api/tool-jobs/{job_id}/files/{name}")
def get_artifact(job_id: str, name: str):
    result = get_result(job_id)
    item = next((a for a in result.artifacts if a.name == name), None)
    if item is None:
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(
        service().DATA / job_id / item.name,
        media_type=item.media_type,
        filename=f"snackpress-{item.name}",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/api/tool-jobs/{job_id}", status_code=204)
def delete_result(job_id: str):
    get_result(job_id)
    svc = service()
    with Session(svc.engine) as db:
        db.delete(db.get(Job, job_id))
        db.commit()
    shutil.rmtree(svc.DATA / job_id, ignore_errors=True)
