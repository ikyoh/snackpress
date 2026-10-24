import base64
from copy import deepcopy
from io import BytesIO

import pikepdf
import pytest
from PIL import Image
from snackpress_tools.catalog import Fortune
from snackpress_tools.fortune_product import placement_guides
from snackpress_tools.products import Component
from snackpress_tools.runner import run
from test_accounts import account_api  # noqa: F401


def snapshot(*guides):
    return {
        "product_name": "Produit de test",
        "variant": {
            "id": "test",
            "name": "100 × 60",
            "components": [
                {
                    "id": "front",
                    "name": "Face",
                    "width": 100,
                    "height": 60,
                    "bleed": 4,
                    "guides": list(guides),
                },
                {"id": "back", "name": "Autre composant", "width": 80, "height": 50},
            ],
        },
    }


def test_product_format_wins_over_manual_and_legacy_pizza_settings():
    params = Fortune(
        width=85,
        height=55,
        bleed=3,
        pizza_template={"width": 120, "height": 120},
        product_snapshot=snapshot(),
    )
    assert (params.width, params.height, params.bleed) == (100, 60, 4)
    assert params.product_component_id == "front"
    assert params.pizza_template is None
    restored = Fortune.model_validate(params.model_dump())
    assert (restored.width, restored.height, restored.bleed) == (100, 60, 4)
    settings = params.model_dump()
    settings["product_component_id"] = "back"
    params = Fortune.model_validate(settings)
    assert (params.width, params.height, params.bleed) == (80, 50, 3)
    with pytest.raises(ValueError, match="composant présent"):
        Fortune(product_snapshot=snapshot(), product_component_id="absent")


@pytest.mark.parametrize("tool", ["pizza", "burrito", "sushi", "taco"])
def test_product_guides_are_transparent_and_excluded_from_output(tmp_path, tool):
    settings = {
        "pizza": {"shape": "ellipse", "safety": 5},
        "burrito": {"hem": 5, "inset": 5},
        "sushi": {"shape": "rectangle", "lines": [{"position": 30}]},
        "taco": {"panels": 3},
    }[tool]
    product = snapshot({"tool": tool, "settings": settings})
    params = Fortune(count=1, product_snapshot=product, repiquages=[])
    component = params.product_snapshot.variant.components[0]
    work = tmp_path / "guides"
    work.mkdir()
    guides = placement_guides(work, component)
    image = Image.open(BytesIO(base64.b64decode(guides["url"].split(",", 1)[1])))
    assert image.mode == "RGBA"
    assert max(image.size) <= 1600
    alpha = image.getchannel("A")
    assert alpha.getextrema() == (0, 255)  # Transparent artwork with visible guide strokes.
    assert alpha.histogram()[0] > image.width * image.height / 2
    assert guides["x"] == guides["y"] == (-15 if tool == "taco" else -4)
    assert guides["width"] == 100 - 2 * guides["x"]
    assert guides["height"] == 60 - 2 * guides["y"]
    # Choosing guides never paints them into the preview or production PDF.
    output = tmp_path / "output"
    output.mkdir()
    run(output, "fortune-cookie", [], params.model_dump())
    with pikepdf.open(output / "serie.pdf") as pdf:
        assert float(pdf.pages[0].MediaBox[2]) == pytest.approx(108 * 72 / 25.4)
        assert not any(
            str(op) in {"S", "s", "Do"} for _, op in pikepdf.parse_content_stream(pdf.pages[0])
        )


# Pytest discovers the imported account_api fixture.
def test_combined_guides_endpoint_and_size_limits(account_api):  # noqa: F811
    client, module, _ = account_api
    component = Component.model_validate(
        snapshot(
            {"tool": "pizza", "settings": {}},
            {"tool": "taco", "settings": {}},
            {"tool": "burrito", "settings": {"hem": 5, "inset": 5}},
            {"tool": "perforation", "settings": {"positions": [20]}},
        )["variant"]["components"][0]
    ).model_dump()
    response = client.post("/api/tools/fortune-cookie/guides", json=component)
    assert response.status_code == 200, response.text
    assert response.json()["width"] == 130
    assert response.json()["url"].startswith("data:image/png;base64,")
    invalid = deepcopy(component)
    invalid["width"] = 600
    response = client.post("/api/tools/fortune-cookie/guides", json=invalid)
    assert response.status_code == 422
    assert not list(module.DATA.glob("fortune-guides-*"))
