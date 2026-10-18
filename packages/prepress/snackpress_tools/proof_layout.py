"""Branding and vector guide keys for presentation proofs."""

from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.units import mm

from .catalog import MODELS
from .common import CORAL, INK


def proof_date():
    return datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")


def header_footer(c, date):
    c.saveState()
    # Native paths from apps/web/public/snackpress.svg, including its gradient.
    c.saveState()
    c.translate(18 * mm, 281 * mm)
    c.scale(10 * mm / 64, -10 * mm / 64)
    c.translate(0, -64)
    path = c.beginPath()
    path.moveTo(48, 5)
    path.lineTo(27, 5)
    path.curveTo(15, 5, 8, 12, 8, 21)
    path.curveTo(8, 29, 13, 34, 23, 37)
    path.lineTo(37, 41)
    path.curveTo(40, 42, 42, 43, 42, 45)
    path.curveTo(42, 47, 40, 48, 36, 48)
    path.lineTo(16, 48)
    path.curveTo(9.333, 48, 9.333, 58, 16, 58)
    path.lineTo(36, 58)
    path.curveTo(49, 58, 56, 53, 56, 44)
    path.curveTo(56, 36, 51, 31, 41, 28)
    path.lineTo(27, 24)
    path.curveTo(23, 23, 21, 22, 21, 20)
    path.curveTo(21, 18, 23, 16, 27, 16)
    path.lineTo(48, 16)
    path.close()
    c.saveState()
    c.clipPath(path, stroke=0, fill=0)
    c.linearGradient(22, 5, 43, 53, [colors.HexColor("#f34ca5"), colors.HexColor("#792bc4")])
    c.restoreState()
    fold = c.beginPath()
    fold.moveTo(38, 5)
    fold.lineTo(48, 5)
    fold.lineTo(48, 16)
    fold.close()
    c.setFillColor(colors.HexColor("#ffe169"))
    c.drawPath(fold, stroke=0, fill=1)
    c.restoreState()
    c.setFillColor(colors.HexColor("#792bc4"))
    c.setFont("SnackBold", 16)
    c.drawString(30 * mm, 284 * mm, "snackpress.")
    c.setFillColor(colors.black)
    c.setFont("Snack", 8)
    c.drawRightString(192 * mm, 285 * mm, f"Date du BAT : {date}")
    c.drawString(18 * mm, 11 * mm, "snackpress.com")
    c.linkURL("https://snackpress.com", (18 * mm, 9 * mm, 49 * mm, 15 * mm), relative=0)
    c.drawRightString(192 * mm, 11 * mm, f"Page {c.getPageNumber()}")
    c.restoreState()


def guide_key(tool, settings):
    if tool == "pdf":
        return [("Repères du PDF fourni : convention du fichier source", INK, "custom")]
    if tool == "perforation":
        return [("Perforation", CORAL, "dashed")]
    p = MODELS[tool].model_validate(settings)
    if tool == "pizza":
        entries = [("Coupe / format fini", CORAL, "solid"), ("Zone de sécurité", INK, "dashed")]
        if any(getattr(p, f"unusable_{side}") for side in ("top", "bottom", "left", "right")):
            entries.append(("Zone inexploitable", colors.HexColor("#e6b800"), "hatched"))
        return entries
    if tool == "taco":
        return [("Format à plat / panneaux", INK, "solid"), ("Pliage", CORAL, "dashed")]
    if tool == "burrito":
        entries = [
            ("Format fini", INK, "solid"),
            ("Ourlet", CORAL, "dashed"),
            ("Œillets", INK, "eyelet"),
        ]
        if p.sleeve:
            entries.append(("Fourreau", CORAL, "dashed"))
        return entries
    entries = [(f"Découpe ({p.cut_name})", colors.magenta, "solid")]
    if p.creases.strip():
        entries.append((f"Rainage ({p.crease_name})", colors.cyan, "solid"))
    return entries


def draw_legend(c, entries, top):
    c.saveState()
    c.setFillColor(colors.black)
    c.setFont("SnackBold", 8)
    c.drawString(18 * mm, (top - 8) * mm, "Légende des repères")
    c.setFont("Snack", 7)
    for index, (label, color, style) in enumerate(entries):
        x, y = 18 + (index % 2) * 88, top - 14 - (index // 2) * 5
        c.setStrokeColor(color)
        c.setLineWidth(0.3 * mm)
        c.setDash(2 * mm, mm) if style in {"dashed", "hatched"} else c.setDash()
        if style == "eyelet":
            c.circle((x + 3) * mm, (y + 0.7) * mm, 1.2 * mm)
        elif style != "custom":
            c.line(x * mm, (y + 0.7) * mm, (x + 7) * mm, (y + 0.7) * mm)
        c.setDash()
        if style == "hatched":
            for step in range(4):
                c.line((x + step * 2) * mm, (y - 1) * mm, (x + step * 2 + 2) * mm, (y + 2) * mm)
        c.setFillColor(colors.black)
        # Keep custom spot names within their column without truncating them.
        size = min(7, 76 * mm / max(c.stringWidth(label, "Snack", 1), 1))
        c.setFont("Snack", size)
        c.drawString((x + (0 if style == "custom" else 10)) * mm, y * mm, label)
    c.restoreState()
