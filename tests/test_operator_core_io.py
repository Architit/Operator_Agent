import hashlib
import json
from pathlib import Path

import pytest
jsonschema = pytest.importorskip("jsonschema")
ValidationError = jsonschema.ValidationError

from agent.block_reader import BlockValidationError, read_block
from agent.error_writer import write_error
from agent.result_writer import write_result


def _build_block(status: str = "ok", text: str = "hello", size_bias: int = 0):
    encoded = text.encode("utf-8")
    return {
        "block_id": "blk_000001",
        "parent_sha256": "0" * 64,
        "src_file": "sample.txt",
        "seq": 1,
        "total_seqs": 1,
        "encoding": "utf-8",
        "lng": "en",
        "status": status,
        "size_bytes": len(encoded) + size_bias,
        "hash_sha256": hashlib.sha256(encoded).hexdigest(),
        "tags": ["sample"],
        "text": text,
    }


def _analysis_payload():
    return {
        "summary": "summary",
        "keywords": ["k1", "k2"],
        "class": "useful",
        "signals": {"people": [], "projects": [], "dates": []},
        "actions": [],
        "risks": [],
        "quotes": [],
    }


def test_read_block_ok_strict_raises_on_hash_mismatch(tmp_path):
    block = _build_block(status="ok")
    block["hash_sha256"] = "f" * 64
    block_path = tmp_path / "block.json"
    block_path.write_text(json.dumps(block), encoding="utf-8")

    with pytest.raises(BlockValidationError):
        read_block(str(block_path))


def test_read_block_damaged_uses_soft_validation(tmp_path):
    block = _build_block(status="damaged", size_bias=500)
    block["hash_sha256"] = "f" * 64
    block_path = tmp_path / "block.json"
    block_path.write_text(json.dumps(block), encoding="utf-8")

    loaded = read_block(str(block_path))
    assert loaded["status"] == "damaged"


def test_write_result_idempotent(tmp_path):
    first = write_result(
        base_dir=str(tmp_path),
        block_id="blk_100",
        model="gpt-4o",
        analysis_version="v1",
        analysis_obj=_analysis_payload(),
        completed_at_iso="2026-02-17T03:00:00Z",
    )
    second = write_result(
        base_dir=str(tmp_path),
        block_id="blk_100",
        model="gpt-4o",
        analysis_version="v1",
        analysis_obj=_analysis_payload(),
        completed_at_iso="2026-02-17T03:01:00Z",
    )

    assert first == second
    payload = json.loads(Path(first).read_text(encoding="utf-8"))
    assert payload["completed_at"] == "2026-02-17T03:00:00Z"


def test_write_error_creates_suffix_if_base_exists(tmp_path):
    first = write_error(
        base_dir=str(tmp_path),
        block_id="blk_200",
        task_id="task-1",
        error_type="InvalidJSON",
        error_detail="bad json",
        response_text=None,
        timestamp_iso="2026-02-17T03:00:00Z",
    )
    second = write_error(
        base_dir=str(tmp_path),
        block_id="blk_200",
        task_id="task-2",
        error_type="IOError",
        error_detail="io fail",
        response_text="",
        timestamp_iso="2026-02-17T03:00:01Z",
    )

    assert first.endswith("blk_200.json")
    assert "blk_200__20260217T030001Z.json" in second


def test_write_result_rejects_invalid_completed_at(tmp_path):
    with pytest.raises(ValidationError):
        write_result(
            base_dir=str(tmp_path),
            block_id="blk_300",
            model="gpt-4o",
            analysis_version="v1",
            analysis_obj=_analysis_payload(),
            completed_at_iso="not-a-date",
        )


def test_write_error_rejects_invalid_timestamp(tmp_path):
    with pytest.raises(ValidationError):
        write_error(
            base_dir=str(tmp_path),
            block_id="blk_301",
            task_id="task-1",
            error_type="IOError",
            error_detail="io fail",
            response_text=None,
            timestamp_iso="not-a-date",
        )
