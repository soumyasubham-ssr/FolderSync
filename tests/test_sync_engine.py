import time

import pytest

from models import FolderPair, SyncMode
from sync_engine import SyncEngine


class RecordingLogger:
    def __init__(self):
        self.entries = []

    def log(self, pair, operation, status="Success", detail=""):
        self.entries.append((operation, status))


@pytest.fixture
def setup(tmp_path, db, qapp):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir(), right.mkdir()
    pair = db.save_pair(FolderPair(None, "test", str(left), str(right), SyncMode.BIDIRECTIONAL))
    log = RecordingLogger()
    engine = SyncEngine(db, log)
    engine.set_pairs([pair])
    yield engine, pair, left, right, log
    engine.shutdown()


def wait_for(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_initial_mirror_copies_and_prunes(setup):
    engine, pair, left, right, log = setup
    (left / "sub").mkdir()
    (left / "sub" / "a.txt").write_text("hello")
    (right / "stale.txt").write_text("old")
    (right / "stale_dir").mkdir()
    engine._initial(pair, "left")
    assert (right / "sub" / "a.txt").read_text() == "hello"
    assert not (right / "stale.txt").exists()
    assert not (right / "stale_dir").exists()
    assert pair.last_sync


def test_initial_mirror_skips_unchanged_files(setup):
    engine, pair, left, right, log = setup
    (left / "a.txt").write_text("x")
    engine._initial(pair, "left")
    log.entries.clear()
    engine._initial(pair, "left")
    assert not any(op.startswith("Copied") for op, _ in log.entries)


def test_one_way_mode_ignores_other_side(setup):
    engine, pair, left, right, log = setup
    pair.mode = SyncMode.LEFT_TO_RIGHT
    (right / "only_right.txt").write_text("x")
    engine._sync(pair.id, "right", "created", str(right / "only_right.txt"), None, False)
    assert not (left / "only_right.txt").exists()


def test_live_create_modify_rename_delete(setup):
    engine, pair, left, right, log = setup
    assert engine.start_pair(pair.id)
    src = left / "note.txt"
    src.write_text("v1")
    assert wait_for(lambda: (right / "note.txt").exists() and (right / "note.txt").read_text() == "v1")
    src.rename(left / "renamed.txt")
    assert wait_for(lambda: (right / "renamed.txt").exists() and not (right / "note.txt").exists())
    time.sleep(1.2)  # let the echo-suppression window for our own write expire
    (right / "renamed.txt").write_text("from right")  # bidirectional: right edits flow back
    assert wait_for(lambda: (left / "renamed.txt").read_text() == "from right")
    time.sleep(1.2)
    (left / "renamed.txt").unlink()
    assert wait_for(lambda: not (right / "renamed.txt").exists())
    assert not any(status == "Error" for _, status in log.entries)


def test_start_pair_reports_missing_folder(setup, tmp_path):
    engine, pair, left, right, log = setup
    pair.right_path = str(tmp_path / "missing")
    assert not engine.start_pair(pair.id)
    assert ("Folder unavailable", "Error") in log.entries
