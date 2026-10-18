"""Composable print specifications shared by the catalogue and frozen proofs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Named(Spec):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)


class Category(Named):
    parent_id: str | None = None


class Material(Named):
    family: str = Field(default="Papier", max_length=80)
    gsm: float | None = Field(default=None, gt=0, le=3000)
    thickness: float | None = Field(default=None, gt=0, le=100)
    description: str = Field(default="", max_length=500)


class Finish(Named):
    mask: bool = False
    material_ids: list[str] = Field(default_factory=list, max_length=100)
    excludes: list[str] = Field(default_factory=list, max_length=30)


class Slot(Named):
    pages: int = Field(default=1, ge=1, le=200)
    role: Literal["visual", "mask"] = "visual"


class Guide(Spec):
    tool: Literal["pizza", "taco", "burrito", "sushi", "perforation"] = "pizza"
    settings: dict = Field(default_factory=dict)


class SerialPlacement(Spec):
    x: float = Field(default=6, ge=0, le=5000)
    y: float = Field(default=20, ge=0, le=5000)
    size: float = Field(default=10, ge=4, le=100)
    offset: int = Field(default=0, ge=0, le=999999999)
    face: int = Field(default=1, ge=1, le=2)


class Tickets(Spec):
    start: int = Field(default=1, ge=0, le=999999999)
    count: int = Field(default=50, ge=1, le=100)
    digits: int = Field(default=4, ge=1, le=12)
    prefix: str = Field(default="", max_length=30)
    suffix: str = Field(default="", max_length=30)
    per_book: int = Field(default=25, ge=1, le=100)
    binding: Literal["loose", "stapled", "glued"] = "loose"
    placements: list[SerialPlacement] = Field(
        default_factory=lambda: [SerialPlacement(), SerialPlacement(x=45)],
        min_length=1,
        max_length=20,
    )
    code: Literal["none", "qr", "code128"] = "none"
    payload: str = Field(default="{n}", max_length=300)
    code_x: float = Field(default=65, ge=0, le=5000)
    code_y: float = Field(default=5, ge=0, le=5000)


class PizzaTemplate(Named):
    revision: int = Field(ge=1)


class Component(Named):
    pizza_template: PizzaTemplate | None = None
    width: float = Field(default=85, gt=5, le=5000)
    height: float = Field(default=55, gt=5, le=5000)
    bleed: float = Field(default=3, ge=0, le=30)
    material_id: str = ""
    page_multiple: int = Field(default=1, ge=1, le=32)
    slots: list[Slot] = Field(
        default_factory=lambda: [Slot(id="recto", name="Recto")], min_length=1, max_length=30
    )
    guides: list[Guide] = Field(default_factory=list, max_length=5)
    tickets: Tickets | None = None

    @model_validator(mode="after")
    def validate_geometry(self):
        # Import lazily: tool models also include the snapshot defined below.
        from .catalog import MODELS

        if len({s.id for s in self.slots}) != len(self.slots):
            raise ValueError("Les emplacements doivent avoir des identifiants distincts.")
        if not any(s.role == "visual" for s in self.slots):
            raise ValueError("Chaque composant doit contenir au moins un visuel.")
        if sum(s.pages for s in self.slots if s.role == "visual") % self.page_multiple:
            raise ValueError(
                f"La pagination de {self.name} doit être un multiple de {self.page_multiple}."
            )
        tools = [g.tool for g in self.guides]
        if self.pizza_template:
            pizza = next((g for g in self.guides if g.tool == "pizza"), None)
            if pizza is None:
                raise ValueError("Le gabarit Pizza sélectionné doit être conservé dans les tracés.")
            template_settings = MODELS["pizza"].model_validate(pizza.settings).model_dump()
            for axis, label in (("width", "largeur"), ("height", "hauteur")):
                if axis == "height" and template_settings["shape"] == "circle":
                    continue
                if (
                    template_settings[f"{axis}_mode"] == "fixed"
                    and abs(getattr(self, axis) - template_settings[axis]) > 0.01
                ):
                    raise ValueError(f"La {label} est fixée par le gabarit Pizza sélectionné.")
            if abs(self.bleed - template_settings["bleed"]) > 0.01:
                raise ValueError("Le fond perdu est fixé par le gabarit Pizza sélectionné.")
        if len(set(tools)) != len(tools):
            raise ValueError("Un seul tracé de chaque outil par composant.")
        if "pizza" in tools and "sushi" in tools:
            raise ValueError("Choisissez Pizza ou Sushi comme référence de découpe.")
        for guide in self.guides:
            if guide.tool == "perforation":
                positions = guide.settings.get("positions", [30])
                axis = guide.settings.get("axis", "vertical")
                if set(guide.settings) - {"positions", "axis"} or axis not in {
                    "vertical",
                    "horizontal",
                }:
                    raise ValueError("Réglages de perforation invalides.")
                limit = self.width if axis == "vertical" else self.height
                if not isinstance(positions, list) or not 1 <= len(positions) <= 20:
                    raise ValueError("Prévoyez de 1 à 20 perforations.")
                if any(not isinstance(x, (int, float)) or not 0 < x < limit for x in positions):
                    raise ValueError("Les perforations doivent rester dans le format fini.")
                if len(set(positions)) != len(positions):
                    raise ValueError("Les perforations doivent être distinctes.")
                guide.settings = {"axis": axis, "positions": positions}
            else:
                settings = {**guide.settings, "width": self.width, "height": self.height}
                if guide.tool == "pizza":
                    settings["bleed"] = self.bleed
                guide.settings = MODELS[guide.tool].model_validate(settings).model_dump()
                if abs(guide.settings["height"] - self.height) > 0.01:
                    raise ValueError("Le cercle exige une largeur et une hauteur identiques.")
        if self.tickets:
            visuals = [s for s in self.slots if s.role == "visual"]
            if not 1 <= len(visuals) <= 2 or any(s.pages != 1 for s in visuals):
                raise ValueError(
                    "Les billets attendent un recto et un verso facultatif, d’une page chacun."
                )
            for placement in self.tickets.placements:
                if (
                    placement.face > len(visuals)
                    or placement.x >= self.width
                    or placement.y >= self.height
                ):
                    raise ValueError("Chaque numéro doit rester sur une face présente du billet.")
            if self.tickets.code != "none" and (
                self.tickets.code_x + 22 > self.width or self.tickets.code_y + 22 > self.height
            ):
                raise ValueError("Réservez 22 × 22 mm pour le code dans le billet.")
        return self


class Variant(Named):
    components: list[Component] = Field(min_length=1, max_length=12)
    finish_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def components_valid(self):
        if len({c.id for c in self.components}) != len(self.components):
            raise ValueError("Les composants doivent avoir des identifiants distincts.")
        if sum(len(c.slots) for c in self.components) > 60:
            raise ValueError("Limite de 60 emplacements par déclinaison.")
        return self


class Product(Named):
    category_id: str
    description: str = Field(default="", max_length=1000)
    material_ids: list[str] = Field(default_factory=list, max_length=100)
    finish_ids: list[str] = Field(default_factory=list, max_length=30)
    variants: list[Variant] = Field(min_length=1, max_length=30)


class Snapshot(Spec):
    schema_version: Literal[1] = 1
    product_name: str = Field(min_length=1, max_length=120)
    category_name: str = Field(default="Mode libre", max_length=240)
    variant: Variant
    materials: list[Material] = Field(default_factory=list, max_length=100)
    finishes: list[Finish] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def references(self):
        materials = {m.id for m in self.materials}
        finishes = {f.id: f for f in self.finishes}
        if len(materials) != len(self.materials) or len(finishes) != len(self.finishes):
            raise ValueError("Supports ou finitions dupliqués dans les spécifications.")
        if any(c.material_id and c.material_id not in materials for c in self.variant.components):
            raise ValueError("Support matière absent des spécifications.")
        selected = set(self.variant.finish_ids)
        if len(selected) != len(self.variant.finish_ids) or not selected <= finishes.keys():
            raise ValueError("Finition inconnue ou dupliquée.")
        for fid in selected:
            finish = finishes[fid]
            if selected.intersection(finish.excludes):
                raise ValueError("Ces finitions sont incompatibles.")
            for component in self.variant.components:
                if finish.material_ids and component.material_id not in finish.material_ids:
                    raise ValueError(
                        f"Finition {finish.name} incompatible avec le support de {component.name}."
                    )
        slots = snapshot_slots(self)
        if len(slots) > 80:
            raise ValueError("Le BAT accepte au maximum 80 fichiers.")
        if sum(s.pages for _, s in slots) > 200:
            raise ValueError("Le BAT accepte au maximum 200 pages source.")
        return self


class PrintCatalog(Spec):
    categories: list[Category] = Field(max_length=100)
    materials: list[Material] = Field(max_length=100)
    finishes: list[Finish] = Field(max_length=30)
    products: list[Product] = Field(max_length=200)

    @model_validator(mode="after")
    def references(self):
        for rows in (self.categories, self.materials, self.finishes, self.products):
            if len({r.id for r in rows}) != len(rows):
                raise ValueError("Les identifiants du catalogue doivent être distincts.")
        categories = {c.id: c for c in self.categories}
        materials = {m.id for m in self.materials}
        finishes = {f.id for f in self.finishes}
        for category in self.categories:
            seen = {category.id}
            parent = category.parent_id
            while parent:
                if parent not in categories or parent in seen:
                    raise ValueError("Hiérarchie des catégories invalide.")
                seen.add(parent)
                parent = categories[parent].parent_id
        for finish in self.finishes:
            if (
                not set(finish.material_ids) <= materials
                or not set(finish.excludes) <= finishes
                or finish.id in finish.excludes
            ):
                raise ValueError("Compatibilités de finition invalides.")
        for product in self.products:
            if product.category_id not in categories:
                raise ValueError("Catégorie du produit introuvable.")
            if (
                not set(product.material_ids) <= materials
                or not set(product.finish_ids) <= finishes
            ):
                raise ValueError("Support ou finition du produit introuvable.")
            if len({v.id for v in product.variants}) != len(product.variants):
                raise ValueError("Déclinaisons dupliquées.")
            for variant in product.variants:
                if any(
                    c.material_id and c.material_id not in product.material_ids
                    for c in variant.components
                ) or not set(variant.finish_ids) <= set(product.finish_ids):
                    raise ValueError("Choix non autorisé pour ce produit.")
                Snapshot(
                    product_name=product.name,
                    variant=variant,
                    materials=self.materials,
                    finishes=self.finishes,
                )
        return self


def seed_catalog():
    categories = [
        Category(id=i, name=n)
        for i, n in [
            ("print", "Communication imprimée et papeterie"),
            ("books", "Brochures et livres"),
            ("stickers", "Adhésifs et étiquettes"),
            ("signs", "Signalétique"),
            ("display", "PLV, stands et événementiel"),
            ("packaging", "Packaging et emballages"),
            ("textile", "Textile et objets personnalisés"),
            ("tickets", "Billetterie"),
        ]
    ]
    materials = [
        Material(id=i, name=n, family=f, gsm=g)
        for i, n, f, g in [
            ("mat350", "Couché mat 350 g/m²", "Papier", 350),
            ("mat135", "Couché mat 135 g/m²", "Papier", 135),
            ("offset", "Offset 90 g/m²", "Papier", 90),
            ("pvc", "Bâche PVC 510 g/m²", "Bâche", 510),
            ("vinyl", "Vinyle adhésif blanc", "Adhésif", None),
        ]
    ]
    finishes = [
        Finish(id="varnish", name="Vernis sélectif", mask=True, material_ids=["mat350"]),
        Finish(id="lamination", name="Pelliculage mat", material_ids=["mat350"]),
        Finish(id="fold", name="Pliage"),
        Finish(id="staple", name="Agrafage"),
        Finish(id="eyelets", name="Œillets"),
        Finish(id="perforation", name="Perforation"),
    ]

    def component(id, name, w, h, material, slots, guides, **kw):
        return Component(
            id=id,
            name=name,
            width=w,
            height=h,
            material_id=material,
            slots=[Slot(id=s[0], name=s[1], pages=s[2]) for s in slots],
            guides=[Guide(tool=t, settings=s) for t, s in guides],
            **kw,
        )

    def product(id, name, category, components, allowed, chosen=()):
        return Product(
            id=id,
            name=name,
            category_id=category,
            material_ids=list(dict.fromkeys(c.material_id for c in components)),
            finish_ids=allowed,
            variants=[
                Variant(
                    id="standard", name="Standard", components=components, finish_ids=list(chosen)
                )
            ],
        )

    products = [
        product(
            "card",
            "Carte recto verso",
            "print",
            [
                component(
                    "card",
                    "Carte",
                    85,
                    55,
                    "mat350",
                    [("front", "Recto", 1), ("back", "Verso", 1)],
                    [("pizza", {})],
                )
            ],
            ["varnish", "lamination"],
        ),
        product(
            "leaflet",
            "Dépliant pli roulé",
            "print",
            [
                component(
                    "leaflet",
                    "Dépliant",
                    297,
                    210,
                    "mat135",
                    [("front", "Extérieur", 1), ("back", "Intérieur", 1)],
                    [("taco", {"fold": "roll"})],
                )
            ],
            ["fold"],
            ["fold"],
        ),
        product(
            "brochure",
            "Brochure agrafée",
            "books",
            [
                component(
                    "cover", "Couverture", 148, 210, "mat350", [("cover", "Couverture", 4)], []
                ),
                component(
                    "inside", "Intérieur", 148, 210, "mat135", [("inside", "Intérieur", 8)], []
                ),
            ],
            ["staple"],
            ["staple"],
        ),
        product(
            "banner",
            "Bâche à œillets",
            "signs",
            [
                component(
                    "banner",
                    "Bâche",
                    2000,
                    1000,
                    "pvc",
                    [("front", "Visuel", 1)],
                    [("burrito", {})],
                )
            ],
            ["eyelets"],
            ["eyelets"],
        ),
        product(
            "label",
            "Étiquette découpée",
            "stickers",
            [
                component(
                    "label", "Étiquette", 85, 55, "vinyl", [("front", "Visuel", 1)], [("sushi", {})]
                )
            ],
            [],
        ),
        product(
            "ticket",
            "Billet détachable numéroté",
            "tickets",
            [
                component(
                    "ticket",
                    "Billet et souche",
                    150,
                    70,
                    "offset",
                    [("front", "Recto", 1)],
                    [("perforation", {"positions": [30]})],
                    tickets=Tickets(
                        placements=[SerialPlacement(x=5, y=60), SerialPlacement(x=40, y=60)]
                    ),
                )
            ],
            ["perforation", "staple"],
            ["perforation"],
        ),
    ]
    for component in next(p for p in products if p.id == "brochure").variants[0].components:
        component.page_multiple = 4
    return PrintCatalog(
        categories=categories, materials=materials, finishes=finishes, products=products
    )


def snapshot_slots(snapshot):
    """Stable ordered file contract, including option-generated masks."""
    result = []
    for component in snapshot.variant.components:
        for slot in component.slots:
            result.append((component, slot))
        for finish in snapshot.finishes:
            if finish.id in snapshot.variant.finish_ids and finish.mask:
                pages = sum(s.pages for s in component.slots if s.role == "visual")
                result.append(
                    (
                        component,
                        Slot(id=f"mask-{finish.id}", name=finish.name, role="mask", pages=pages),
                    )
                )
    return result
