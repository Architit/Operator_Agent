import json
from pathlib import Path

from agent.queue_manager import (
    iter_pending,
    load_queue,
    mark_done,
    mark_error,
    mark_in_progress,
    save_queue_atomic,
)


def _task(task_id: str, status: str, priority: int, created_at: str):
    return {
        "id": task_id,
        "block_id": f"blk_{task_id}",
        "block_path": f"/tmp/{task_id}.json",
        "lng": "en",
        "prompt_template": "default",
        "status": status,
        "priority": priority,
        "created_at": created_at,
        "completed_at": None,
        "result_path": None,
        "error_path": None,
        "error_msg": None,
    }


def test_load_queue_skips_invalid_lines(tmp_path):
    q_path = tmp_path / "queue.jsonl"
    valid = _task("1", "pending", 10, "2026-02-17T00:00:00Z")
    invalid_json = '{"id":"2"'
    invalid_schema = {"id": "3", "status": "pending"}
    q_path.write_text(
        "\n".join(
            [
                json.dumps(valid),
                invalid_json,
                json.dumps(invalid_schema),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_queue(str(q_path))
    assert len(loaded) == 1
    assert loaded[0]["id"] == "1"


def test_load_queue_rejects_invalid_datetime_format(tmp_path):
    q_path = tmp_path / "queue.jsonl"
    invalid_dt = _task("1", "pending", 10, "not-a-date")
    q_path.write_text(json.dumps(invalid_dt) + "\n", encoding="utf-8")

    loaded = load_queue(str(q_path))
    assert loaded == []


def test_iter_pending_and_status_transitions(tmp_path):
    items = [
        _task("a", "pending", 5, "2026-02-17T00:00:02Z"),
        _task("b", "pending", 8, "2026-02-17T00:00:03Z"),
        _task("c", "pending", 8, "2026-02-17T00:00:01Z"),
        _task("d", "done", 100, "2026-02-17T00:00:00Z"),
    ]

    pending = iter_pending(items)
    assert [t["id"] for t in pending] == ["c", "b", "a"]

    mark_in_progress(items, "a")
    assert next(t for t in items if t["id"] == "a")["status"] == "in_progress"

    mark_done(items, "a", "/tmp/result.json", "2026-02-17T01:00:00Z")
    task_a = next(t for t in items if t["id"] == "a")
    assert task_a["status"] == "done"
    assert task_a["result_path"] == "/tmp/result.json"
    assert task_a["error_msg"] is None

    mark_error(items, "b", "boom", "/tmp/err.json", "2026-02-17T01:01:00Z")
    task_b = next(t for t in items if t["id"] == "b")
    assert task_b["status"] == "error"
    assert task_b["result_path"] is None

    out_path = tmp_path / "queue.saved.jsonl"
    save_queue_atomic(str(out_path), items)
    lines = [line for line in out_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == len(items)


def test_iter_pending_handles_unparseable_created_at():
    items = [
        _task("a", "pending", 3, "2026-02-17T00:00:00Z"),
        _task("b", "pending", 3, "not-a-date"),
    ]
    pending = iter_pending(items)
    assert [t["id"] for t in pending] == ["a", "b"]


def test_load_queue_skips_non_object_when_jsonschema_missing(tmp_path, monkeypatch):
    q_path = tmp_path / "queue.jsonl"
    q_path.write_text(json.dumps(["bad", "entry"]) + "\n", encoding="utf-8")

    import agent.queue_manager as qm

    monkeypatch.setattr(qm, "jsonschema", None)
    loaded = qm.load_queue(str(q_path))
    assert loaded == []
