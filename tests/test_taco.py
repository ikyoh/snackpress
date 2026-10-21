import pikepdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.units import mm
from snackpress_tools.catalog import Taco
from snackpress_tools.common import new_canvas, render_page
from snackpress_tools.runner import run
from snackpress_tools.taco_layout import (
    face_label,
    face_panels,
    fold_positions,
    fold_widths,
    reference_corner,
)


def test_roll_front_back_keep_physical_panel_identity():
    p = Taco(fold="roll")
    assert fold_widths(p) == [101, 99, 97]
    assert fold_positions(p, "recto") == [101, 200]
    assert fold_positions(p, "verso") == [97, 196]
    assert [panel.number for panel in face_panels(p, "verso")] == [3, 2, 1]
    assert [(panel.number, panel.width) for panel in face_panels(p, "recto")] == list(
        reversed([(panel.number, panel.width) for panel in face_panels(p, "verso")])
    )
    assert [panel.number for panel in face_panels(p, "recto") if panel.flap] == [3]
    assert [panel.number for panel in face_panels(p, "verso") if panel.flap] == [3]


def test_turns_and_flap_side_are_independent():
    p = Taco(fold="roll", flap_side="left", turn="top_bottom", recto_face="inside")
    assert fold_widths(p) == [97, 99, 101]
    assert fold_positions(p, "recto") == fold_positions(p, "verso") == [97, 196]
    assert reference_corner(p, "recto") == (0, 210)
    assert reference_corner(p, "verso") == (0, 0)
    assert reference_corner(Taco(), "verso") == (297, 210)
    assert face_label(p, "recto") == "Recto — Intérieur"
    assert face_label(p, "verso") == "Verso — Extérieur"
    assert [panel.number for panel in face_panels(p, "verso") if panel.flap] == [1]


@pytest.mark.parametrize("fold", ["accordion", "roll", "gate"])
@pytest.mark.parametrize("panels", [2, 3, 4, 8])
@pytest.mark.parametrize("turn", ["left_right", "top_bottom"])
def test_both_faces_share_one_geometry(fold, panels, turn):
    p = Taco(width=500, panels=panels, fold=fold, turn=turn)
    recto, verso = face_panels(p, "recto"), face_panels(p, "verso")
    assert sum(panel.width for panel in recto) == pytest.approx(500)
    assert sum(panel.width for panel in verso) == pytest.approx(500)
    assert {panel.number: panel.width for panel in recto} == {
        panel.number: panel.width for panel in verso
    }
    if fold == "gate":
        assert {panel.number for panel in verso if panel.flap} == {1, 4}
    if fold == "accordion":
        assert all(not panel.flap for panel in recto)


def has_coral(image, x_mm, y_mm, page_height_mm):
    x, y = round(x_mm * 144 / 25.4), round((page_height_mm - y_mm) * 144 / 25.4)
    crop = image.crop((x - 2, y - 2, x + 3, y + 3))
    return any(
        r > 150 and r > g * 1.25 and g > b
        for r, g, b in (crop.getpixel((col, row)) for col in range(5) for row in range(5))
    )


def test_export_has_two_named_faces_and_visible_corresponding_folds(tmp_path):
    result = run(tmp_path, "taco", [], {"fold": "roll"})
    assert result.artifacts[0].pages == 2
    path = tmp_path / "plan-pliage.pdf"
    with pdfium.PdfDocument(str(path)) as pdf:
        for index, label in enumerate(["Recto — Extérieur", "Verso — Intérieur"]):
            text = pdf[index].get_textpage().get_text_range()
            assert label in text
            assert "Rabat rentrant" in text
            assert f"Page {index + 1} / 2" in text
    for index, positions in enumerate([[101, 200], [97, 196]]):
        image, _ = render_page(path, index, dpi=144)
        for position in positions:
            assert has_coral(image, 15 + position, 16.5, 240)
            assert not has_coral(image, 15 + position, 19, 240), (
                "Les plis doivent rester en pointillés."
            )
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            assert [float(n) / mm for n in page.trimbox] == pytest.approx([15, 15, 312, 225])
    with pdfium.PdfDocument(str(tmp_path / "fiche-pliage.pdf")) as pdf:
        text = "\n".join(page.get_textpage().get_text_range() for page in pdf)
        assert "101 mm / 200 mm" in text
        assert "97 mm / 196 mm" in text
        assert "Roulé" in text and "Gauche-droite" in text


def artwork(folder, name, pages):
    path = folder / name
    c = new_canvas(path, 297, 210)
    for index in range(pages):
        c.drawString(20, 30, f"Visuel {index + 1}")
        c.showPage()
    c.save()
    return path


def stroke_positions(form):
    return [
        float(args[0]) / mm - 15
        for args, op in pikepdf.parse_content_stream(form)
        if str(op) == "m" and len(args) == 2 and abs(float(args[1]) / mm - 15) < 0.01
    ]


@pytest.mark.parametrize("split", [False, True])
def test_burger_alternates_front_back_across_artwork_files_and_pages(tmp_path, split):
    files = [
        artwork(tmp_path, f"visuel-{i}.pdf", 1 if split else 2) for i in range(2 if split else 1)
    ]
    files.append(artwork(tmp_path, "masque.pdf", 2))
    out = tmp_path / "bat"
    out.mkdir()
    run(
        out,
        "burger",
        files,
        {
            "expected_files": 2 if split else 1,
            "finishes": ["Vernis"],
            "template_tool": "taco",
            "template_settings": {"fold": "roll"},
        },
    )
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert len(pdf.pages) == 4
        for index, expected in enumerate([[101, 200], [97, 196]] * 2):
            forms = [
                obj
                for obj in dict(pdf.pages[index].Resources.XObject).values()
                if obj.Subtype == "/Form"
            ]
            assert len(forms) == 1
            assert stroke_positions(forms[0]) == pytest.approx(expected)


def test_imported_duplex_template_keeps_back_guides(tmp_path):
    guide = tmp_path / "taco"
    guide.mkdir()
    run(guide, "taco", [], {"fold": "roll"})
    source = artwork(tmp_path, "visuel.pdf", 2)
    out = tmp_path / "burger"
    out.mkdir()
    run(out, "burger", [source, guide / "plan-pliage.pdf"], {"template_tool": "pdf"})
    with pikepdf.open(out / "bat.pdf") as pdf:
        form = next(
            obj for obj in dict(pdf.pages[1].Resources.XObject).values() if obj.Subtype == "/Form"
        )
        assert stroke_positions(form) == pytest.approx([97, 196])


def test_duplex_template_refuses_incompatible_back_dimensions(tmp_path):
    source = artwork(tmp_path, "visuel.pdf", 1)
    guide = artwork(tmp_path, "gabarit.pdf", 2)
    with pikepdf.open(guide, allow_overwriting_input=True) as pdf:
        pdf.pages[1].MediaBox = pikepdf.Array([0, 0, 100 * mm, 100 * mm])
        pdf.save(guide)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError, match="mêmes formats"):
        run(out, "burger", [source, guide], {"template_tool": "pdf"})
