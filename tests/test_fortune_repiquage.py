import json

import pikepdf
import pypdfium2 as pdfium
import pytest
from reportlab.pdfbase.pdfmetrics import stringWidth
from snackpress_tools.catalog import CsvData, Fortune
from snackpress_tools.fortune_data import barcode_value
from snackpress_tools.runner import run

PT = 72 / 25.4


def test_alignment_anchors_the_same_text_around_x(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 1,
            "prefix": "ALIGN",
            "digits": 1,
            "start": 0,
            "repiquages": [
                {"x": 42, "y": 15 + index * 15, "align": align, "font": "Courier", "size": 12}
                for index, align in enumerate(["left", "center", "right"])
            ],
        },
    )
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as pdf:
        text = pdf[0].get_textpage()
        content = text.get_text_range()
        positions = [i for i in range(len(content)) if content.startswith("ALIGN0", i)]
        assert len(positions) == 3
        starts = [text.get_charbox(i)[0] for i in positions]
        width = stringWidth("ALIGN0", "Courier", 12)
        assert starts[0] - starts[1] == pytest.approx(width / 2, abs=0.01)
        assert starts[0] - starts[2] == pytest.approx(width, abs=0.01)


def test_csv_text_sequence_and_both_vector_barcodes_share_the_same_record(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 2,
            "csv_data": {
                "columns": ["nom", "code", "ean"],
                "rows": [
                    ["Élodie\nAtelier A", "00017", "590123412345"],
                    ["Zoé", "00018", "5901234123457"],
                ],
            },
            "repiquages": [
                {"source": "csv", "column": "nom", "x": 42, "y": 12, "align": "center"},
                {
                    "source": "csv",
                    "column": "code",
                    "rendering": "code128",
                    "x": 4,
                    "y": 34,
                    "barcode_width": 35,
                },
                {
                    "source": "csv",
                    "column": "ean",
                    "rendering": "ean13",
                    "x": 81,
                    "y": 50,
                    "align": "right",
                    "barcode_width": 38,
                },
                {"x": 4, "y": 52},
            ],
        },
    )
    with pdfium.PdfDocument(str(tmp_path / "serie.pdf")) as pdf:
        assert "Élodie" in pdf[0].get_textpage().get_text_range()
        assert "Atelier A" in pdf[0].get_textpage().get_text_range()
        assert "Zoé" in pdf[1].get_textpage().get_text_range()
        for index, page in enumerate(pdf):
            assert f"SP-{index + 1:04d}" in page.get_textpage().get_text_range()
    with pikepdf.open(tmp_path / "serie.pdf") as pdf:
        # Bars remain vector rectangles, not embedded raster images.
        commands = pikepdf.parse_content_stream(pdf.pages[0])
        assert sum(str(op) == "re" for _, op in commands) > 50
        assert "/XObject" not in pdf.pages[0].Resources


def test_csv_records_remain_in_order_after_cutting_the_full_stack(tmp_path):
    run(
        tmp_path,
        "fortune-cookie",
        [],
        {
            "count": 8,
            "tickets_per_book": 2,
            "csv_data": {"columns": ["id"], "rows": [[f"CLIENT-{i}"] for i in range(1, 9)]},
            "repiquages": [{"source": "csv", "column": "id", "x": 20, "y": 20}],
            "layer_template": {"sheet_width": 210, "sheet_height": 150, "gap": 6},
        },
    )
    with pdfium.PdfDocument(str(tmp_path / "imposition.pdf")) as pdf:
        for sheet, page in enumerate(pdf):
            content = page.get_textpage().get_text_range()
            expected = [f"CLIENT-{sheet + 1 + pose * 2}" for pose in range(4)]
            assert [content.index(value) for value in expected] == sorted(
                content.index(value) for value in expected
            )
    manifest = json.loads((tmp_path / "plan-souches.json").read_text())
    assert manifest["csv_row_numbers"] == [[2, 4, 6, 8], [3, 5, 7, 9]]
    assert manifest["sheets"][0] == [f"Ligne CSV {i}" for i in [2, 4, 6, 8]]


@pytest.mark.parametrize("value", ["590123412345", "5901234123457"])
def test_ean13_accepts_a_calculated_or_supplied_valid_key(value):
    assert barcode_value(value, "ean13") == "5901234123457"


@pytest.mark.parametrize(
    "kind,value",
    [("ean13", "5901234123458"), ("ean13", "123"), ("code128", "Élodie"), ("code128", "")],
)
def test_invalid_codes_on_later_records_fail_before_generation(kind, value):
    with pytest.raises(ValueError, match="billet 2"):
        Fortune(
            count=2,
            csv_data={"columns": ["code"], "rows": [["5901234123457"], [value]]},
            repiquages=[{"source": "csv", "column": "code", "rendering": kind}],
        )


def test_csv_count_and_mapping_cannot_silently_drop_or_repeat_records():
    with pytest.raises(ValueError, match="nombre de lignes"):
        Fortune(
            count=2,
            csv_data={"columns": ["nom"], "rows": [["A"]]},
            repiquages=[{"source": "csv", "column": "nom"}],
        )
    with pytest.raises(ValueError, match="choisissez une colonne"):
        Fortune(repiquages=[{"source": "csv", "column": "absente"}])
    with pytest.raises(ValueError, match="trop dense"):
        Fortune(count=1, repiquages=[{"rendering": "code128", "barcode_width": 1}])


@pytest.mark.parametrize(
    "columns,rows",
    [
        (["nom", "nom"], [["A", "B"]]),
        (["nom"], [["A", "B"]]),
        ([" "], [["A"]]),
        (["nom"], [["A"]] * 1001),
    ],
)
def test_invalid_csv_tables_are_rejected(columns, rows):
    with pytest.raises(ValueError):
        CsvData(columns=columns, rows=rows)
