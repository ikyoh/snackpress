"""Durable, versioned presets scoped to the authenticated owner."""

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from snackpress_imposition.geometry import Settings
from snackpress_tools.catalog import MODELS
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .accounts import AccountResponse, current_user, engine, now, protect
from .database import Configuration, User

router = APIRouter(prefix="/api/configurations", tags=["configurations"])


class ConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    settings: dict
    schema_version: int = Field(default=1, ge=1, le=1)
    is_default: bool = False
    revision: int = Field(default=1, ge=1)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Donnez un nom à cette configuration.")
        return value


class ConfigurationResponse(ConfigurationInput):
    id: str
    tool_id: str
    created_at: str
    updated_at: str


def tool_model(tool_id: str):
    model = Settings if tool_id == "imposition" else MODELS.get(tool_id)
    if model is None:
        raise HTTPException(404, "Outil inconnu.")
    return model


def validated(tool_id: str, settings: dict):
    limit = 2 * 1024 * 1024 if tool_id == "fortune-cookie" else 65536
    if len(json.dumps(settings, ensure_ascii=False).encode("utf-8")) > limit:
        raise HTTPException(413, "Configuration trop volumineuse.")
    try:
        result = tool_model(tool_id).model_validate(settings).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(e["msg"] for e in exc.errors())) from None
    if tool_id == "imposition":
        # A saved preset never certifies dimensions for a newly imported document.
        result["confirm_trim"] = False
    return result


def output(row: Configuration):
    return ConfigurationResponse(
        id=row.id,
        tool_id=row.tool_id,
        name=row.name,
        settings=json.loads(row.settings),
        schema_version=row.schema_version,
        is_default=row.is_default,
        revision=row.revision,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def owned(db: Session, config_id: str, user_id: str):
    row = db.scalar(
        select(Configuration).where(
            Configuration.id == config_id,
            Configuration.user_id == user_id,
        )
    )
    if not row:
        raise HTTPException(404, "Configuration introuvable.")
    return row


def clear_defaults(db: Session, user_id: str, tool_id: str):
    db.execute(
        update(Configuration)
        .where(
            Configuration.user_id == user_id,
            Configuration.tool_id == tool_id,
            Configuration.is_default.is_(True),
        )
        .values(is_default=False, revision=Configuration.revision + 1, updated_at=now())
    )


@router.get("", response_model=list[ConfigurationResponse])
def list_configurations(tool_id: str, user: AccountResponse = Depends(current_user)):
    tool_model(tool_id)
    with Session(engine()) as db:
        return [
            output(row)
            for row in db.scalars(
                select(Configuration)
                .where(
                    Configuration.user_id == user.id,
                    Configuration.tool_id == tool_id,
                )
                .order_by(Configuration.name)
            )
        ]


@router.post(
    "", response_model=ConfigurationResponse, status_code=201, dependencies=[Depends(protect)]
)
def create_configuration(
    data: ConfigurationInput, tool_id: str, user: AccountResponse = Depends(current_user)
):
    settings = validated(tool_id, data.settings)
    with Session(engine()) as db:
        # Acquire SQLite's write lock before checking the quota / replacing a default.
        db.execute(update(User).where(User.id == user.id).values(email=user.email))
        count = db.scalar(
            select(func.count())
            .select_from(Configuration)
            .where(
                Configuration.user_id == user.id,
            )
        )
        if count >= 200:
            raise HTTPException(409, "Limite de 200 configurations atteinte. Supprimez-en une.")
        if data.is_default:
            clear_defaults(db, user.id, tool_id)
        row = Configuration(
            id=uuid4().hex,
            user_id=user.id,
            tool_id=tool_id,
            name=data.name,
            settings=json.dumps(settings),
            schema_version=1,
            is_default=data.is_default,
            revision=1,
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Ce nom existe déjà pour cet outil. Choisissez un autre nom.")
        return output(row)


@router.put("/{config_id}", response_model=ConfigurationResponse, dependencies=[Depends(protect)])
def update_configuration(
    config_id: str, data: ConfigurationInput, user: AccountResponse = Depends(current_user)
):
    with Session(engine()) as db:
        row = owned(db, config_id, user.id)
        settings = validated(row.tool_id, data.settings)
        changed = db.execute(
            update(Configuration)
            .where(
                Configuration.id == config_id,
                Configuration.user_id == user.id,
                Configuration.revision == data.revision,
            )
            .values(revision=Configuration.revision + 1)
        )
        if changed.rowcount != 1:
            raise HTTPException(
                409,
                "Cette configuration a changé sur un autre appareil. "
                "Rechargez la liste avant de réessayer.",
            )
        if data.is_default and not row.is_default:
            clear_defaults(db, user.id, row.tool_id)
        row.name = data.name
        row.settings = json.dumps(settings)
        row.is_default = data.is_default
        row.updated_at = now()
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "Ce nom existe déjà pour cet outil. Choisissez un autre nom.")
        return output(row)


@router.delete("/{config_id}", status_code=204, dependencies=[Depends(protect)])
def delete_configuration(
    config_id: str, revision: int = Query(ge=1), user: AccountResponse = Depends(current_user)
):
    with Session(engine()) as db:
        owned(db, config_id, user.id)
        result = db.execute(
            delete(Configuration).where(
                Configuration.id == config_id,
                Configuration.user_id == user.id,
                Configuration.revision == revision,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Cette configuration a changé. Rechargez la liste.")
        db.commit()
