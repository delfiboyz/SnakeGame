from snakegame.storage import LEADERBOARD_SIZE, ScoreEntry, Store


def test_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    store = Store(path)
    store.settings.mode = "Portal"
    store.settings.muted = True
    assert store.submit("Classic/Normal", ScoreEntry(10, 12, 30.0)) == 0
    store.save()

    loaded = Store(path)
    assert loaded.settings.mode == "Portal"
    assert loaded.settings.muted is True
    assert loaded.best("Classic/Normal") == 10


def test_leaderboard_ranking_and_limit(tmp_path):
    store = Store(tmp_path / "data.json")
    key = "Classic/Easy"
    for score in (5, 20, 10, 15, 1):
        store.submit(key, ScoreEntry(score, 3, 1.0))
    assert [e.score for e in store.leaderboard(key)] == [20, 15, 10, 5, 1]
    assert store.submit(key, ScoreEntry(12, 3, 1.0)) == 2
    assert len(store.leaderboard(key)) == LEADERBOARD_SIZE
    assert store.submit(key, ScoreEntry(2, 3, 1.0)) is None
    assert store.submit(key, ScoreEntry(0, 3, 1.0)) is None


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{not json")
    store = Store(path)
    assert store.scores == {}
    assert store.settings.difficulty == "Normal"


class FakeLocalStorage:
    def __init__(self):
        self.items = {}

    def getItem(self, key):  # noqa: N802 - meniru API JavaScript
        return self.items.get(key)

    def setItem(self, key, value):  # noqa: N802
        self.items[key] = value


def test_browser_local_storage(tmp_path):
    storage = FakeLocalStorage()
    store = Store(local_storage=storage)
    assert store.scores == {}  # getItem mengembalikan None saat kosong
    store.submit("Portal/Hard", ScoreEntry(7, 9, 12.0))
    store.save()
    assert "snakegame" in storage.items

    loaded = Store(local_storage=storage)
    assert loaded.best("Portal/Hard") == 7
