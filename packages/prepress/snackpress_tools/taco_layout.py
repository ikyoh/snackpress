"""Physical panel identities and front/back coordinates for folding plans."""

from dataclasses import dataclass
from itertools import accumulate

FOLD_NAMES = {"accordion": "Accordéon", "roll": "Roulé", "gate": "Portefeuille"}
TURN_NAMES = {
    "left_right": "Gauche-droite (axe vertical)",
    "top_bottom": "Haut-bas (axe horizontal)",
}


@dataclass(frozen=True)
class Panel:
    number: int
    width: float
    flap: bool


def fold_widths(p):
    if p.fold == "gate":
        widths = [
            p.width / 4 - p.allowance / 2,
            p.width / 4 + p.allowance / 2,
            p.width / 4 + p.allowance / 2,
            p.width / 4 - p.allowance / 2,
        ]
    elif p.fold == "roll":
        outer = (p.width + p.allowance * p.panels * (p.panels - 1) / 2) / p.panels
        widths = [outer - i * p.allowance for i in range(p.panels)]
        if p.flap_side == "left":
            widths.reverse()
    else:
        widths = [p.width / p.panels] * p.panels
    if min(widths) <= 5:
        raise ValueError("Un panneau est trop petit. Réduisez le retrait ou le nombre de panneaux.")
    return widths


def face_panels(p, face):
    widths = fold_widths(p)
    flap = 0 if p.flap_side == "left" else len(widths) - 1
    panels = [
        Panel(i + 1, width, (p.fold == "roll" and i == flap) or (p.fold == "gate" and i in (0, 3)))
        for i, width in enumerate(widths)
    ]
    if face == "verso" and p.turn == "left_right":
        panels.reverse()
    return panels


def fold_positions(p, face):
    return list(accumulate(panel.width for panel in face_panels(p, face)))[:-1]


def face_label(p, face):
    outside = (face == "recto") == (p.recto_face == "outside")
    return f"{face.capitalize()} — {'Extérieur' if outside else 'Intérieur'}"


def reference_corner(p, face):
    """Position of the recto's top-left corner, expressed in each face's own frame."""
    if face == "verso":
        return (p.width, p.height) if p.turn == "left_right" else (0, 0)
    return 0, p.height
