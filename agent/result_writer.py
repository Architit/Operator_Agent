"""
Result writing utilities for OperatorAgent.

This module provides a function to write analysis results to disk in a
structured JSON format. Results are stored under
``Archive/AnalysisResults/<block_id>.json`` relative to a base directory.
Each result contains metadata about the analysed block and a nested
analysis object describing the outcome. Both the analysis payload and the
final result wrapper are validated against JSON schemas defined in
``schemas/analysis_payload.schema.json`` and
``schemas/analysis_result.schema.json``.

Repeated calls to write the same block identifier are idempotent: if the
result file already exists, it is not overwritten and an informational
log message is emitted.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

import jsonschema

logger = logging.getLogger(__name__)


def _load_schema(schema_name: str) -> Dict[str, Any]:
    """Load a JSON schema from the schemas directory by file name."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    schema_path = project_root / "schemas" / schema_name
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# Preload schemas to avoid repeated disk access
_ANALYSIS_PAYLOAD_SCHEMA = _load_schema("analysis_payload.schema.json")
_ANALYSIS_RESULT_SCHEMA = _load_schema("analysis_result.schema.json")

# Determine the schemas directory URI for resolving references
_SCHEMAS_DIR = (Path(__file__).resolve().parent.parent / "schemas").absolute()



def write_result(
    base_dir: str,
    block_id: str,
    model: str,
    analysis_version: str,
    analysis_obj: Dict[str, Any],
    completed_at_iso: str,
) -> str:
    """Validate and write an analysis result to disk.

    Parameters:
        base_dir: Base directory of the archive. The result will be
            written to ``<base_dir>/Archive/AnalysisResults/<block_id>.json``.
        block_id: Identifier of the analysed block.
        model: Name of the model that produced the analysis.
        analysis_version: Version string of the analysis pipeline.
        analysis_obj: Dictionary containing analysis details (summary,
            keywords, class, signals, actions, risks, quotes).
        completed_at_iso: ISO 8601 timestamp when analysis completed.

    Returns:
        The file system path to the written result (or existing file).

    Raises:
        jsonschema.ValidationError: If either the analysis payload or the
            final result does not conform to the schemas.
        OSError: If an I/O error occurs while writing the file.
    """
    # Validate the analysis payload
    jsonschema.validate(instance=analysis_obj, schema=_ANALYSIS_PAYLOAD_SCHEMA)
    # Construct the wrapper result
    result: Dict[str, Any] = {
        "block_id": block_id,
        "model": model,
        "completed_at": completed_at_iso,
        "analysis_version": analysis_version,
        "analysis": analysis_obj,
    }
    # Validate the final result. The result schema references the payload
    # schema via $ref. Provide a resolver that knows where to find it.
    resolver = jsonschema.RefResolver(
        base_uri=_SCHEMAS_DIR.as_uri() + "/",
        referrer=_ANALYSIS_RESULT_SCHEMA,
        store={
            "analysis_payload.schema.json": _ANALYSIS_PAYLOAD_SCHEMA,
            "analysis_result.schema.json": _ANALYSIS_RESULT_SCHEMA,
        },
    )
    jsonschema.validate(instance=result, schema=_ANALYSIS_RESULT_SCHEMA, resolver=resolver)
    # Determine output path
    base_path = Path(base_dir)
    out_path = base_path / "Archive" / "AnalysisResults" / f"{block_id}.json"
    # Create directories if necessary
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        logger.info(f"Result file {out_path} already exists; skipping write")
        return str(out_path)
    # Write result to file
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except Exception as e:
        # Clean up partial file on error
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass
        raise
    logger.info(f"Result written to {out_path}")
    return str(out_path)