from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .products import Snapshot


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Burger(Params):
    source_mode: Literal["classic", "catalog", "free"] = "classic"
    product_snapshot: Snapshot | None = None
    title: str = Field(default="Bon à tirer", max_length=120)
    client: str = Field(default="", max_length=120)
    paper: str = Field(default="À confirmer", max_length=120)
    notes: str = Field(default="", max_length=3000)
    document_type: Literal["custom", "card", "brochure"] = "custom"
    expected_files: int = Field(default=1, ge=1, le=80)
    cover_files: int = Field(default=1, ge=1, le=79)
    interior_pages: int = Field(default=4, ge=1, le=200)
    finishes: list[str] = Field(default_factory=list, max_length=12)
    template_tool: Literal["none", "pizza", "taco", "burrito", "sushi", "pdf"] = "none"
    template_settings: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def production(self):
        if self.source_mode != "classic" and self.product_snapshot is None:
            raise ValueError("Choisissez un produit ou configurez le mode libre avant le BAT.")
        if self.document_type == "card" and self.expected_files != 2:
            raise ValueError("Une carte recto verso attend 2 fichiers, un par face.")
        if self.document_type == "brochure" and self.cover_files >= self.expected_files:
            raise ValueError(
                "Prévoyez des fichiers de couverture et au moins un fichier intérieur."
            )
        if self.document_type == "brochure" and self.cover_files > 4:
            raise ValueError("La couverture de 4 pages accepte au maximum 4 fichiers.")
        self.finishes = [name.strip() for name in self.finishes]
        if any(not name or len(name) > 80 for name in self.finishes):
            raise ValueError("Chaque finition doit avoir un nom de 1 à 80 caractères.")
        if len({name.casefold() for name in self.finishes}) != len(self.finishes):
            raise ValueError("Chaque finition doit avoir un nom distinct.")
        models = {"pizza": Pizza, "taco": Taco, "burrito": Burrito, "sushi": Sushi}
        if self.template_tool in models:
            self.template_settings = (
                models[self.template_tool].model_validate(self.template_settings).model_dump()
            )
        elif self.template_settings:
            raise ValueError(
                "Sélectionnez Pizza, Taco, Burrito ou Sushi pour ces réglages de gabarit."
            )
        return self


class Chili(Params):
    pass


class Donut(Params):
    bleed: float = Field(default=3, gt=0, le=30)
    method: Literal["edge", "mirror"] = "mirror"
    dpi: int = Field(default=150, ge=72, le=300)
    image_width: float = Field(default=85, gt=0, le=2000)
    output: Literal["pdf", "png"] = "pdf"


class Tiramisu(Params):
    dpi: int = Field(default=96, ge=72, le=150)
    tolerance: int = Field(default=12, ge=0, le=255)
    opacity: float = Field(default=0.5, ge=0, le=1)


class Taco(Params):
    width: float = Field(default=297, gt=20, le=2000)
    height: float = Field(default=210, gt=20, le=2000)
    fold: Literal["accordion", "roll", "gate"] = "accordion"
    panels: int = Field(default=3, ge=2, le=8)
    allowance: float = Field(default=2, ge=0, le=10)
    turn: Literal["left_right", "top_bottom"] = "left_right"
    recto_face: Literal["outside", "inside"] = "outside"
    flap_side: Literal["right", "left"] = "right"


class Pizza(Params):
    shape: Literal["rectangle", "circle", "ellipse"] = "rectangle"
    corner_radius: float = Field(default=0, ge=0, le=1000)
    width: float = Field(default=85, gt=0, le=2000)
    height: float = Field(default=55, gt=0, le=2000)
    width_mode: Literal["fixed", "bounded"] = "fixed"
    width_min: float = Field(default=0.1, gt=0, le=2000)
    width_max: float = Field(default=2000, gt=0, le=2000)
    height_mode: Literal["fixed", "bounded"] = "fixed"
    height_min: float = Field(default=0.1, gt=0, le=2000)
    height_max: float = Field(default=2000, gt=0, le=2000)
    bleed: float = Field(default=3, ge=0, le=30)
    safety: float = Field(default=4, ge=0, le=100)
    safety_top: float | None = Field(default=None, ge=0, le=100)
    safety_bottom: float | None = Field(default=None, ge=0, le=100)
    safety_left: float | None = Field(default=None, ge=0, le=100)
    safety_right: float | None = Field(default=None, ge=0, le=100)
    unusable_top: float = Field(default=0, ge=0, le=2000)
    unusable_bottom: float = Field(default=0, ge=0, le=2000)
    unusable_left: float = Field(default=0, ge=0, le=2000)
    unusable_right: float = Field(default=0, ge=0, le=2000)

    @model_validator(mode="after")
    def inside(self):
        for axis, label in (("width", "largeur"), ("height", "hauteur")):
            if axis == "height" and self.shape == "circle":
                continue
            if getattr(self, f"{axis}_mode") == "bounded":
                low, high = getattr(self, f"{axis}_min"), getattr(self, f"{axis}_max")
                if low > high:
                    raise ValueError(
                        f"La borne minimale de {label} doit être inférieure ou égale au maximum."
                    )
                if not low <= getattr(self, axis) <= high:
                    raise ValueError(f"La {label} doit être comprise entre {low:g} et {high:g} mm.")
        if self.shape == "circle":
            self.height = self.width
        elif self.shape == "rectangle" and self.corner_radius * 2 > min(self.width, self.height):
            raise ValueError(
                "Le rayon des coins ne peut pas dépasser la moitié du plus petit côté."
            )
        for side in ("top", "bottom", "left", "right"):
            if getattr(self, f"safety_{side}") is None:
                setattr(self, f"safety_{side}", self.safety)
        for prefix, label in (("safety", "sécurité"), ("unusable", "inexploitable")):
            if (
                getattr(self, f"{prefix}_left") + getattr(self, f"{prefix}_right") >= self.width
                or getattr(self, f"{prefix}_top") + getattr(self, f"{prefix}_bottom") >= self.height
            ):
                raise ValueError(
                    f"La zone {label} doit laisser une surface intérieure au format fini."
                )
        return self


class Burrito(Params):
    width: float = Field(default=2000, gt=10, le=5000)
    height: float = Field(default=1000, gt=10, le=5000)
    hem: float = Field(default=30, ge=0, le=200)
    sleeve: float = Field(default=0, ge=0, le=300)
    spacing: float = Field(default=500, ge=50, le=2000)
    inset: float = Field(default=20, ge=0, le=200)

    @model_validator(mode="after")
    def inside(self):
        if 2 * max(self.inset, self.hem) >= min(self.width, self.height):
            raise ValueError("Les ourlets et œillets doivent rester dans le format fini.")
        return self


class Club(Params):
    pages: int = Field(default=128, ge=4, le=2000, multiple_of=2)
    mode: Literal["bulk", "caliper"] = "bulk"
    gsm: float = Field(default=100, ge=20, le=500)
    bulk: float = Field(default=1, ge=0.5, le=3)
    caliper: float = Field(default=100, ge=20, le=600)
    glue: float = Field(default=0.5, ge=0, le=5)


class Numbering(Params):
    x: float = Field(default=6, ge=0, le=500)
    y: float = Field(default=49, ge=0, le=500)
    color: str = Field(default="#183d36", pattern=r"^#[0-9a-fA-F]{6}$")
    size: float = Field(default=8, ge=1, le=300)
    font: Literal["Snack", "SnackBold", "Helvetica", "Times-Roman", "Courier"] = "SnackBold"
    rotation: float = Field(default=0, ge=-360, le=360)


class Fortune(Params):
    width: float = Field(default=85, ge=40, le=500)
    height: float = Field(default=55, ge=40, le=500)
    count: int = Field(default=10, ge=1, le=100)
    start: int = Field(default=1, ge=0, le=999999999)
    digits: int = Field(default=4, ge=1, le=12)
    prefix: str = Field(default="SP-", max_length=30)
    code: Literal["code128", "none"] = "none"
    payload: str = Field(default="https://example.com/{n}", max_length=500)
    numberings: list[Numbering] | None = None

    @model_validator(mode="before")
    @classmethod
    def remove_legacy_fields(cls, values):
        if isinstance(values, dict):
            values = dict(values)
            values.pop("text", None)
            if values.get("code") == "qr":
                values["code"] = "none"
        return values

    @model_validator(mode="after")
    def positions(self):
        for numbering in self.numberings or []:
            if numbering.x > self.width or numbering.y > self.height:
                raise ValueError(
                    "Le point de placement de chaque numérotation doit rester sur le support."
                )
        return self


class Poke(Params):
    dpi: int = Field(default=72, ge=36, le=150)


class Sushi(Params):
    width: float = Field(default=85, gt=5, le=2000)
    height: float = Field(default=55, gt=5, le=2000)
    shape: Literal["rectangle", "circle"] = "rectangle"
    creases: str = Field(default="", max_length=300)
    cut_name: str = Field(default="CutContour", min_length=1, max_length=40)
    crease_name: str = Field(default="Crease", min_length=1, max_length=40)

    @model_validator(mode="after")
    def names(self):
        if self.cut_name == self.crease_name:
            raise ValueError("Les deux tons directs doivent avoir des noms différents.")
        if self.shape == "circle" and abs(self.width - self.height) > 0.001:
            raise ValueError("Un contour cercle demande une largeur et une hauteur identiques.")
        return self


class Kebab(Params):
    product_snapshot: Snapshot
    title: str = Field(default="Fiche de fabrication", max_length=120)
    client: str = Field(default="", max_length=120)
    quantity: int = Field(default=250, ge=1, le=10000000)
    colors: str = Field(default="Quadri", max_length=200)
    notes: str = Field(default="", max_length=4000)


class Layer(Params):
    mode: Literal["repeat", "booklet"] = "repeat"
    sheet_width: float = Field(default=320, gt=0, le=1200)
    sheet_height: float = Field(default=450, gt=0, le=1200)
    margin: float = Field(default=10, ge=0, le=100)
    gap: float = Field(default=6, ge=0, le=100)
    quantity: int = Field(default=250, ge=1, le=1000000)
    flip: Literal["long", "short"] = "long"


class Bento(Params):
    operation: Literal["merge", "extract", "reorder", "rotate"] = "merge"
    pages: str = Field(default="1", max_length=1000)
    rotation: int = Field(default=90, ge=0, le=270, multiple_of=90)


class Option(BaseModel):
    value: str
    label: str


class ToolField(BaseModel):
    key: str
    label: str
    type: Literal["number", "text", "textarea", "select"]
    default: str | float | int
    unit: str = ""
    min: float | None = None
    max: float | None = None
    step: float = 1
    help: str = ""
    options: list[Option] = []


class ToolDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    limit: str
    min_files: int = 0
    max_files: int = 0
    accept: str = ".pdf"
    fields: list[ToolField]


def number(key, label, default, unit="mm", low=0, high=2000, step=0.5, help=""):
    return ToolField(
        key=key,
        label=label,
        type="number",
        default=default,
        unit=unit,
        min=low,
        max=high,
        step=step,
        help=help,
    )


def text(key, label, default="", area=False, help=""):
    return ToolField(
        key=key, label=label, type="textarea" if area else "text", default=default, help=help
    )


def choice(key, label, options):
    return ToolField(
        key=key,
        label=label,
        type="select",
        default=options[0][0],
        options=[Option(value=str(v), label=label) for v, label in options],
    )


DEFINITIONS = [
    ToolDefinition(
        id="burger",
        name="Burger",
        category="Présenter",
        min_files=1,
        max_files=93,
        description="Un BAT A4 avec visuels, finitions, gabarits et fiche technique intégrée.",
        limit=(
            "BAT de présentation, couleurs non contractuelles. Jusqu’à 200 pages source au total."
        ),
        fields=[
            text("title", "Titre du BAT", "Bon à tirer"),
            text("client", "Client / projet"),
            text("paper", "Papier", "À confirmer"),
            text("notes", "Commentaires", area=True),
        ],
    ),
    ToolDefinition(
        id="chili-dog",
        name="Chili Dog",
        category="Contrôler",
        min_files=1,
        max_files=1,
        description="Inspecter les formats, boîtes, polices et images déclarées du PDF.",
        limit="Inspection structurelle ; aucun certificat PDF/X. Jusqu’à 80 pages.",
        fields=[],
    ),
    ToolDefinition(
        id="donut",
        name="Donut",
        category="Préparer",
        min_files=1,
        max_files=1,
        accept=".pdf,.png,.jpg,.jpeg",
        description="Ajouter du fond perdu par prolongement ou miroir.",
        limit=(
            "Correction rasterisée ; chaque bord doit être relu. La zone "
            "visible devient le format fini."
        ),
        fields=[
            number("bleed", "Fond perdu à ajouter", 3, low=0.1, high=30),
            choice(
                "method",
                "Méthode",
                [("mirror", "Miroir"), ("edge", "Prolonger les pixels du bord")],
            ),
            number("dpi", "Résolution raster", 150, "dpi", 72, 300, 1),
            number("image_width", "Largeur finie si image", 85, low=0.1),
            choice(
                "output",
                "Format de sortie",
                [("pdf", "PDF (toutes les pages)"), ("png", "PNG (une page)")],
            ),
        ],
    ),
    ToolDefinition(
        id="tiramisu",
        name="Tiramisu",
        category="Contrôler",
        min_files=2,
        max_files=2,
        description="Comparer deux versions, page par page, avec superposition et différences.",
        limit="Comparaison visuelle raster, page par page. Aucun recalage ni contrôle sémantique.",
        fields=[
            number("dpi", "Résolution de comparaison", 96, "dpi", 72, 150, 1),
            number("tolerance", "Tolérance par canal RGB", 12, "/ 255", 0, 255, 1),
            number("opacity", "Part de la seconde version", 0.5, "", 0, 1, 0.05),
        ],
    ),
    ToolDefinition(
        id="taco",
        name="Taco",
        category="Tracer",
        description="Dessiner les panneaux et les plis du dépliant.",
        limit=(
            "Schéma de panneaux ; valider le pliage avec le façonnier. Portefeuille : 4 panneaux."
        ),
        fields=[
            number("width", "Largeur à plat", 297, low=21),
            number("height", "Hauteur à plat", 210, low=21),
            choice(
                "fold",
                "Type de pli",
                [
                    ("accordion", "Accordéon"),
                    ("roll", "Roulé"),
                    ("gate", "Portefeuille (4 panneaux)"),
                ],
            ),
            number("panels", "Nombre de panneaux", 3, "", 2, 8, 1),
            number("allowance", "Retrait du panneau rentrant", 2, high=10),
            choice(
                "flap_side",
                "Côté du rabat rentrant au recto",
                [("right", "Droite"), ("left", "Gauche")],
            ),
            choice(
                "turn",
                "Retournement du verso",
                [("left_right", "Gauche-droite"), ("top_bottom", "Haut-bas")],
            ),
            choice(
                "recto_face",
                "Face représentée au recto",
                [("outside", "Extérieur du dépliant"), ("inside", "Intérieur du dépliant")],
            ),
        ],
    ),
    ToolDefinition(
        id="pizza",
        name="Pizza",
        category="Tracer",
        description="Créer un gabarit avec coupe, fond perdu et sécurité.",
        limit="Gabarit technique avec guides visibles, à retirer du fichier d’impression final.",
        fields=[
            choice(
                "shape",
                "Forme",
                [
                    ("rectangle", "Carrée / rectangulaire"),
                    ("circle", "Ronde"),
                    ("ellipse", "Ovale"),
                ],
            ),
            choice(
                "width_mode",
                "Réglage de la largeur",
                [("fixed", "Valeur fixe"), ("bounded", "Entre min et max")],
            ),
            number("width_min", "Largeur minimale", 0.1, low=0.1),
            number("width_max", "Largeur maximale", 2000, low=0.1),
            number("width", "Largeur finie", 85, low=0.1),
            choice(
                "height_mode",
                "Réglage de la hauteur",
                [("fixed", "Valeur fixe"), ("bounded", "Entre min et max")],
            ),
            number("height_min", "Hauteur minimale", 0.1, low=0.1),
            number("height_max", "Hauteur maximale", 2000, low=0.1),
            number("height", "Hauteur finie", 55, low=0.1),
            number(
                "corner_radius",
                "Rayon des coins",
                0,
                high=1000,
                help="0 = coins droits. Au maximum la moitié du plus petit côté.",
            ),
            number("bleed", "Fond perdu", 3, high=30),
            number("safety_top", "Sécurité — haut", 4, high=100),
            number("safety_bottom", "Sécurité — bas", 4, high=100),
            number("safety_left", "Sécurité — gauche", 4, high=100),
            number("safety_right", "Sécurité — droite", 4, high=100),
            number("unusable_top", "Zone inexploitable — haut", 0, high=2000),
            number("unusable_bottom", "Zone inexploitable — bas", 0, high=2000),
            number("unusable_left", "Zone inexploitable — gauche", 0, high=2000),
            number("unusable_right", "Zone inexploitable — droite", 0, high=2000),
        ],
    ),
    ToolDefinition(
        id="burrito",
        name="Burrito",
        category="Tracer",
        description="Préparer un plan de bâche : ourlets, fourreaux et œillets.",
        limit=(
            "Plan technique grand format ; aucune modification du visuel. "
            "Fourreau sur le bord supérieur."
        ),
        fields=[
            number("width", "Largeur finie", 2000, low=11, high=5000),
            number("height", "Hauteur finie", 1000, low=11, high=5000),
            number("hem", "Ourlet sur les 4 côtés", 30, high=200),
            number("sleeve", "Fourreau supérieur (0 = aucun)", 0, high=300),
            number("spacing", "Entraxe maximal des œillets", 500, low=50),
            number("inset", "Retrait des œillets", 20, high=200),
        ],
    ),
    ToolDefinition(
        id="club-sandwich",
        name="Club Sandwich",
        category="Calculer",
        description="Estimer le dos d’une brochure à partir du papier intérieur.",
        limit=(
            "Estimation pour dos carré collé, à confirmer au relieur. Pages "
            "intérieures, hors couverture."
        ),
        fields=[
            number("pages", "Pages intérieures (nombre pair)", 128, "pages", 4, 2000, 2),
            choice(
                "mode",
                "Méthode de calcul",
                [("bulk", "Grammage × main"), ("caliper", "Calibre mesuré")],
            ),
            number("gsm", "Grammage", 100, "g/m²", 20, 500, 1),
            number("bulk", "Main du papier", 1, "cm³/g", 0.5, 3, 0.05),
            number("caliper", "Calibre d’une feuille", 100, "µm", 20, 600, 1),
            number("glue", "Marge de colle estimée", 0.5, high=5),
        ],
    ),
    ToolDefinition(
        id="fortune-cookie",
        name="Fortune Cookie",
        category="Personnaliser",
        min_files=0,
        max_files=1,
        description="Générer une série numérotée avec un Code 128 facultatif.",
        limit=(
            "Une page par exemplaire, jusqu’à 100 exemplaires. Fond PDF "
            "facultatif d’une page ; contrôler la numérotation et les éventuels Code 128."
        ),
        fields=[
            number("width", "Largeur du support", 85, low=40, high=500),
            number("height", "Hauteur du support", 55, low=40, high=500),
            number("count", "Nombre d’exemplaires", 10, "", 1, 100, 1),
            number("start", "Premier numéro", 1, "", 0, 999999999, 1),
            number("digits", "Nombre minimal de chiffres", 4, "", 1, 12, 1),
            text("prefix", "Préfixe", "SP-"),
            choice(
                "code", "Code", [("none", "Sans code"), ("code128", "Code 128")]
            ),
            text(
                "payload", "Contenu du code ({n} = numéro avec préfixe)", "https://example.com/{n}"
            ),
        ],
    ),
    ToolDefinition(
        id="poke",
        name="Poké",
        category="Contrôler",
        min_files=1,
        max_files=1,
        description="Relever les espaces couleur, tons directs et estimer la couverture CMJN.",
        limit="Estimation écran à partir du rendu RGB : pas de séparation RIP ni de TAC certifié.",
        fields=[number("dpi", "Échantillonnage écran", 72, "dpi", 36, 150, 1)],
    ),
    ToolDefinition(
        id="sushi",
        name="Sushi",
        category="Tracer",
        description="Tracer des contours de découpe et des rainages vectoriels.",
        limit=(
            "Deux tons directs nommés ; convention, surimpression et "
            "orientation à confirmer à l’atelier."
        ),
        fields=[
            number("width", "Largeur", 85, low=6),
            number("height", "Hauteur (égale à la largeur pour un cercle)", 55, low=6),
            choice("shape", "Contour", [("rectangle", "Rectangle"), ("circle", "Cercle")]),
            text(
                "creases",
                "Rainages verticaux depuis le bord gauche",
                "",
                help="Positions en mm séparées par des virgules, ex. 25, 60.",
            ),
            text("cut_name", "Ton direct de découpe", "CutContour"),
            text("crease_name", "Ton direct de rainage", "Crease"),
        ],
    ),
    ToolDefinition(
        id="kebab",
        name="Kebab",
        category="Présenter",
        description="Créer une fiche de fabrication PDF à partir d’un produit d’impression.",
        limit="Fiche d’instructions, aucune validation automatique des choix ou des consignes.",
        fields=[
            text("title", "Titre", "Fiche de fabrication"),
            text("client", "Client / projet"),
            number("quantity", "Quantité", 250, "ex.", 1, 10000000, 1),
            text("colors", "Couleurs", "Quadri"),
            text("notes", "Consignes atelier", area=True),
        ],
    ),
    ToolDefinition(
        id="layer-cake",
        name="Layer Cake",
        category="Assembler",
        min_files=1,
        max_files=1,
        description="Répéter les poses ou imposer un livret piqué de 4 à 80 pages.",
        limit=(
            "Aucune compensation de chasse ni gestion presse automatique. "
            "Livret : multiple de 4, lecture gauche à droite."
        ),
        fields=[
            choice(
                "mode",
                "Imposition",
                [
                    ("repeat", "Poses répétées (PDF de 1 ou 2 pages)"),
                    ("booklet", "Livret piqué (4 à 80 pages)"),
                ],
            ),
            number("sheet_width", "Largeur feuille", 320, low=1, high=1200),
            number("sheet_height", "Hauteur feuille", 450, low=1, high=1200),
            number("margin", "Marges machine", 10, high=100),
            number("gap", "Espacement (répétition)", 6, high=100),
            number("quantity", "Quantité de produits finis", 250, "ex.", 1, 1000000, 1),
            choice(
                "flip",
                "Retournement (répétition)",
                [("long", "Bord long"), ("short", "Bord court")],
            ),
        ],
    ),
    ToolDefinition(
        id="bento",
        name="Bento",
        category="Assembler",
        min_files=1,
        max_files=8,
        description="Fusionner, extraire, réordonner et pivoter les pages de vos PDF.",
        limit=(
            "PDF non chiffrés ; signatures numériques, formulaires et "
            "annotations non conservés. 80 pages par source, 200 en sortie."
        ),
        fields=[
            choice(
                "operation",
                "Opération",
                [
                    ("merge", "Fusionner dans l’ordre des fichiers"),
                    ("extract", "Extraire des pages du premier fichier"),
                    ("reorder", "Réordonner le premier fichier"),
                    ("rotate", "Pivoter des pages du premier fichier"),
                ],
            ),
            text(
                "pages",
                "Pages (hors fusion)",
                "1",
                help="Ex. 3, 1, 2 ou 1-4, 8. Numérotation à partir de 1.",
            ),
            choice(
                "rotation",
                "Rotation à ajouter",
                [("90", "90°"), ("180", "180°"), ("270", "270°"), ("0", "0°")],
            ),
        ],
    ),
]
MODELS = dict(
    zip(
        [t.id for t in DEFINITIONS],
        [
            Burger,
            Chili,
            Donut,
            Tiramisu,
            Taco,
            Pizza,
            Burrito,
            Club,
            Fortune,
            Poke,
            Sushi,
            Kebab,
            Layer,
            Bento,
        ],
        strict=True,
    )
)
CATALOG = {tool.id: tool for tool in DEFINITIONS}


class Artifact(BaseModel):
    name: str
    label: str
    media_type: str
    pages: int | None = None


class ToolResult(BaseModel):
    id: str = ""
    tool: str
    summary: str
    metrics: dict[str, str | float | int] = {}
    warnings: list[str] = []
    artifacts: list[Artifact] = []
