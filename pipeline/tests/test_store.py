from scs import store
from scs.models import RepoSnapshot


def test_snapshots_roundtrip_keeps_check_time_out_of_rows(tmp_path):
    snaps = [
        RepoSnapshot("a/b", "2026-01-02T03:04:05+00:00", True, listing=(("README.md", 10),)),
        RepoSnapshot("c/d", "2026-01-02T03:04:06+00:00", False),
    ]
    store.save_snapshots("v", snaps, tmp_path)
    rows = (tmp_path / "snapshots" / "v.jsonl").read_text(encoding="utf-8")
    assert "checked_at" not in rows
    loaded = store.load_snapshots("v", tmp_path)
    assert loaded[0].listing == (("README.md", 10),)
    assert {s.checked_at for s in loaded} == {"2026-01-02T03:04:06+00:00"}
