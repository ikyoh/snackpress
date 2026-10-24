import asyncio
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from snackpress_imposition.geometry import Plan, Settings, calculate
from snackpress_imposition.pdf import DocumentInfo
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from .accounts import router as accounts_router
from .configurations import router as configurations_router
from .database import AccountToken, Base, Job, LoginSession
from .previews import router as previews_router
from .products import router as products_router
from .tools import router as tools_router

DATA = Path(os.environ.get("SNACKPRESS_DATA", ".data")).resolve()
DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(DATA, 0o700)
engine = create_engine(f"sqlite:///{DATA / 'jobs.db'}")
Base.metadata.create_all(engine)
MAX_BYTES = 25 * 1024 * 1024
slots = asyncio.Semaphore(2)
busy: set[str] = set()


def purge():
    with Session(engine) as db:
        from .accounts import now

        db.execute(delete(AccountToken).where(AccountToken.expires_at <= now()))
        db.execute(delete(LoginSession).where(LoginSession.expires_at <= now()))
        expired = db.scalars(
            select(Job).where(
                (Job.created_at < datetime.now() - timedelta(hours=24))
                | (
                    (Job.status == "preview")
                    & (Job.created_at < datetime.now() - timedelta(minutes=30))
                )
            )
        )
        for job in expired:
            if job.id not in busy:
                shutil.rmtree(DATA / job.id, ignore_errors=True)
                db.delete(job)
        db.commit()
        known = set(db.scalars(select(Job.id)))
    # Interrupted imports can leave an orphan folder before a database row exists.
    for folder in DATA.iterdir():
        if folder.name == "mail-outbox":
            for mail in folder.glob("*.eml"):
                if mail.stat().st_mtime < datetime.now().timestamp() - 3600:
                    mail.unlink(missing_ok=True)
            continue
        if folder.is_dir() and folder.name not in known and folder.name not in busy:
            if datetime.fromtimestamp(folder.stat().st_mtime) < datetime.now() - timedelta(
                hours=24
            ):
                shutil.rmtree(folder, ignore_errors=True)


async def sweeper():
    while True:
        await asyncio.sleep(60)
        purge()


@asynccontextmanager
async def lifespan(app):
    purge()
    task = asyncio.create_task(sweeper())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Snackpress", version="0.2.0", lifespan=lifespan)
app.include_router(tools_router)
app.include_router(previews_router)
app.include_router(accounts_router)
app.include_router(configurations_router)
app.include_router(products_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not reflect passwords, bearer links or private settings in error responses.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        },
    )


@app.middleware("http")
async def private_account_responses(request: Request, call_next):
    private = request.url.path.startswith(
        ("/api/auth", "/api/configurations", "/api/print-catalog")
    )
    if private:
        limit = (
            2 * 1024 * 1024 + 16 * 1024
            if request.url.path.startswith("/api/configurations")
            else 300 * 1024
            if request.url.path.startswith("/api/print-catalog")
            else 80 * 1024
        )
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            chunks.append(chunk)
            if size > limit:
                return JSONResponse(
                    status_code=413, content={"detail": "Requête trop volumineuse."}
                )
        request._body = b"".join(chunks)
    response = await call_next(request)
    if private:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


class JobResponse(BaseModel):
    id: str
    name: str
    document: DocumentInfo


def get_job(job_id: str) -> JobResponse:
    with Session(engine) as db:
        job = db.get(Job, job_id)
        if not job or job.created_at < datetime.now() - timedelta(hours=24):
            raise HTTPException(404, "Travail introuvable ou expiré. Importez à nouveau votre PDF.")
        if "tool" in json.loads(job.info):
            raise HTTPException(404, "Travail d’imposition introuvable.")
        return JobResponse(
            id=job.id, name=job.name, document=DocumentInfo.model_validate_json(job.info)
        )


async def worker(action: str, folder: Path):
    async with slots:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "snackpress_api.worker",
            action,
            str(folder),
            env={
                **os.environ,
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "PYTHONPATH": os.pathsep.join(
                    [
                        str(Path(__file__).resolve().parents[1]),
                        str(Path(__file__).resolve().parents[3] / "packages/imposition"),
                        str(Path(__file__).resolve().parents[3] / "packages/prepress"),
                    ]
                ),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.wait()
            raise HTTPException(
                422, "Traitement interrompu (limite de 30 secondes). Simplifiez le PDF."
            )
        try:
            result = json.loads(stdout)
        except (ValueError, TypeError):
            raise HTTPException(422, "Le PDF dépasse les ressources du prototype.") from None
        if process.returncode or "error" in result:
            raise HTTPException(422, result.get("error", "Traitement impossible."))
        return result


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.post("/api/jobs", response_model=JobResponse, status_code=201)
async def upload(file: UploadFile):
    purge()
    # Quota for the local prototype, including concurrent uploads.
    if sum(1 for p in DATA.iterdir() if p.is_dir() and p.name != "mail-outbox") >= 100:
        raise HTTPException(
            429,
            "Limite de 100 travaux atteinte. Supprimez des travaux ou attendez leur expiration.",
        )
    job_id = uuid4().hex
    folder = DATA / job_id
    folder.mkdir(mode=0o700)
    busy.add(job_id)
    try:
        total = 0
        with (folder / "source.pdf").open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(
                        413, "Le PDF dépasse 25 Mo. Réduisez sa taille puis réessayez."
                    )
                output.write(chunk)
        with (folder / "source.pdf").open("rb") as source:
            if not source.read(1024).lstrip().startswith(b"%PDF-"):
                raise HTTPException(422, "Ce fichier n’est pas un PDF valide.")
        info = DocumentInfo.model_validate(await worker("inspect", folder))
        name = Path((file.filename or "document.pdf").replace("\\", "/")).name[:150]
        with Session(engine) as db:
            db.add(
                Job(id=job_id, name=name, created_at=datetime.now(), info=info.model_dump_json())
            )
            db.commit()
        return JobResponse(id=job_id, name=name, document=info)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        busy.discard(job_id)
        await file.close()


@app.post("/api/jobs/{job_id}/plan", response_model=Plan)
def plan_job(job_id: str, settings: Settings):
    job = get_job(job_id)
    try:
        return calculate(settings, len(job.document.pages) == 2)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/jobs/{job_id}/export", response_model=Plan)
async def export_job(job_id: str, settings: Settings):
    get_job(job_id)
    if job_id in busy:
        raise HTTPException(409, "Un traitement est déjà en cours pour ce travail.")
    busy.add(job_id)
    try:
        plan = plan_job(job_id, settings)
        folder = DATA / job_id
        (folder / "request.json").write_text(plan.model_dump_json(indent=2))
        await worker("export", folder)
        return plan
    finally:
        busy.discard(job_id)


@app.get("/api/jobs/{job_id}/{artifact}")
def download(job_id: str, artifact: str):
    get_job(job_id)
    names = {
        "source": ("source.pdf", "application/pdf"),
        "output": ("output.pdf", "application/pdf"),
        "settings": ("plan.json", "application/json"),
    }
    if artifact != "source" and job_id in busy:
        raise HTTPException(409, "Le PDF est en cours de génération.")
    if artifact not in names:
        raise HTTPException(404, "Fichier introuvable.")
    name, mime = names[artifact]
    path = DATA / job_id / name
    if not path.is_file():
        raise HTTPException(404, "Générez d’abord le PDF imposé.")
    return FileResponse(
        path,
        media_type=mime,
        filename=f"snackpress-{name}",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    get_job(job_id)
    if job_id in busy:
        raise HTTPException(409, "Attendez la fin du traitement avant de supprimer le travail.")
    with Session(engine) as db:
        db.delete(db.get(Job, job_id))
        db.commit()
    shutil.rmtree(DATA / job_id, ignore_errors=True)
