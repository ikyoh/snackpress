import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf, proof_body_count, proof_body_pages
from snackpress_tools.catalog import Burger
from snackpress_tools.proof_layout import proof_date
from snackpress_tools.runner import run


def source(tmp_path, name, pages=1, width=91, height=61):
    path = tmp_path / name
    make_pdf(path, pages=pages)
    with pikepdf.open(path, allow_overwriting_input=True) as doc:
        for page in doc.pages:
            page.Contents = doc.make_stream(
                f"q {width / 91} 0 0 {height / 61} 0 0 cm ".encode()
                + page.Contents.read_bytes()
                + b" Q"
            )
            page.MediaBox = pikepdf.Array([0, 0, width * 72 / 25.4, height * 72 / 25.4])
        doc.save(path)
    return path


def generate(tmp_path, files, settings):
    out = tmp_path / "out"
    out.mkdir()
    return out, run(out, "burger", files, settings)


def text(path):
    with pdfium.PdfDocument(str(path)) as pdf:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)


def guide_forms(page):
    forms = []

    def collect(resources, guided=False):
        for obj in dict(resources.get("/XObject", {})).values():
            if obj.get("/Subtype") == "/Form":
                is_guide = guided or obj.get("/SnackpressRole") == "/Guide"
                if is_guide:
                    forms.append(obj)
                collect(obj.get("/Resources", {}), is_guide)
            else:
                assert obj.get("/Subtype") == "/Image"

    collect(page.Resources)
    return forms


def assert_native_guides(page):
    forms = guide_forms(page)
    assert forms
    assert any(
        str(operator) in {"S", "s"}
        for form in forms
        for _, operator in pikepdf.parse_content_stream(form)
    )
    assert all(
        obj.Subtype != "/Image"
        for form in forms
        for obj in dict(form.get("/Resources", {}).get("/XObject", {})).values()
    )


def test_card_with_finish_masks_only_shows_composites(tmp_path):
    recto = source(tmp_path, "recto.pdf")
    verso = source(tmp_path, "verso.pdf")
    varnish = source(tmp_path, "vernis.pdf", pages=2)
    out, result = generate(
        tmp_path,
        [recto, verso, varnish],
        {
            "document_type": "card",
            "expected_files": 2,
            "finishes": ["Vernis"],
        },
    )
    assert result.metrics["Pages du BAT"] == 3
    content = text(out / "bat.pdf")
    assert "Recto" in content and "Verso" in content and "Finition : Vernis" in content
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        for index, page in enumerate(pdf, 1):
            content = page.get_textpage().get_text_range()
            assert f"Date du BAT : {proof_date()}" in content
            assert "snackpress." in content and "snackpress.app" in content
            assert "Légende des repères" not in content
            assert f"Page {index} / {len(pdf)}" in content
    with pikepdf.open(out / "bat.pdf") as pdf:
        for page in pdf.pages:
            assert page.Resources.Shading  # The logo gradient remains vector artwork.
            assert any(a.get("/A", {}).get("/URI") == "https://snackpress.app" for a in page.Annots)


@pytest.mark.parametrize("cover_files", [1, 4])
def test_brochure_grouped_or_split_cover(tmp_path, cover_files):
    cover = source(tmp_path, "cover.pdf", pages=4 // cover_files)
    interior = source(tmp_path, "interior.pdf", pages=8)
    _, result = generate(
        tmp_path,
        [cover] * cover_files + [interior],
        {
            "document_type": "brochure",
            "expected_files": cover_files + 1,
            "cover_files": cover_files,
            "interior_pages": 8,
        },
    )
    assert result.metrics["Faces"] == 12


@pytest.mark.parametrize(
    "tool,width,height", [("pizza", 85, 55), ("taco", 297, 210), ("burrito", 2000, 1000)]
)
def test_registered_template_marks_on_every_page(tmp_path, tool, width, height):
    if tool == "pizza":
        width, height = width + 6, height + 6
    visual = source(tmp_path, "visual.pdf", width=width, height=height)
    out, result = generate(tmp_path, [visual], {"template_tool": tool})
    assert result.metrics["Pages du BAT"] == 3
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        first = pdf[0].render(scale=1).to_pil().copy()
        # The artwork is present under the template, including the large-format source.
        assert first.getpixel((297, 390)) != (255, 255, 255)
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert not guide_forms(pdf.pages[0])
        assert "/Normal" in str(pdf.pages[1].Resources.ExtGState)
        assert_native_guides(pdf.pages[1])


@pytest.mark.parametrize(
    "tool,width,height,settings",
    [
        ("pizza", 85, 55, {}),
        ("taco", 297, 210, {}),
        ("burrito", 2000, 1000, {"sleeve": 50}),
    ],
)
def test_import_exported_pdf_template(tmp_path, tool, width, height, settings):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    exported = run(template_dir, tool, [], settings)
    visual = source(tmp_path, "visual.pdf", width=width, height=height)
    out, result = generate(
        tmp_path, [visual, template_dir / exported.artifacts[0].name], {"template_tool": "pdf"}
    )
    assert result.metrics["Pages du BAT"] == 3
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert_native_guides(pdf.pages[1])


def test_vector_guides_on_every_artwork_and_finish_page(tmp_path):
    visual = source(tmp_path, "visual.pdf", pages=2)
    finish = source(tmp_path, "finish.pdf")
    out, result = generate(
        tmp_path,
        [visual, finish],
        {
            "finishes": ["Vernis"],
            "template_tool": "pizza",
            "template_settings": {"unusable_top": 7, "safety_left": 5},
        },
    )
    assert result.metrics["Pages du BAT"] == 3
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        assert "Légende des repères" not in pdf[0].get_textpage().get_text_range()
        for page in list(pdf)[1 : proof_body_count(out / "bat.pdf")]:
            content = page.get_textpage().get_text_range()
            assert "Légende des repères" in content
            for label in ("Coupe / format fini", "Zone de sécurité", "Zone inexploitable"):
                assert label in content
    with pikepdf.open(out / "bat.pdf") as pdf:
        for page in proof_body_pages(pdf)[1:]:
            assert_native_guides(page)
            assert any(
                str(op) == "W*"
                for form in guide_forms(page)
                for _, op in pikepdf.parse_content_stream(form)
            )


@pytest.mark.parametrize(
    "settings,error",
    [
        ({"expected_files": 2}, "2 fichier"),
        ({"finishes": ["Dorure"]}, "2 fichier"),
        ({"template_tool": "pizza", "template_settings": {"width": 120}}, "incompatible"),
        ({"document_type": "card", "expected_files": 2}, "deux PDF"),
        ({"document_type": "brochure", "expected_files": 2}, "couverture"),
        ({"document_type": "brochure", "expected_files": 2, "interior_pages": 8}, "intérieur"),
    ],
)
def test_invalid_production_inputs(tmp_path, settings, error):
    pages = 2 if settings.get("document_type") == "card" else 1
    if error == "intérieur":
        pages = 4
    visual = source(tmp_path, "visual.pdf", pages=pages)
    files = [visual] * (2 if settings.get("document_type") in {"card", "brochure"} else 1)
    with pytest.raises(ValueError, match=error):
        generate(tmp_path, files, settings)


def test_finish_and_nested_template_validation():
    with pytest.raises(ValueError, match="distinct"):
        Burger(finishes=["Vernis", " vernis "])
    with pytest.raises(ValueError, match="rayon"):
        Burger(template_tool="pizza", template_settings={"corner_radius": 100})
