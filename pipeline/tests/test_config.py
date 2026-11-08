from datetime import date

from scs import config

CFG = config.load()


def test_every_venue_has_a_year_and_valid_date():
    for key, v in CFG.venues.items():
        assert key.endswith(v.year), key
        date.fromisoformat(v.conference_date)


def test_held_and_due():
    v = CFG.venues["icml2026"]  # 2026-07-06 开幕
    assert not v.held(date(2026, 7, 5))
    assert v.held(date(2026, 7, 6))
    assert not v.due(date(2026, 10, 3), 90)
    assert v.due(date(2026, 10, 4), 90)


def test_due_venues_are_a_subset_of_held_ones():
    today = date(2026, 11, 8)
    held, due = CFG.held_venues(today), CFG.due_venues(today)
    assert set(due) <= set(held)
    assert "acl2026" in due and "eccv2026" in held and "eccv2026" not in due
    assert "neurips2026" not in held
