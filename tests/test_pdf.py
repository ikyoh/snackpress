import pikepdf
import pytest
from conftest import make_pdf
from snackpress_imposition.geometry import Settings, calculate
from snackpress_imposition.pdf import PT, compose, inspect


@pytest.mark.parametrize("rotation", ["0", "90"])
@pytest.mark.parametrize("origin", [(0, 0), (37, -19)])
def test_native_export_geometry_and_resources(tmp_path, rotation, origin):
    source, output = tmp_path / "source.pdf", tmp_path / "result.pdf"
    make_pdf(source, origin=origin)
    s = Settings(rotation=rotation, bleed=3)
    plan = calculate(s, True)
    compose(source, output, plan)
    with pikepdf.open(output) as pdf:
        assert len(pdf.pages) == 2
        assert float(pdf.pages[0].mediabox[2]) == pytest.approx(320 * PT, abs=0.001)
        for page in pdf.pages:
            forms = [v for _, v in page.Resources.XObject.items()]
            assert len(forms) == 1
            assert forms[0].Subtype == pikepdf.Name.Form
            assert forms[0].Resources.Font.F1.BaseFont == pikepdf.Name.Helvetica
            assert b"0.8 0.1 0 0.1 k" in forms[0].read_bytes()
            page.contents_coalesce()
            assert page.Contents.read_bytes().count(b" Do Q") == plan.poses


def test_no_implicit_scaling_or_missing_bleed(source, tmp_path):
    with pytest.raises(ValueError, match="mise à l’échelle"):
        compose(source, tmp_path / "bad.pdf", calculate(Settings(trim_width=90), True))
    with pytest.raises(ValueError, match="indisponible"):
        compose(source, tmp_path / "bad.pdf", calculate(Settings(bleed=4, gap=8), True))


def test_missing_trim_requires_confirmation(tmp_path):
    src = tmp_path / "no-trim.pdf"
    make_pdf(src, trim=False)
    info = inspect(src)
    assert not info.pages[0].has_trim
    s = Settings(trim_width=91, trim_height=61)
    with pytest.raises(ValueError, match="Confirmez"):
        compose(src, tmp_path / "out.pdf", calculate(s, True))


@pytest.mark.parametrize("pages,rotation", [(3, 0), (1, 90)])
def test_explicit_rejection(tmp_path, pages, rotation):
    src = tmp_path / "unsupported.pdf"
    make_pdf(src, pages=pages, rotation=rotation)
    with pytest.raises(ValueError):
        inspect(src)


def test_annotations_and_encryption_rejected(source, tmp_path):
    target = tmp_path / "annotated.pdf"
    with pikepdf.open(source) as pdf:
        pdf.pages[0].Annots = pikepdf.Array([pikepdf.Dictionary(Subtype=pikepdf.Name.Text)])
        pdf.save(target)
    with pytest.raises(ValueError, match="annotations"):
        inspect(target)
    with pikepdf.open(source) as pdf:
        pdf.save(target, encryption=pikepdf.Encryption(owner="owner", user="password"))
    with pytest.raises(ValueError, match="protégé"):
        inspect(target)
