import json
from xml.etree import ElementTree as ET

import numpy as np
import pikepdf
import pytest
from PIL import Image
from shapely import box
from snackpress_tools.biscuit import cut_geometry
from snackpress_tools.biscuit_svg import read_svg
from snackpress_tools.catalog import Biscuit
from snackpress_tools.runner import run
from test_api import api  # noqa: F401


@pytest.mark.parametrize("offset,expected", [(3, (91, 61)), (0, (85, 55)), (-2, (81, 51))])
def test_signed_offset_and_matching_exports(tmp_path, offset, expected):
    settings = dict(radius=0, offset=offset, smoothing=0, join="mitre")
    result = run(tmp_path, "biscuit", [], settings)
    assert result.metrics["Largeur de découpe (mm)"] == expected[0]
    assert result.metrics["Hauteur de découpe (mm)"] == expected[1]
    svg = ET.parse(tmp_path / "decoupe.svg").getroot()
    assert svg.get("width").endswith("mm")
    path = svg.find("{http://www.w3.org/2000/svg}path")
    assert path.get("d").endswith(" Z")
    with pikepdf.open(tmp_path / "decoupe.pdf") as pdf:
        page = pdf.pages[0]
        assert not pdf.check_pdf_syntax()
        assert "/XObject" not in page.Resources
        assert any(str(color[1]) == "/CutContour" for _, color in page.Resources.ColorSpace.items())
        assert any(bool(state.get("/OP", False)) for _, state in page.Resources.ExtGState.items())
        # Same coordinates, inverse y-axis, and physical scale in the SVG and PDF.
        assert float(page.MediaBox[2]) / (72 / 25.4) == pytest.approx(
            float(svg.get("width")[:-2]), abs=0.001
        )
        assert any(str(op) == "h" for _, op in pikepdf.parse_content_stream(page))


def test_negative_offset_disappearance_and_split(tmp_path):
    with pytest.raises(ValueError, match="disparaître"):
        run(tmp_path, "biscuit", [], dict(width=10, height=10, radius=0, offset=-6))
    svg = tmp_path / "bridge.svg"
    svg.write_text('<svg><path d="M0 0H10V4H20V0H30V10H20V6H10V10H0Z"/></svg>')
    result = run(tmp_path, "biscuit", [svg], dict(source="svg", width=30, offset=-1.1, smoothing=0))
    assert result.metrics["Contours fermés"] == 2
    assert any("nombre de contours" in warning for warning in result.warnings)


def test_image_alpha_and_holes(tmp_path):
    image = np.zeros((100, 100, 4), dtype=np.uint8)
    image[10:90, 10:90] = [200, 30, 50, 255]
    image[35:65, 35:65, 3] = 0
    path = tmp_path / "ring.png"
    Image.fromarray(image).save(path)
    for holes, area in [("keep", 55), ("fill", 64)]:
        p = Biscuit(source="image", width=10, offset=0, smoothing=0, holes=holes)
        source, result, _, _, _ = cut_geometry([path], p)
        assert source.area == pytest.approx(area)
        assert result.bounds == pytest.approx((1, 1, 9, 9))
    p = Biscuit(source="image", width=10, offset=1, smoothing=0, holes="keep")
    _, result, _, _, _ = cut_geometry([path], p)
    assert len(result.interiors) == 1
    assert box(*result.interiors[0].bounds).area == pytest.approx(1)


def test_white_background_and_noise_filter(tmp_path):
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    image[20:80, 10:90] = 0
    image[2, 2] = 0
    path = tmp_path / "white.jpg"
    Image.fromarray(image).save(path, quality=100, subsampling=0)
    p = Biscuit(source="image", width=100, offset=0, smoothing=0, min_area=2)
    _, result, _, _, _ = cut_geometry([path], p)
    assert result.bounds == pytest.approx((10, 20, 90, 80))


@pytest.mark.parametrize("rule,area", [("evenodd", 64), ("nonzero", 100)])
def test_svg_fill_rules_groups_curves_and_transform(tmp_path, rule, area):
    path = tmp_path / "ring.svg"
    path.write_text(
        f'<svg><g transform="translate(20 30) scale(2)" fill-rule="{rule}">'
        '<path d="M0 0H10V10H0Z M2 2H8V8H2Z"/></g></svg>'
    )
    result = read_svg(path)
    assert result.area == pytest.approx(area * 4)
    assert result.bounds == (20, 30, 40, 50)
    path.write_text('<svg><path d="M0 0 C0 10 10 10 10 0 L0 0 Z"/></svg>')
    assert read_svg(path).area == pytest.approx(60, abs=0.15)


@pytest.mark.parametrize(
    "content",
    [
        '<svg><path d="M0 0L10 10"/></svg>',
        "<svg><script>alert(1)</script></svg>",
        '<svg><image href="https://example.com/x.png"/></svg>',
        '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg/>',
        '<svg><rect width="10" height="10" clip-path="url(#x)"/></svg>',
        '<svg><path d="M0 0L10 10L0 10L10 0Z"/></svg>',
    ],
)
def test_unsupported_or_unsafe_svg_is_rejected(tmp_path, content):
    path = tmp_path / "bad.svg"
    path.write_text(content)
    with pytest.raises(ValueError):
        read_svg(path)


def test_svg_roundtrip_preserves_holes(tmp_path):
    source = tmp_path / "source.svg"
    source.write_text('<svg><path fill-rule="evenodd" d="M0 0H20V20H0Z M5 5H15V15H5Z"/></svg>')
    result = run(
        tmp_path,
        "biscuit",
        [source],
        dict(source="svg", width=20, offset=0, smoothing=0, holes="keep"),
    )
    assert result.metrics["Contours fermés"] == 2
    assert read_svg(tmp_path / "decoupe.svg").area == pytest.approx(300)


def test_api_upload_preview_download_and_validation(api):  # noqa: F811
    client, _ = api
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="20" height="10"/></svg>'
    settings = dict(source="svg", width=80, offset=-2, smoothing=0)
    upload = {"files": ("shape.svg", raw, "image/svg+xml")}
    result = client.post(
        "/api/tools/biscuit/run", files=upload, data={"settings": json.dumps(settings)}
    )
    assert result.status_code == 201, result.text
    result = result.json()
    assert result["metrics"]["Largeur de découpe (mm)"] == 76
    file = client.get(f"/api/tool-jobs/{result['id']}/files/decoupe.svg")
    assert file.status_code == 200
    assert file.headers["content-type"].startswith("image/svg+xml")
    assert b"CutContour" in file.content and b"<script" not in file.content
    session = client.post("/api/tools/biscuit/previews", files=upload).json()
    preview = client.post(f"/api/tool-previews/{session['id']}/render", json={"settings": settings})
    assert preview.status_code == 200, preview.text
    assert preview.json()["metrics"] == result["metrics"]
    assert (
        client.post("/api/tools/biscuit/run", data={"settings": '{"source":"image"}'}).status_code
        == 422
    )
    assert (
        client.post("/api/tools/biscuit/run", data={"settings": '{"offset":101}'}).status_code
        == 422
    )
