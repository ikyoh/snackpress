import pikepdf
import pytest
from conftest import make_pdf
from snackpress_tools.common import dimensions
from snackpress_tools.examples import burger_example
from snackpress_tools.runner import run


@pytest.mark.parametrize(
    "tool,settings,size,trim",
    [
        ("none", {}, (91, 61), (3, 3, 85, 55)),
        ("pizza", {"width": 120, "height": 80, "bleed": 5}, (130, 90), (5, 5, 120, 80)),
        ("pizza", {"shape": "circle", "width": 80}, (86, 86), (3, 3, 80, 80)),
        ("taco", {"width": 297, "height": 210}, (297, 210), (0, 0, 297, 210)),
        (
            "burrito",
            {"width": 600, "height": 300, "sleeve": 50},
            (600, 350),
            (0, 0, 600, 300),
        ),
        ("sushi", {"width": 60, "height": 40}, (60, 40), (0, 0, 60, 40)),
        ("sushi", {"width": 60, "height": 40, "bleed": 3}, (66, 46), (3, 3, 60, 40)),
    ],
)
def test_burger_example_matches_template_and_generates_proof(tmp_path, tool, settings, size, trim):
    values = {"template_tool": tool, "template_settings": settings}
    example = burger_example(tmp_path, [], values)
    paths = [tmp_path / item.name for item in example.artifacts]
    assert len(paths) == 1
    with pikepdf.open(paths[0]) as pdf:
        assert len(pdf.pages) == 2
        for page in pdf.pages:
            assert dimensions(page) == pytest.approx(size)
            box = [float(n) * 25.4 / 72 for n in page.TrimBox]
            x, y, w, h = trim
            assert box == pytest.approx((x, y, x + w, y + h))
    work = tmp_path / "proof"
    work.mkdir()
    proof = run(work, "burger", paths, values)
    assert proof.metrics["Faces"] == 2
    assert proof.metrics["Pages du BAT"] == 5


@pytest.mark.parametrize(
    "values,counts",
    [
        ({"document_type": "card", "expected_files": 2, "finishes": ["Dorure"]}, [1, 1, 2]),
        (
            {
                "document_type": "brochure",
                "expected_files": 5,
                "cover_files": 3,
                "interior_pages": 9,
            },
            [2, 1, 1, 5, 4],
        ),
    ],
)
def test_burger_example_supplies_all_file_roles(tmp_path, values, counts):
    example = burger_example(tmp_path, [], values)
    assert [item.pages for item in example.artifacts] == counts
    work = tmp_path / "proof"
    work.mkdir()
    proof = run(work, "burger", [tmp_path / item.name for item in example.artifacts], values)
    assert proof.metrics["Fichiers visuels"] == values["expected_files"]


def test_burger_example_uses_imported_pdf_and_retains_both_faces(tmp_path):
    source = tmp_path / "source.pdf"
    make_pdf(source)
    example = burger_example(tmp_path, [source], {"template_tool": "pdf"})
    assert [item.pages for item in example.artifacts] == [2, 2]
    with pikepdf.open(tmp_path / example.artifacts[0].name) as pdf:
        assert dimensions(pdf.pages[0]) == pytest.approx((91, 61))
    assert (tmp_path / example.artifacts[-1].name).read_bytes() == source.read_bytes()
    work = tmp_path / "proof"
    work.mkdir()
    assert (
        run(
            work, "burger", [tmp_path / a.name for a in example.artifacts], {"template_tool": "pdf"}
        ).metrics["Faces"]
        == 2
    )


@pytest.mark.parametrize(
    "values,message",
    [
        ({"template_tool": "pdf"}, "Importez le gabarit PDF"),
        (
            {"document_type": "brochure", "expected_files": 10, "interior_pages": 4},
            "au moins une page",
        ),
        ({"finishes": ["Dorure", "Vernis"], "expected_files": 80}, "200 pages"),
    ],
)
def test_burger_example_rejects_unusable_compositions(tmp_path, values, message):
    with pytest.raises(ValueError, match=message):
        burger_example(tmp_path, [], values)
