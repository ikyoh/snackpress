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
    assert len(batches) == 1
    gathered = []
    for pose in range(4):
        pile = [sheet[pose] for sheet in sheets if sheet[pose] is not None]
        if pile:
            assert pile == list(range(pile[0], pile[-1] + 1))
            for start in range(0, len(pile), per_book):
                book = pile[start : start + per_book]
                assert len(book) == min(per_book, count - book[0])
            gathered.extend(pile)
    assert gathered == list(range(count))


@pytest.mark.parametrize(
    "per_book, ranges, sheets",
    [
        (25, [(1, 26), (26, 51), (51, 76), (76, 101)], 25),
        (10, [(1, 31), (31, 61), (61, 81), (81, 101)], 30),
    ],
)
def test_pdf_numbering_is_continuous_after_cutting_the_whole_stack(
    tmp_path, per_book, ranges, sheets
):
    result = run(
        tmp_path,
        "fortune-cookie",
        [],
        {"count": 100, "tickets_per_book": per_book, "layer_template": LAYER},
    )
    assert result.metrics["Feuilles à tirer"] == sheets
    assert result.metrics["Souches"] == 100 // per_book
    assert result.metrics["Poses"] == 4
    assert result.artifacts[0].name == "imposition.pdf"
    # Independently inspect the four physical cut piles, top-left to bottom-right.
    positions = [(17, 78), (108, 78), (17, 17), (108, 17)]
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        assert len(pdf) == sheets
        for pose, (x, y) in enumerate(positions):
            pile = []
            for page in pdf:
                text = page.get_textpage().get_text_bounded(
                    x * PT, y * PT, (x + 85) * PT, (y + 55) * PT
                )
                pile.extend(map(int, re.findall(r"SP-(\d+)", text)))
            assert pile == list(range(*ranges[pose]))
    plan = json.loads((tmp_path / "plan-souches.json").read_text())
    assert plan["sheets"][0] == [f"SP-{first:04d}" for first, _ in ranges]
    assert plan["sheets"][-1] == [
        f"SP-{last - 1:04d}" if last - first == sheets else None for first, last in ranges
    ]


def test_partial_book_and_multiple_books_per_pose_stay_in_one_cut_stack(tmp_path):
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
    assert result.metrics["Feuilles à tirer"] == 10
    assert result.metrics["Souches"] == 5
    assert result.metrics["Lots de coupe"] == 1
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        numbers = [
            int(n)
            for page in pdf
            for n in re.findall(r"T-(\d+)", page.get_textpage().get_text_range())
        ]
        assert sorted(numbers) == list(range(8, 31))
        gathered = []
        for x, y in [(17, 78), (108, 78), (17, 17), (108, 17)]:
            for page in pdf:
                text = page.get_textpage().get_text_bounded(
                    x * PT, y * PT, (x + 85) * PT, (y + 55) * PT
                )
                gathered.extend(map(int, re.findall(r"T-(\d+)", text)))
        assert gathered == list(range(8, 31))
    plan = json.loads((tmp_path / "plan-souches.json").read_text())
    assert plan["sheets"][5:] == [[f"T-{i:03d}", None, None, None] for i in range(13, 18)]


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


def test_preview_stays_on_individual_tickets_and_export_contains_imposed_sheets(tmp_path):
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
    assert [a.name for a in result.artifacts if a.media_type == "application/pdf"] == ["serie.pdf"]
    assert result.artifacts[0].pages == 2
    assert not (preview / "imposition.pdf").exists()
    with pdfium.PdfDocument(str(preview / "serie.pdf")) as pdf:
        assert "SP-0001" in pdf[0].get_textpage().get_text_range()
        assert "SP-0026" not in pdf[0].get_textpage().get_text_range()
        bitmap = pdf[0].render(scale=2, rev_byteorder=True)
        pixels = bitmap.to_pil().convert("RGB").get_flattened_data()
        assert not any(r > 140 and g > 90 and b < 60 for r, g, b in pixels)
        bitmap.close()
    run(final, "fortune-cookie", [], settings)
    with pdfium.PdfDocument(str(final / "imposition.pdf")) as pdf:
        assert len(pdf) == 25
        text = pdf[0].get_textpage().get_text_range()
        assert all(f"SP-{n:04d}" in text for n in [1, 26, 51, 76])
        bitmap = pdf[0].render(scale=2, rev_byteorder=True)
        pixels = bitmap.to_pil().convert("RGB").get_flattened_data()
        assert not any(r > 140 and g > 90 and b < 60 for r, g, b in pixels)
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
