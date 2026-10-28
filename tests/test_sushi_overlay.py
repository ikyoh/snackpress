import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf
from reportlab.lib.units import mm
from snackpress_tools.runner import run


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("unit", [1, 2])
def test_overlay_preserves_artwork_boxes_and_adds_named_rectangle(tmp_path, rotation, unit):
    source = tmp_path / "source.pdf"
    make_pdf(source, origin=(30, -20), rotation=rotation)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.docinfo.Title = "Source conservée"
        for page in pdf.pages:
            page.UserUnit = unit
            # The source leaves its CTM and clipping changed: the contour must be isolated.
            page.contents_add(b"2 0 0 2 0 0 cm 0 0 1 1 re W n")
        pdf.save(source)
    original = source.read_bytes()
    settings = {"cut_name": "Découpe / atelier #1", "pdf_inset": 2, "cut_width": 0.2}
    result = run(tmp_path, "sushi", [source], settings)
    assert result.metrics["Rectangles de découpe"] == 2
    assert source.read_bytes() == original
    with pikepdf.open(source) as before, pikepdf.open(tmp_path / "contours.pdf") as after:
        assert len(after.pages) == len(before.pages)
        assert after.docinfo.Title == before.docinfo.Title
        for old, page in zip(before.pages, after.pages, strict=True):
            assert list(page.MediaBox) == list(old.MediaBox)
            assert list(page.TrimBox) == list(old.TrimBox)
            assert int(page.obj.get("/Rotate", 0)) == rotation
            assert int(page.UserUnit) == unit
            assert page.Resources.Font == old.Resources.Font
            assert "/XObject" not in page.Resources
            space = next(value for _, value in page.Resources.ColorSpace.items())
            assert str(space[0]) == "/Separation"
            assert str(space[1]) == "/Découpe / atelier #1"
            assert list(space[3].C1) == [0, 1, 0, 0]
            state = next(value for _, value in page.Resources.ExtGState.items())
            assert state.OP and int(state.OPM) == 1
            commands = list(pikepdf.parse_content_stream(page))
            rectangles = [list(map(float, args)) for args, op in commands if str(op) == "re"]
            assert rectangles[-1] == pytest.approx(
                [
                    30 + 3 * mm + 2 * mm / unit,
                    -20 + 3 * mm + 2 * mm / unit,
                    85 * mm - 4 * mm / unit,
                    55 * mm - 4 * mm / unit,
                ]
            )
            stroke = [float(args[0]) for args, op in commands if str(op) == "w"][-1]
            assert stroke == pytest.approx(0.2 * mm / unit)
            assert str(commands[-2][1]) == "S"
    # Actual PDF rendering checks both visible text and unchanged interior artwork.
    with (
        pdfium.PdfDocument(source) as before,
        pdfium.PdfDocument(tmp_path / "contours.pdf") as after,
    ):
        for index in range(len(before)):
            assert (
                before[index].get_textpage().get_text_range()
                == after[index].get_textpage().get_text_range()
            )
            first, second = before[index].render(scale=2), after[index].render(scale=2)
            a, b = np.array(first.to_pil()), np.array(second.to_pil())
            assert a.shape == b.shape
            assert np.any(a != b)
            # The rectangle is near the edges; the page interior must remain identical.
            assert np.array_equal(a[40:-40, 40:-40], b[40:-40, 40:-40])
            first.close()
            second.close()


@pytest.mark.parametrize("trim,reference", [(False, "trim"), (True, "page")])
def test_overlay_page_edge_and_missing_trim_fallback(tmp_path, trim, reference):
    source = tmp_path / "source.pdf"
    make_pdf(source, trim=trim)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        pdf.pages[0].CropBox = pikepdf.Array([mm, mm, 90 * mm, 60 * mm])
        pdf.save(source)
    result = run(tmp_path, "sushi", [source], {"pdf_box": reference})
    assert any("TrimBox absente" in warning for warning in result.warnings) == (not trim)
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        rectangles = [
            args for args, op in pikepdf.parse_content_stream(pdf.pages[0]) if str(op) == "re"
        ]
        assert list(map(float, rectangles[-1])) == pytest.approx([mm, mm, 89 * mm, 59 * mm])


def test_overlay_shared_resources_and_different_page_sizes(tmp_path):
    source = tmp_path / "source.pdf"
    make_pdf(source)
    with pikepdf.open(source, allow_overwriting_input=True) as pdf:
        shared = pdf.make_indirect(pikepdf.Dictionary(pdf.pages[0].Resources))
        shared.ColorSpace = pikepdf.Dictionary(Existing=pikepdf.Name.DeviceCMYK)
        for page in pdf.pages:
            page.Resources = shared
        pdf.pages[1].MediaBox = pikepdf.Array([0, 0, 120 * mm, 90 * mm])
        pdf.pages[1].TrimBox = pikepdf.Array([5 * mm, 5 * mm, 115 * mm, 85 * mm])
        pdf.save(source)
    run(tmp_path, "sushi", [source], {})
    with pikepdf.open(tmp_path / "contours.pdf") as pdf:
        for index, page in enumerate(pdf.pages):
            spaces = [value for _, value in page.Resources.ColorSpace.items()]
            assert len(spaces) == 2
            assert str(page.Resources.ColorSpace.Existing) == "/DeviceCMYK"
            rect = [args for args, op in pikepdf.parse_content_stream(page) if str(op) == "re"][-1]
            assert float(rect[2]) / mm == pytest.approx(85 if index == 0 else 110)


def test_overlay_rejects_excessive_inset_and_invalid_pdf(tmp_path, source):
    with pytest.raises(ValueError, match="retrait"):
        run(tmp_path, "sushi", [source], {"pdf_inset": 28})
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"%PDF-invalid")
    with pytest.raises(ValueError, match="illisible"):
        run(tmp_path, "sushi", [invalid], {})


@pytest.mark.parametrize(
    "settings",
    [
        {"cut_name": "   "},
        {"cut_name": "All"},
        {"cut_name": "None"},
        {"cut_width": 0},
        {"cut_width": float("nan")},
        {"pdf_inset": -1},
        {"pdf_box": "other"},
    ],
)
def test_overlay_rejects_invalid_settings(tmp_path, source, settings):
    with pytest.raises(ValueError):
        run(tmp_path, "sushi", [source], settings)
