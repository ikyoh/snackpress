import pikepdf
import pypdfium2 as pdfium
import pytest
from conftest import make_pdf
from snackpress_tools.catalog import Burger
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

    def collect(resources):
        for obj in dict(resources.get("/XObject", {})).values():
            if obj.get("/Subtype") == "/Form":
                forms.append(obj)
                collect(obj.get("/Resources", {}))
            else:
                assert obj.get("/Subtype") == "/Image"

    collect(page.Resources)
    return forms


def assert_native_guides(page):
    # One image is the artwork. The guides must add PDF paths, not another image.
    images = [obj for obj in dict(page.Resources.XObject).values() if obj.Subtype == "/Image"]
    assert len(images) == 1
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


def test_card_and_separate_finishes(tmp_path):
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
    assert result.metrics["Pages du BAT"] == 4
    content = text(out / "bat.pdf")
    assert "Recto" in content and "Verso" in content and "Finition : Vernis" in content


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
def test_registered_template_marks_on_additional_page(tmp_path, tool, width, height):
    visual = source(tmp_path, "visual.pdf", width=width, height=height)
    out, result = generate(tmp_path, [visual], {"template_tool": tool})
    assert result.metrics["Pages du BAT"] == 2
    with pdfium.PdfDocument(str(out / "bat.pdf")) as pdf:
        first = pdf[0].render(scale=1).to_pil().copy()
        second = pdf[1].render(scale=1).to_pil().copy()
        # The artwork is present under the template, including the large-format source.
        assert first.getpixel((297, 390)) != (255, 255, 255)
        assert second.getpixel((297, 390)) != (255, 255, 255)
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert "/Multiply" in str(pdf.pages[1].Resources.ExtGState)
        assert not guide_forms(pdf.pages[0])
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
    assert result.metrics["Pages du BAT"] == 2
    with pikepdf.open(out / "bat.pdf") as pdf:
        assert_native_guides(pdf.pages[1])


def test_vector_guides_on_each_artwork_page_but_not_finish_pages(tmp_path):
    visual = source(tmp_path, "visual.pdf", pages=2, width=85, height=55)
    finish = source(tmp_path, "finish.pdf", width=85, height=55)
    out, result = generate(
        tmp_path,
        [visual, finish],
        {
            "finishes": ["Vernis"],
            "template_tool": "pizza",
            "template_settings": {"unusable_top": 7, "safety_left": 5},
        },
    )
    assert result.metrics["Pages du BAT"] == 5
    with pikepdf.open(out / "bat.pdf") as pdf:
        for index in (1, 3):
            assert_native_guides(pdf.pages[index])
            assert any(
                str(op) == "W*"
                for form in guide_forms(pdf.pages[index])
                for _, op in pikepdf.parse_content_stream(form)
            )
        for index in (0, 2, 4):
            assert not guide_forms(pdf.pages[index])


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
