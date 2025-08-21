"""
Error writing utilities for OperatorAgent.

This module provides a function to write error reports to disk. When the
analysis of a block fails, an error record capturing the type and detail
of the failure, as well as the originating task and timestamp, is
persisted under ``Archive/AnalysisErrors/<block_id>.json``.  If an
error file for the same block already exists, additional errors are
written with a timestamp suffix to preserve history.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema

logger = logging.getLogger(__name__)


def _load_schema() -> Dict[str, Any]:
    """Load the analysis error JSON schema from the schemas directory."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    schema_path = project_root / "schemas" / "analysis_error.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


_ERROR_SCHEMA: Dict[str, Any] = _load_schema()


def write_error(
    base_dir: str,
    block_id: str,
    task_id: str,
    error_type: str,
    error_detail: str,
    response_text: Optional[str],
    timestamp_iso: str,
) -> str:
    """Validate and write an analysis error to disk.

    Parameters:
        base_dir: Base directory of the archive. The error will be written
            to ``<base_dir>/Archive/AnalysisErrors/<block_id>.json``.
        block_id: Identifier of the block whose analysis failed.
        task_id: Identifier of the queue task that failed.
        error_type: Categorical type of error (e.g. "Network").
        error_detail: Human‑readable description of the error.
        response_text: Raw response text that caused the error, if any.
        timestamp_iso: ISO 8601 UTC timestamp when the error occurred.

    Returns:
        The file system path to the written error record.

    Raises:
        jsonschema.ValidationError: If the error object does not conform
            to the schema.
        OSError: If an I/O error occurs while writing the file.
    """
    error_obj: Dict[str, Any] = {
        "block_id": block_id,
        "task_id": task_id,
        "error_type": error_type,
        "error_detail": error_detail,
        "response_text": response_text,
        "timestamp": timestamp_iso,
    }
    # Validate error object
    jsonschema.validate(instance=error_obj, schema=_ERROR_SCHEMA)
    # Determine directory and base filename
    base_path = Path(base_dir)
    errors_dir = base_path / "Archive" / "AnalysisErrors"
    errors_dir.mkdir(parents=True, exist_ok=True)
    # Compose initial file path
    base_file = errors_dir / f"{block_id}.json"
    if base_file.exists():
        # Append timestamp suffix without separators
        suffix_ts = timestamp_iso.replace("-", "").replace(":", "")
        file_name = f"{block_id}__{suffix_ts}.json"
        out_path = errors_dir / file_name
    else:
        out_path = base_file
    # Write error JSON
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(error_obj, f, ensure_ascii=False)
    logger.info(f"Error written to {out_path}")
    return str(out_path)