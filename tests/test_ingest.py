from app.rag import ingest


class NoWaitLimiter:
    def wait(self, text):
        pass


def test_build_regulation_rows_embeds_each_regulation(monkeypatch):
    monkeypatch.setattr(ingest, "embed", lambda text, kind: [0.1, 0.2, 0.3])

    rows = ingest.build_regulation_rows(limiter=NoWaitLimiter())

    assert len(rows) == len(ingest.REGULATIONS)
    first = rows[0]
    assert first["metadata"] == {"source": "regulation", "regulation_id": 1}
    assert first["embedding"] == "[0.1,0.2,0.3]"
    assert first["content"] == ingest.REGULATIONS[1]


def test_build_regulation_rows_uses_passage_kind(monkeypatch):
    seen = {}

    def fake_embed(text, kind):
        seen["kind"] = kind
        return [0.0]

    monkeypatch.setattr(ingest, "embed", fake_embed)
    ingest.build_regulation_rows(limiter=NoWaitLimiter())

    assert seen["kind"] == "passage"
