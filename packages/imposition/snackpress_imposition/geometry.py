from math import ceil, floor
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    schema_version: Literal[1] = 1
    sheet_width: float = Field(default=320, gt=0, le=1200)
    sheet_height: float = Field(default=450, gt=0, le=1200)
    margin: float = Field(default=10, ge=0, le=100)
    trim_width: float = Field(default=85, gt=0, le=1200)
    trim_height: float = Field(default=55, gt=0, le=1200)
    bleed: float = Field(default=0, ge=0, le=20)
    gap: float = Field(default=6, ge=0, le=100)
    quantity: int = Field(default=250, ge=1, le=1_000_000)
    rotation: Literal["auto", "0", "90"] = "auto"
    columns: int | None = Field(default=None, ge=1, le=100)
    rows: int | None = Field(default=None, ge=1, le=100)
    flip: Literal["long", "short"] = "long"
    crop_marks: bool = True
    confirm_trim: bool = False

    @model_validator(mode="after")
    def validate_gap(self):
        if self.gap < self.bleed * 2:
            raise ValueError("L’espacement doit être au moins égal à deux fois le fond perdu.")
        return self


class Placement(BaseModel):
    x: float
    y: float
    width: float
    height: float
    rotation: int


class Mark(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Plan(BaseModel):
    settings: Settings
    columns: int
    rows: int
    rotation: int
    poses: int
    sheets: int
    produced: int
    front: list[Placement]
    back: list[Placement]
    marks: list[Mark]
    warnings: list[str]


def calculate(settings: Settings, duplex: bool = False) -> Plan:
    s = settings
    usable_w = s.sheet_width - 2 * (s.margin + s.bleed)
    usable_h = s.sheet_height - 2 * (s.margin + s.bleed)
    options = []
    for angle in (0, 90):
        if s.rotation != "auto" and int(s.rotation) != angle:
            continue
        w, h = (s.trim_width, s.trim_height) if angle == 0 else (s.trim_height, s.trim_width)
        cols = s.columns or floor((usable_w + s.gap + 1e-8) / (w + s.gap))
        rows = s.rows or floor((usable_h + s.gap + 1e-8) / (h + s.gap))
        gw, gh = cols * (w + s.gap) - s.gap, rows * (h + s.gap) - s.gap
        if cols > 0 and rows > 0 and gw <= usable_w + 1e-7 and gh <= usable_h + 1e-7:
            options.append((cols * rows, angle, cols, rows, w, h, gw, gh))
    if not options:
        raise ValueError("Aucune pose ne tient. Agrandissez la feuille ou réduisez les marges.")
    # Stable tie-break: prefer unrotated artwork for equal yields.
    poses, angle, cols, rows, w, h, gw, gh = max(options, key=lambda o: (o[0], -o[1]))
    if poses > 2000:
        raise ValueError("Le prototype est limité à 2 000 poses par feuille.")
    x0, y0 = (s.sheet_width - gw) / 2, (s.sheet_height - gh) / 2
    front = [
        Placement(
            x=x0 + col * (w + s.gap), y=y0 + row * (h + s.gap), width=w, height=h, rotation=angle
        )
        for row in range(rows)
        for col in range(cols)
    ]
    # Long edge is vertical on portrait paper, horizontal on landscape paper.
    mirror_x = (s.sheet_height >= s.sheet_width) == (s.flip == "long")
    back = (
        [
            Placement(
                x=s.sheet_width - p.x - w if mirror_x else p.x,
                y=p.y if mirror_x else s.sheet_height - p.y - h,
                width=w,
                height=h,
                rotation=angle,
            )
            for p in front
        ]
        if duplex
        else []
    )
    marks = []
    warnings = []
    if s.crop_marks:
        offset, length = s.bleed + 1, 3
        if min(x0, y0) < offset + length:
            warnings.append("Espace extérieur insuffisant : repères de coupe omis.")
        else:
            # Shared cut guides outside the entire artwork grid, never inside another pose.
            for x in sorted({round(p.x + dx, 8) for p in front for dx in (0, w)}):
                for y, sign in ((y0 - offset, -1), (y0 + gh + offset, 1)):
                    marks.append(Mark(x1=x, y1=y, x2=x, y2=y + sign * length))
            for y in sorted({round(p.y + dy, 8) for p in front for dy in (0, h)}):
                for x, sign in ((x0 - offset, -1), (x0 + gw + offset, 1)):
                    marks.append(Mark(x1=x, y1=y, x2=x + sign * length, y2=y))
    warnings.append("Imprimer à 100 %. Vérifier le retournement sur une épreuve papier.")
    return Plan(
        settings=s,
        columns=cols,
        rows=rows,
        rotation=angle,
        poses=poses,
        sheets=ceil(s.quantity / poses),
        produced=ceil(s.quantity / poses) * poses,
        front=front,
        back=back,
        marks=marks,
        warnings=warnings,
    )
