"""
Block reader and validator for archive data blocks.

This module provides functionality to read JSON block files from disk,
validate their structure against a JSON Schema, and perform additional
integrity checks such as text length, size in bytes and SHA-256 hash
verification. When a block is marked as damaged or binary via its
``status`` field, warnings are logged and the block is returned without
raising exceptions for soft validation issues. For blocks with ``status``
set to ``"ok"``, strict validation is applied and any discrepancies
raise ``BlockValidationError``.

The JSON schema for blocks resides at ``schemas/block.schema.json`` and is
loaded relative to the package root.

Functions:
    read_block(path: str) -> dict
        Read a block from a JSON file, validate it and return its content.

    validate_block(obj: dict, *, strict: bool = False) -> None
        Validate a block dictionary against the schema and perform
        additional integrity checks.

Classes:
    BlockValidationError(Exception)
        Raised when strict validation fails during block validation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

import jsonschema


class BlockValidationError(Exception):
    """Exception raised for block validation errors in strict mode."""


def _load_schema() -> Dict[str, Any]:
    """Load the JSON schema for blocks from the schemas directory.

    Returns:
        The loaded JSON schema as a dictionary.

    Raises:
        FileNotFoundError: If the schema file cannot be found.
        json.JSONDecodeError: If the schema file contains invalid JSON.
    """
    # Determine the project root based on this file's location. The schema
    # directory is expected to live alongside the ``agent`` package at the
    # project root.
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    schema_path = project_root / "schemas" / "block.schema.json"
    # Read and parse the schema file
    with schema_path.open("r", encoding="utf-8") as f:
        schema_data = json.load(f)
    return schema_data


def validate_block(obj: Dict[str, Any], *, strict: bool = False) -> None:
    """Validate a block dictionary against the schema and additional rules.

    Parameters:
        obj: The block dictionary parsed from a JSON file.
        strict: Whether to raise errors on validation failures. If False,
            violations of soft rules will only generate warnings via the
            logger. When True, a :class:`BlockValidationError` will be
            raised for violations of hard rules.

    Raises:
        jsonschema.exceptions.ValidationError: If the object does not
            conform to the JSON schema.
        BlockValidationError: If a hard validation error occurs and
            ``strict`` is True.
    """
    logger = logging.getLogger(__name__)
    block_id = obj.get("block_id", "<unknown>")
    # Validate against the JSON schema
    schema = _load_schema()
    jsonschema.validate(instance=obj, schema=schema)

    # Additional integrity checks
    # Extract required fields with defaults where appropriate
    text = obj.get("text", "")
    encoding = obj.get("encoding", "utf-8")
    recorded_size = obj.get("size_bytes", 0)
    recorded_hash = obj.get("hash_sha256", "")
    seq = obj.get("seq")
    total_seqs = obj.get("total_seqs")

    # 1. Text length check
    text_length = len(text)
    if text_length > 20000:
        message = f"[{block_id}] WARNING: text length {text_length} > 20000"
        if strict:
            logger.error(message)
            raise BlockValidationError(message)
        logger.warning(message)

    # 6. Encoding check: attempt to encode using provided encoding
    encoded_bytes: bytes
    used_encoding = encoding
    try:
        encoded_bytes = text.encode(encoding, errors="strict")
    except (LookupError, UnicodeEncodeError) as e:
        # In strict mode, fail; otherwise warn and fall back to utf-8
        fallback_message = (
            f"[{block_id}] WARNING: failed to encode text with encoding "
            f"'{encoding}': {e}. Using 'utf-8' as fallback."
        )
        if strict:
            logger.error(fallback_message)
            raise BlockValidationError(fallback_message)
        logger.warning(fallback_message)
        used_encoding = "utf-8"
        encoded_bytes = text.encode("utf-8", errors="replace")

    computed_size = len(encoded_bytes)
    # 2. Size in bytes check
    # Check absolute size limit (1 MiB)
    if computed_size > 1048576:
        message = (
            f"[{block_id}] WARNING: encoded text size {computed_size} bytes > "
            f"1048576"
        )
        if strict:
            logger.error(message)
            raise BlockValidationError(message)
        logger.warning(message)

    # Check difference between recorded and computed sizes
    # To avoid division by zero, handle recorded_size == 0 separately
    size_diff = abs(computed_size - recorded_size)
    allow_diff = recorded_size * 0.08
    # If recorded_size is zero and computed_size is non-zero, treat as full difference
    significant_mismatch = False
    if recorded_size == 0:
        significant_mismatch = computed_size != 0
    else:
        significant_mismatch = size_diff > allow_diff
    if significant_mismatch:
        message = (
            f"[{block_id}] WARNING: size_bytes mismatch: recorded {recorded_size}, "
            f"computed {computed_size} (diff {size_diff} bytes)"
        )
        if strict:
            logger.error(message)
            raise BlockValidationError(message)
        logger.warning(message)

    # 3. Hash check
    # Compute sha256 of the encoded bytes used above
    sha256 = hashlib.sha256()
    sha256.update(encoded_bytes)
    computed_hash = sha256.hexdigest()
    if computed_hash != recorded_hash:
        message = (
            f"[{block_id}] WARNING: hash mismatch: recorded {recorded_hash}, "
            f"computed {computed_hash}"
        )
        if strict:
            logger.error(message)
            raise BlockValidationError(message)
        logger.warning(message)

    # 4. Sequence check: ensure 1 <= seq <= total_seqs
    if isinstance(seq, int) and isinstance(total_seqs, int):
        if not (1 <= seq <= total_seqs):
            message = (
                f"[{block_id}] WARNING: sequence number {seq} outside of range "
                f"1..{total_seqs}"
            )
            if strict:
                logger.error(message)
                raise BlockValidationError(message)
            logger.warning(message)

    # 5. Status handling: warn if status is not 'ok'
    status = obj.get("status")
    if status in {"damaged", "binary"}:
        logger.warning(f"[{block_id}] WARNING: block status '{status}'")


def read_block(path: str) -> Dict[str, Any]:
    """Read a JSON block file, validate it and return its dictionary.

    This function reads the specified JSON file, validates its content
    against the block schema, performs additional integrity checks and
    returns the resulting dictionary. If the block's status is other than
    ``"ok"``, soft validation is applied and warnings are logged rather
    than raising exceptions for non-structural issues.

    Parameters:
        path: Path to the JSON block file on disk.

    Returns:
        The parsed block as a dictionary if it passes validation.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If there is an I/O error reading the file.
        json.JSONDecodeError: If the file does not contain valid JSON.
        jsonschema.exceptions.ValidationError: If the block violates the
            JSON schema.
        BlockValidationError: If strict validation fails on additional
            integrity checks (only for blocks with status ``"ok"``).
    """
    # Read the file contents
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure we have a dictionary
    if not isinstance(data, dict):
        raise json.JSONDecodeError(
            f"Block JSON must be an object, got {type(data).__name__}",
            doc=str(data),
            pos=0,
        )

    # Determine whether to use strict validation based on status
    status = data.get("status")
    strict = True if status == "ok" else False
    # Perform validation
    validate_block(data, strict=strict)
    return data