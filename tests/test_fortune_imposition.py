import json
import re

import pikepdf
import pypdfium2 as pdfium
import pytest
from snackpress_tools.catalog import Fortune
from snackpress_tools.fortune_imposition import cut_stack
from snackpress_tools.preview import render
from snackpress_tools.runner import run

PT = 72 / 25.4
LAYER = {"sheet_width": 210, "sheet_height": 150, "margin": 10, "gap": 6}


@pytest.mark.parametrize("count", [1, 7, 23, 60, 100])
@pytest.mark.parametrize("per_book", [1, 5, 25])
def test_cut_piles_form_complete_consecutive_books(count, per_book):
    sheets, batches = cut_stack(count, per_book, 4)
    gathered = []
    for batch in batches:
        stack = sheets[batch["first_sheet"] - 1 : batch["last_sheet"]]
        for pose in range(4):
            book = [sheet[pose] for sheet in stack if sheet[pose] is not None]
            if book:
                assert book == list(range(book[0], book[-1] + 1))
                assert len(book) == min(per_book, count - book[0])
                gathered.extend(book)
    assert gathered == list(range(count))


def test_pdf_numbering_is_physically_positioned_for_cutting_25_ticket_books(tmp_path):
    result = run(
        tmp_path,
        "fortune-cookie",
        [],
        {"count": 100, "tickets_per_book": 25, "layer_template": LAYER},
    )
    assert result.metrics["Feuilles à tirer"] == 25
    assert result.metrics["Souches"] == 4
    assert result.metrics["Poses"] == 4
    assert result.artifacts[0].name == "imposition.pdf"
    # Independently inspect the four physical cut piles, top-left to bottom-right.
    positions = [(17, 78), (108, 78), (17, 17), (108, 17)]
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        assert len(pdf) == 25
        for pose, (x, y) in enumerate(positions):
            pile = []
            for page in pdf:
                text = page.get_textpage().get_text_bounded(
                    x * PT, y * PT, (x + 85) * PT, (y + 55) * PT
                )
                pile.extend(map(int, re.findall(r"SP-(\d+)", text)))
            assert pile == list(range(1 + pose * 25, 26 + pose * 25))
    plan = json.loads((tmp_path / "plan-souches.json").read_text())
    assert plan["sheets"][0] == ["SP-0001", "SP-0026", "SP-0051", "SP-0076"]
    assert plan["sheets"][-1] == ["SP-0025", "SP-0050", "SP-0075", "SP-0100"]


def test_partial_book_and_multiple_cut_batches_do_not_repeat_tickets(tmp_path):
    result = run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 23,
            "start": 8,
            "prefix": "T-",
            "digits": 3,
            "tickets_per_book": 5,
            "layer_template": LAYER,
        },
    )
    assert result.metrics["Feuilles à tirer"] == 8
    assert result.metrics["Souches"] == 5
    assert result.metrics["Lots de coupe"] == 2
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        numbers = [
            int(n)
            for page in pdf
            for n in re.findall(r"T-(\d+)", page.get_textpage().get_text_range())
        ]
        assert sorted(numbers) == list(range(8, 31))
    plan = json.loads((tmp_path / "plan-souches.json").read_text())
    assert plan["sheets"][5:] == [[f"T-{i:03d}", None, None, None] for i in range(28, 31)]


def test_rotation_keeps_native_ticket_size_and_readable_numbers(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {"count": 2, "layer_template": {**LAYER, "sheet_width": 100, "sheet_height": 120}},
    )
    plan = json.loads((tmp_path / "plan-souches.json").read_text())
    assert plan["grid"]["rotation"] == 90
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        assert len(pdf) == 2
        assert "SP-0001" in pdf[0].get_textpage().get_text_range()
    with pikepdf.open(tmp_path / "imposition.pdf") as pdf:
        matrices = [
            list(args) for args, op in pikepdf.parse_content_stream(pdf.pages[0]) if str(op) == "cm"
        ]
        assert any(m[:4] == [0, 1, -1, 0] for m in matrices)


def test_imposed_preview_preserves_sequence_jumps_and_hides_pizza_guides_on_export(tmp_path):
    settings = {
        "count": 100,
        "tickets_per_book": 25,
        "layer_template": LAYER,
        "pizza_template": {"unusable_left": 2},
    }
    preview, final = tmp_path / "preview", tmp_path / "final"
    preview.mkdir()
    final.mkdir()
    result = render(preview, "fortune-cookie", [], settings)
    assert [a.name for a in result.artifacts if a.media_type == "application/pdf"] == [
        "imposition.pdf"
    ]
    assert result.artifacts[0].pages == 2
    run(final, "fortune-cookie", [], settings)
    for folder, pages, colored_guides in [(preview, 2, True), (final, 25, False)]:
        with pdfium.PdfDocument(str(folder / "imposition.pdf")) as pdf:
            assert len(pdf) == pages
            text = pdf[0].get_textpage().get_text_range()
            assert all(f"SP-{n:04d}" in text for n in [1, 26, 51, 76])
            bitmap = pdf[0].render(scale=2, rev_byteorder=True)
            pixels = bitmap.to_pil().convert("RGB").get_flattened_data()
            assert any(r > 140 and g > 90 and b < 60 for r, g, b in pixels) == colored_guides
            bitmap.close()


@pytest.mark.parametrize(
    "settings",
    [
        {"layer_template": {"mode": "booklet"}},
        {"tickets_per_book": 0},
        {"tickets_per_book": 101},
        {"tickets_per_book": 1.5},
    ],
)
def test_invalid_book_settings(settings):
    with pytest.raises(ValueError):
        Fortune(**settings)


def test_impossible_sheet_and_insufficient_gap_for_pizza_guides_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Aucune pose"):
        run(
            tmp_path,
            "fortune-cookie",
            [],
            {"layer_template": {"sheet_width": 30, "sheet_height": 30}},
        )
    with pytest.raises(ValueError, match="deux fois le fond perdu"):
        run(
            tmp_path,
            "fortune-cookie",
            [],
            {"layer_template": LAYER, "pizza_template": {"bleed": 4}},
        )
