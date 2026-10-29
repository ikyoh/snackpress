import importlib
import json
from collections import Counter
from io import BytesIO
from random import Random

import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.lib.units import mm
from snackpress_tools.catalog import Granola, GranolaItem
from snackpress_tools.granola import pack
from snackpress_tools.preview import render
from snackpress_tools.runner import run


def check_layout(sheets, sizes, items, params):
    counts = Counter()
    copies = set()
    for sheet in sheets:
        for i, pose in enumerate(sheet):
            counts[pose.file] += 1
            assert (pose.file, pose.copy) not in copies
            copies.add((pose.file, pose.copy))
            assert pose.x >= params.margin - 1e-6
            assert pose.y >= params.margin - 1e-6
            assert pose.x + pose.width <= params.sheet_width - params.margin + 1e-6
            assert pose.y + pose.height <= params.sheet_height - params.margin + 1e-6
            expected = sizes[pose.file][::-1] if pose.rotation else sizes[pose.file]
            assert (pose.width, pose.height) == pytest.approx(expected)
            for other in sheet[i + 1 :]:
                assert (
                    pose.x + pose.width + params.gap <= other.x + 1e-6
                    or other.x + other.width + params.gap <= pose.x + 1e-6
                    or pose.y + pose.height + params.gap <= other.y + 1e-6
                    or other.y + other.height + params.gap <= pose.y + 1e-6
                )
    assert counts == {i: item.quantity for i, item in enumerate(items)}


def test_mixed_formats_fill_one_sheet_instead_of_separate_grids():
    params = Granola(sheet_width=100, sheet_height=100, margin=0, gap=0)
    sizes = [(60, 60), (40, 60), (100, 40)]
    items = [GranolaItem()] * 3
    sheets = pack(sizes, items, params)
    assert len(sheets) == 1
    check_layout(sheets, sizes, items, params)


@pytest.mark.parametrize("rotation", ["auto", "none"])
def test_mixed_layout_invariants_with_fractional_sizes_and_gaps(rotation):
    rng = Random(702)
    for gap in (0, 0.25, 3.5, 11):
        params = Granola(sheet_width=210, sheet_height=297, margin=7.25, gap=gap, rotation=rotation)
        sizes = [(rng.uniform(15, 100), rng.uniform(15, 130)) for _ in range(12)]
        items = [GranolaItem(quantity=rng.randint(1, 15)) for _ in sizes]
        sheets = pack(sizes, items, params)
        check_layout(sheets, sizes, items, params)
        if rotation == "none":
            assert all(p.rotation == 0 for s in sheets for p in s)
        assert pack(sizes, items, params) == sheets


def test_exact_edge_fit_rotation_and_oversize():
    params = Granola(sheet_width=100, sheet_height=70, margin=5, gap=20)
    sheets = pack([(60, 90)], [GranolaItem(quantity=2)], params)
    assert len(sheets) == 2
    assert sheets[0][0].rotation == 90
    with pytest.raises(ValueError, match="ne tient pas"):
        pack([(60, 90)], [GranolaItem()], params.model_copy(update={"rotation": "none"}))
    with pytest.raises(ValueError, match="ne tient pas"):
        pack([(91, 61)], [GranolaItem()], params)


def test_rotation_optimizes_the_first_pose_on_a_new_sheet():
    params = Granola(sheet_width=100, sheet_height=200, margin=0, gap=0)
    items = [GranolaItem(quantity=3)]
    sheets = pack([(60, 100)], items, params)
    assert len(sheets) == 1
    assert all(p.rotation == 90 for p in sheets[0])
    check_layout(sheets, [(60, 100)], items, params)


@pytest.mark.parametrize(
    "settings",
    [
        {"margin": 100, "sheet_width": 100},
        {"sheet_width": 0},
        {"gap": -1},
        {"gap": float("nan")},
        {"items": [{"quantity": 0}]},
        {"items": [{"quantity": 1.5}]},
        {"items": [{"quantity": 1500}, {"quantity": 501}]},
        {"items": [{"page": 0}]},
        {"items": [{"image_width": 0}]},
    ],
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        Granola(**settings)


def test_sheet_limit_and_maximum_quantity():
    with pytest.raises(ValueError, match="200 planches"):
        pack(
            [(100, 100)],
            [GranolaItem(quantity=201)],
            Granola(sheet_width=100, sheet_height=100, margin=0, gap=0),
        )
    params = Granola(items=[GranolaItem(quantity=2000)])
    sheets = pack([(10, 10)], params.items, params)
    check_layout(sheets, [(10, 10)], params.items, params)


def test_pdf_png_jpeg_quantities_sizes_native_content_and_preview(tmp_path):
    source = tmp_path / "source.pdf"
    make_pdf(source)
    png, jpeg = tmp_path / "source.png", tmp_path / "source.jpg"
    Image.new("RGB", (400, 200), "red").save(png)
    Image.new("RGB", (100, 300), "blue").save(jpeg)
    settings = {
        "sheet_width": 210,
        "sheet_height": 297,
        "items": [
            {"quantity": 12, "page": 2},
            {"quantity": 9, "image_width": 80},
            {"quantity": 7, "image_width": 30},
        ],
    }
    final, preview = tmp_path / "final", tmp_path / "preview"
    final.mkdir()
    preview.mkdir()
    result = run(final, "granola", [source, png, jpeg], settings)
    render(preview, "granola", [source, png, jpeg], settings)
    data = json.loads((final / "plan-imposition.json").read_text())
    assert [s["width"] for s in data["sources"]] == pytest.approx([91, 80, 30])
    assert [s["height"] for s in data["sources"]] == pytest.approx([61, 40, 90])
    assert data == json.loads((preview / "plan-imposition.json").read_text())
    assert Counter(p["file"] for sheet in data["sheets"] for p in sheet) == {0: 12, 1: 9, 2: 7}
    assert result.metrics["Exemplaires"] == 28
    assert result.metrics["Planches"] == len(data["sheets"])
    with pikepdf.open(final / "imposition.pdf") as pdf:
        assert len(pdf.pages) == len(data["sheets"])
        assert all(
            list(map(float, p.mediabox)) == pytest.approx([0, 0, 210 * mm, 297 * mm])
            for p in pdf.pages
        )
        assert not pdf.check_pdf_syntax()
        assert any(
            form.get("/Resources", {}).get("/Font")
            for page in pdf.pages
            for _, form in page.Resources.XObject.items()
        )
    with pdfium.PdfDocument(str(final / "imposition.pdf")) as pdf:
        text = "".join(p.get_textpage().get_text_range() for p in pdf)
        assert text.count("VERSO") == 12
        assert "RECTO" not in text
    with pikepdf.open(preview / "imposition.pdf") as pdf:
        assert len(pdf.pages) == min(2, len(data["sheets"]))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("unit", [1, 2])
def test_pdf_origin_crop_and_rotation_preserve_visible_artwork(tmp_path, rotation, unit):
    source = tmp_path / "quadrants.pdf"
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(120, 100))
        page.MediaBox = pikepdf.Array([10, 20, 130, 120])
        page.CropBox = pikepdf.Array([20, 30, 120, 110])
        page.Rotate = rotation
        page.UserUnit = unit
        page.Contents = pikepdf.Stream(
            pdf,
            b"1 0 0 rg 20 30 50 40 re f "
            b"0 1 0 rg 70 30 50 40 re f "
            b"0 0 1 rg 20 70 50 40 re f "
            b"1 1 0 rg 70 70 50 40 re f",
        )
        pdf.save(source)
    folder = tmp_path / "out"
    folder.mkdir()
    run(folder, "granola", [source], {"rotation": "none"})
    with (
        pdfium.PdfDocument(str(source)) as src,
        pdfium.PdfDocument(str(folder / "imposition.pdf")) as dest,
    ):
        a, b = src[0].render(scale=2), dest[0].render(scale=2)
        original, imposed = a.to_pil().convert("RGB"), b.to_pil().convert("RGB")
        # PDFium reports the source size without UserUnit; the imposed page uses points.
        for x in (0.25, 0.75):
            for y in (0.25, 0.75):
                pixel = original.getpixel((int(original.width * x), int(original.height * y)))
                assert (
                    imposed.getpixel(
                        (
                            round(10 * mm * 2 + original.width * unit * x),
                            round((450 - 10) * mm * 2 - original.height * unit * (1 - y)),
                        )
                    )
                    == pixel
                )
        a.close()
        b.close()


def test_missing_page_mismatched_items_and_annotations(tmp_path, source):
    folder = tmp_path / "out"
    folder.mkdir()
    with pytest.raises(ValueError, match="n’existe pas"):
        run(folder, "granola", [source], {"items": [{"page": 3}]})
    with pytest.raises(ValueError, match="chaque fichier"):
        run(folder, "granola", [source, source], {"items": [{"quantity": 1}]})
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].Annots = pikepdf.Array([pikepdf.Dictionary(Subtype=pikepdf.Name.Text)])
        pdf.save(source)
    with pytest.raises(ValueError, match="annotations"):
        run(folder, "granola", [source], {})


def test_api_import_preview_export_download_and_invalid_quantity(tmp_path, monkeypatch, source):
    monkeypatch.setenv("SNACKPRESS_DATA", str(tmp_path / "data"))
    import snackpress_api.main as module

    module = importlib.reload(module)
    buf = BytesIO()
    Image.new("RGB", (200, 100), "green").save(buf, format="PNG")
    files = [
        ("files", ("card.pdf", source.read_bytes(), "application/pdf")),
        ("files", ("label.png", buf.getvalue(), "image/png")),
    ]
    settings = {"items": [{"quantity": 7, "page": 2}, {"quantity": 3, "image_width": 40}]}
    with TestClient(module.app) as client:
        preview = client.post("/api/tools/granola/previews", files=files)
        assert preview.status_code == 201, preview.text
        preview_id = preview.json()["id"]
        response = client.post(
            f"/api/tool-previews/{preview_id}/render", json={"settings": settings}
        )
        assert response.status_code == 200, response.text
        assert response.json()["metrics"]["Exemplaires"] == 10
        response = client.post(
            "/api/tools/granola/run", files=files, data={"settings": json.dumps(settings)}
        )
        assert response.status_code == 201, response.text
        result = response.json()
        download = client.get(f"/api/tool-jobs/{result['id']}/files/imposition.pdf")
        assert download.status_code == 200
        with pikepdf.open(BytesIO(download.content)) as pdf:
            assert len(pdf.pages) == result["metrics"]["Planches"]
        invalid = client.post(
            "/api/tools/granola/run",
            files=files,
            data={"settings": json.dumps({"items": [{"quantity": 0}]})},
        )
        assert invalid.status_code == 422
        assert client.delete(f"/api/tool-previews/{preview_id}").status_code == 204
        assert client.delete(f"/api/tool-jobs/{result['id']}").status_code == 204


def test_compact_search_reduces_the_common_sheet_area():
    from snackpress_tools.granola import tight_size

    params = Granola(sheet_width=320, sheet_height=450, margin=10, gap=3)
    sizes, items = [(80, 40)], [GranolaItem(quantity=4)]
    sheets = pack(sizes, items, params)
    assert len(sheets) == 1
    width, height = tight_size(sheets, params.margin)
    # A two-by-two arrangement needs at most 183 × 103 mm, margins included.
    assert width * height <= 183 * 103
    check_layout(sheets, sizes, items, params)


@pytest.mark.parametrize("crop,outer", [("none", 10), ("margin", 10), ("poses", 0)])
def test_crop_preserves_native_artwork_and_exact_geometry(tmp_path, source, crop, outer):
    from snackpress_tools.granola import Pose

    folder = tmp_path / crop
    folder.mkdir()
    settings = {
        "rotation": "none",
        "margin": 10,
        "gap": 3,
        "crop": crop,
        "items": [{"quantity": 4, "page": 2}],
    }
    result = run(folder, "granola", [source], settings)
    data = json.loads((folder / "plan-imposition.json").read_text())
    expected = data["sheet_format"]["output"]
    assert data["sheet_format"]["original"] == {"width": 320, "height": 450}
    assert result.metrics["Exemplaires"] == 4
    check_layout(
        [[Pose(**p) for p in sheet] for sheet in data["sheets"]],
        [(91, 61)],
        [GranolaItem(quantity=4)],
        Granola(
            sheet_width=expected["width"], sheet_height=expected["height"], margin=outer, gap=3
        ),
    )
    with pikepdf.open(folder / "imposition.pdf") as pdf:
        assert not pdf.check_pdf_syntax()
        for page in pdf.pages:
            assert list(map(float, page.mediabox)) == pytest.approx(
                [0, 0, expected["width"] * mm, expected["height"] * mm]
            )
    with pdfium.PdfDocument(str(folder / "imposition.pdf")) as pdf:
        assert sum(p.get_textpage().get_text_range().count("VERSO") for p in pdf) == 4
    if crop != "none":
        assert expected["width"] * expected["height"] < 320 * 450
        assert min(p["x"] for s in data["sheets"] for p in s) == pytest.approx(outer)
        assert min(p["y"] for s in data["sheets"] for p in s) == pytest.approx(outer)
        pose_width = max(p["x"] + p["width"] for s in data["sheets"] for p in s)
        pose_height = max(p["y"] + p["height"] for s in data["sheets"] for p in s)
        assert expected["width"] == pytest.approx(pose_width + outer, abs=0.01)
        assert expected["height"] == pytest.approx(pose_height + outer, abs=0.01)


def test_crop_does_not_repack_or_change_the_quantities(tmp_path, source):
    plans = []
    for crop in ("none", "margin", "poses"):
        folder = tmp_path / crop
        folder.mkdir()
        run(folder, "granola", [source], {"crop": crop, "items": [{"quantity": 18}]})
        plans.append(json.loads((folder / "plan-imposition.json").read_text()))
    assert plans[0]["sheets"] == plans[1]["sheets"]
    for before, after in zip(plans[0]["sheets"], plans[2]["sheets"], strict=True):
        for a, b in zip(before, after, strict=True):
            assert {k: v for k, v in a.items() if k not in ("x", "y")} == {
                k: v for k, v in b.items() if k not in ("x", "y")
            }
            assert b["x"] == pytest.approx(a["x"] - 10)
            assert b["y"] == pytest.approx(a["y"] - 10)


def test_cropped_preview_and_all_output_pages_share_the_same_format(tmp_path):
    from snackpress_tools.granola import Pose

    big, small = tmp_path / "big.png", tmp_path / "small.png"
    Image.new("RGB", (90, 60), "red").save(big)
    Image.new("RGB", (35, 50), "blue").save(small)
    settings = {
        "sheet_width": 120,
        "sheet_height": 100,
        "margin": 5,
        "gap": 3,
        "crop": "margin",
        "rotation": "none",
        "items": [{"quantity": 3, "image_width": 90}, {"quantity": 8, "image_width": 35}],
    }
    folders = [tmp_path / "final", tmp_path / "preview"]
    for folder in folders:
        folder.mkdir()
    run(folders[0], "granola", [big, small], settings)
    render(folders[1], "granola", [big, small], settings)
    plan = json.loads((folders[0] / "plan-imposition.json").read_text())
    assert plan == json.loads((folders[1] / "plan-imposition.json").read_text())
    assert len(plan["sheets"]) > 2
    size = plan["sheet_format"]["output"]
    check_layout(
        [[Pose(**p) for p in s] for s in plan["sheets"]],
        [(90, 60), (35, 50)],
        [GranolaItem(quantity=3), GranolaItem(quantity=8)],
        Granola(sheet_width=size["width"], sheet_height=size["height"], margin=5, gap=3),
    )
    for index, folder in enumerate(folders):
        with pikepdf.open(folder / "imposition.pdf") as pdf:
            assert len(pdf.pages) == (len(plan["sheets"]) if index == 0 else 2)
            for page in pdf.pages:
                assert list(map(float, page.mediabox)) == pytest.approx(
                    [0, 0, size["width"] * mm, size["height"] * mm]
                )


@pytest.mark.parametrize("crop", ["margin", "poses"])
def test_fractional_crop_rounds_outward_and_never_exceeds_the_input_sheet(tmp_path, crop):
    source = tmp_path / "fractional.pdf"
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(210.001 * mm, 29.123456 * mm))
        page.Contents = pikepdf.Stream(pdf, b"0 0 1 rg 0 0 1000 1000 re f")
        pdf.save(source)
    folder = tmp_path / "out"
    folder.mkdir()
    result = run(
        folder,
        "granola",
        [source],
        {
            "sheet_width": 210.001,
            "sheet_height": 297,
            "margin": 0,
            "rotation": "none",
            "crop": crop,
        },
    )
    assert result.metrics["Largeur avec marge (mm)"] == 210.001
    assert result.metrics["Hauteur avec marge (mm)"] == 29.13
    with pikepdf.open(folder / "imposition.pdf") as pdf:
        assert float(pdf.pages[0].mediabox[2]) / mm == pytest.approx(210.001)
        assert float(pdf.pages[0].mediabox[3]) / mm >= 29.123456
