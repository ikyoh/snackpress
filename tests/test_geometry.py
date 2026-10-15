import math

import pytest
from pydantic import ValidationError
from snackpress_imposition.geometry import Settings, calculate


def test_sra3_business_card():
    p = calculate(Settings())
    assert (p.columns, p.rows, p.rotation, p.poses) == (3, 7, 0, 21)
    assert (p.sheets, p.produced) == (12, 252)
    assert p.front[0].x == pytest.approx(26.5)
    assert p.front[0].y == pytest.approx(14.5)


@pytest.mark.parametrize("sheet", [(210, 297), (297, 420), (320, 450), (450, 320)])
@pytest.mark.parametrize("rotation", ["auto", "0", "90"])
def test_placements_within_printable_area_and_no_overlap(sheet, rotation):
    s = Settings(sheet_width=sheet[0], sheet_height=sheet[1], rotation=rotation, bleed=3)
    p = calculate(s)
    for a in p.front:
        assert a.x - s.bleed >= s.margin - 1e-8
        assert a.y - s.bleed >= s.margin - 1e-8
        assert a.x + a.width + s.bleed <= s.sheet_width - s.margin + 1e-8
        assert a.y + a.height + s.bleed <= s.sheet_height - s.margin + 1e-8
    for i, a in enumerate(p.front):
        for b in p.front[i + 1 :]:
            assert (
                a.x + a.width + 2 * s.bleed <= b.x + 1e-8
                or b.x + b.width + 2 * s.bleed <= a.x + 1e-8
                or a.y + a.height + 2 * s.bleed <= b.y + 1e-8
                or b.y + b.height + 2 * s.bleed <= a.y + 1e-8
            )


@pytest.mark.parametrize(
    "portrait,flip,mirror_x",
    [(True, "long", True), (True, "short", False), (False, "long", False), (False, "short", True)],
)
def test_duplex_positions(portrait, flip, mirror_x):
    s = Settings(
        sheet_width=320 if portrait else 450, sheet_height=450 if portrait else 320, flip=flip
    )
    p = calculate(s, True)
    a, b = p.front[0], p.back[0]
    assert b.x == pytest.approx(s.sheet_width - a.x - a.width if mirror_x else a.x)
    assert b.y == pytest.approx(a.y if mirror_x else s.sheet_height - a.y - a.height)
    assert b.rotation == a.rotation


def test_unfit_and_manual_overflow():
    with pytest.raises(ValueError, match="Aucune pose"):
        calculate(Settings(sheet_width=50, sheet_height=50))
    with pytest.raises(ValueError, match="Aucune pose"):
        calculate(Settings(columns=99))


def test_bleed_overlap_and_nan_rejected():
    with pytest.raises(ValidationError):
        Settings(bleed=4, gap=6)
    with pytest.raises(ValidationError):
        Settings(sheet_width=math.nan)


def test_crop_marks_outside_artwork():
    p = calculate(Settings(bleed=3))
    for m in p.marks:
        for pose in p.front:
            assert not (
                pose.x - 3 < (m.x1 + m.x2) / 2 < pose.x + pose.width + 3
                and pose.y - 3 < (m.y1 + m.y2) / 2 < pose.y + pose.height + 3
            )
