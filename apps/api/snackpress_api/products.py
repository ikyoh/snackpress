"""Owner-scoped catalogue with optimistic concurrency and public starter examples."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from snackpress_tools.products import PrintCatalog, seed_catalog
from sqlalchemy import update
from sqlalchemy.orm import Session

from .accounts import AccountResponse, current_user, engine, protect
from .database import PrintLibrary, User

router = APIRouter(prefix="/api/print-catalog", tags=["print-catalog"])


class LibraryResponse(BaseModel):
    catalog: PrintCatalog
    revision: int = Field(default=0, ge=0)


@router.get("/starter", response_model=LibraryResponse)
def starter():
    return LibraryResponse(catalog=seed_catalog())


@router.get("", response_model=LibraryResponse)
def get_library(user: AccountResponse = Depends(current_user)):
    with Session(engine()) as db:
        row = db.get(PrintLibrary, user.id)
        return (
            LibraryResponse(
                catalog=PrintCatalog.model_validate_json(row.content), revision=row.revision
            )
            if row
            else starter()
        )


@router.put("", response_model=LibraryResponse, dependencies=[Depends(protect)])
def save_library(data: LibraryResponse, user: AccountResponse = Depends(current_user)):
    content = data.catalog.model_dump_json()
    if len(content.encode()) > 250_000:
        raise HTTPException(413, "Catalogue trop volumineux (250 Ko maximum).")
    with Session(engine()) as db:
        # Serialize first creation and revision checks as well as updates.
        db.execute(update(User).where(User.id == user.id).values(email=user.email))
        row = db.get(PrintLibrary, user.id)
        if (row.revision if row else 0) != data.revision:
            raise HTTPException(
                409, "Le catalogue a changé sur un autre appareil. Rechargez-le avant de réessayer."
            )
        if row:
            row.content = content
            row.revision += 1
        else:
            row = PrintLibrary(user_id=user.id, content=content, revision=1)
            db.add(row)
        db.commit()
        return LibraryResponse(catalog=data.catalog, revision=row.revision)
