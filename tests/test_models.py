from pathlib import Path

from models import FolderPair, PairStatus, SyncMode


def pair(left="a", right="b", mode=SyncMode.BIDIRECTIONAL, **kw):
    return FolderPair(None, "p", left, right, mode, **kw)


def test_source_for_respects_direction():
    assert pair().source_for("left") == (Path("a"), Path("b"))
    assert pair().source_for("right") == (Path("b"), Path("a"))
    assert pair(mode=SyncMode.LEFT_TO_RIGHT).source_for("right") is None
    assert pair(mode=SyncMode.RIGHT_TO_LEFT).source_for("left") is None


def test_validate(tmp_path):
    assert pair(str(tmp_path / "x"), str(tmp_path / "y")).validate() is None
    assert "required" in FolderPair(None, " ", "a", "b").validate()
    assert "different" in pair(str(tmp_path), str(tmp_path)).validate()
    assert "inside" in pair(str(tmp_path), str(tmp_path / "sub")).validate()
    # A shared name prefix is not nesting.
    assert pair(str(tmp_path / "data"), str(tmp_path / "data2")).validate() is None


def test_status():
    assert pair().status is PairStatus.IDLE
    assert pair(paused=True).status is PairStatus.PAUSED
    assert pair(enabled=False, paused=True).status is PairStatus.DISABLED


def test_labels():
    assert [m.label for m in SyncMode] == ["Bidirectional", "Left → Right", "Right → Left"]
