"""
Queue management utilities for OperatorAgent.

This module defines a schema for queue entries and provides functions to
load tasks from a JSON Lines file, filter pending tasks, update their
status and save the queue back to disk in an atomic manner. Each line of
the queue file represents a single task and must conform to the
``schemas/queue_line.schema.json`` definition. Malformed lines or entries
that do not validate against the schema are skipped with an error log.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import jsonschema

logger = logging.getLogger(__name__)


def _load_schema() -> Dict[str, Any]:
    """Load the queue entry JSON schema from the schemas directory."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    schema_path = project_root / "schemas" / "queue_line.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# Load the schema once at module import
_QUEUE_SCHEMA: Dict[str, Any] = _load_schema()


def load_queue(path: str) -> List[Dict[str, Any]]:
    """Load tasks from a JSON Lines queue file.

    Each non-empty line in the file is parsed as JSON and validated
    against the queue entry schema. Lines that are not valid JSON or
    that fail schema validation are skipped with an error logged.

    Parameters:
        path: Path to the queue file on disk.

    Returns:
        A list of valid task dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: For other I/O related errors.
    """
    items: List[Dict[str, Any]] = []
    lines_processed = 0
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.rstrip("\n\r")
            if not line:
                # skip empty lines without counting
                continue
            lines_processed += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON at line {idx}: {e}")
                continue
            try:
                jsonschema.validate(instance=entry, schema=_QUEUE_SCHEMA)
            except jsonschema.ValidationError as e:
                logger.error(f"Invalid queue entry at line {idx}: {e.message}")
                continue
            # at this point entry is a valid dict per schema
            items.append(entry)
    skipped = lines_processed - len(items)
    logger.info(
        f"Loaded {len(items)} task(s) from queue file {path}"
        + (f", skipped {skipped} invalid line(s)" if skipped else "")
    )
    return items


def _parse_datetime(dt: Optional[str]) -> Any:
    """Parse an ISO 8601 date-time string into a datetime for sorting.

    If parsing fails, the original string is returned to allow
    lexicographic comparison as a fallback. This helper accepts None and
    returns None unchanged.
    """
    if dt is None:
        return None
    dt = dt.strip()
    if not dt:
        return dt
    # Handle trailing 'Z' as UTC
    try:
        if dt.endswith("Z"):
            # Convert 'Z' to '+00:00' for fromisoformat
            dt_iso = dt[:-1] + "+00:00"
            return datetime.fromisoformat(dt_iso)
        return datetime.fromisoformat(dt)
    except Exception:
        # Try a more generic format without timezone
        try:
            return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            logger.warning(f"Could not parse datetime '{dt}': {e}")
            return dt


def iter_pending(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a list of tasks with status 'pending' sorted by priority and created_at.

    The returned tasks are sorted by descending priority and then by
    ascending creation time. Tasks with missing or unparsable date-times
    fall back to lexicographic ordering of the original string.

    Parameters:
        items: List of task dictionaries loaded from the queue.

    Returns:
        A list of pending task dictionaries in the desired order.
    """
    pending = [task for task in items if task.get("status") == "pending"]
    # Sorting: priority descending, created_at ascending
    pending.sort(
        key=lambda task: (
            -task.get("priority", 0),
            _parse_datetime(task.get("created_at"))
        )
    )
    return pending


def mark_in_progress(items: List[Dict[str, Any]], task_id: str) -> None:
    """Mark a task as in-progress by updating its status.

    If the task is already in progress, done or error, no changes are made.

    Parameters:
        items: List of task dictionaries loaded from the queue.
        task_id: Identifier of the task to update.
    """
    task = next((t for t in items if t.get("id") == task_id), None)
    if task is None:
        logger.error(f"mark_in_progress: Task {task_id} not found")
        return
    current_status = task.get("status")
    if current_status == "in_progress":
        logger.info(f"Task {task_id} is already in_progress (no change)")
        return
    if current_status in ("done", "error"):
        logger.error(
            f"Cannot mark task {task_id} as in_progress (already {current_status})"
        )
        return
    task["status"] = "in_progress"
    logger.info(f"Task {task_id} marked as in_progress")


def mark_done(
    items: List[Dict[str, Any]],
    task_id: str,
    result_path: str,
    completed_at: str,
) -> None:
    """Mark a task as done and record its result path and completion time.

    Parameters:
        items: List of task dictionaries loaded from the queue.
        task_id: Identifier of the task to update.
        result_path: File path to the result produced by the task.
        completed_at: ISO 8601 timestamp of completion.
    """
    task = next((t for t in items if t.get("id") == task_id), None)
    if task is None:
        logger.error(f"mark_done: Task {task_id} not found")
        return
    current_status = task.get("status")
    if current_status == "done":
        logger.info(f"Task {task_id} is already done (no change)")
        return
    if current_status == "error":
        logger.error(f"Cannot mark task {task_id} as done (already error)")
        return
    # Set status and update paths
    task["status"] = "done"
    task["result_path"] = result_path
    task["completed_at"] = completed_at
    # Clear error fields
    task["error_path"] = None
    task["error_msg"] = None
    logger.info(f"Task {task_id} marked as done")


def mark_error(
    items: List[Dict[str, Any]],
    task_id: str,
    error_msg: str,
    error_path: str,
    completed_at: str,
) -> None:
    """Mark a task as failed, recording error information and completion time.

    Parameters:
        items: List of task dictionaries loaded from the queue.
        task_id: Identifier of the task to update.
        error_msg: Error description.
        error_path: Path to an error log or dump file.
        completed_at: ISO 8601 timestamp of when the error occurred.
    """
    task = next((t for t in items if t.get("id") == task_id), None)
    if task is None:
        logger.error(f"mark_error: Task {task_id} not found")
        return
    current_status = task.get("status")
    if current_status == "error":
        logger.info(f"Task {task_id} is already error (no change)")
        return
    if current_status == "done":
        logger.error(f"Cannot mark task {task_id} as error (already done)")
        return
    task["status"] = "error"
    task["error_msg"] = error_msg
    task["error_path"] = error_path
    task["completed_at"] = completed_at
    # Clear result path
    task["result_path"] = None
    logger.info(f"Task {task_id} marked as error")


def save_queue_atomic(path: str, items: List[Dict[str, Any]]) -> None:
    """Save the list of tasks to the JSON Lines file atomically.

    The queue is written to a temporary file in the same directory, flushed
    and synced to disk, then renamed over the original file. This ensures
    that the queue file is never left in a partially written state.

    Parameters:
        path: Path to the queue file on disk.
        items: List of task dictionaries to serialize and write.

    Raises:
        OSError: If writing to the file fails.
    """
    dir_name = os.path.dirname(path) or "."
    tmp_file = None
    try:
        import tempfile

        tmp_file = tempfile.NamedTemporaryFile(
            "w", delete=False, dir=dir_name, encoding="utf-8"
        )
        for task in items:
            tmp_file.write(json.dumps(task, ensure_ascii=False) + "\n")
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        temp_path = tmp_file.name
    except Exception as e:
        logger.error(f"Failed to write queue to temp file: {e}")
        if tmp_file:
            try:
                tmp_file.close()
            except Exception:
                pass
            try:
                os.remove(tmp_file.name)
            except Exception:
                pass
        raise
    finally:
        if tmp_file:
            tmp_file.close()
    try:
        os.replace(temp_path, path)
        logger.info(f"Queue saved to {path}")
    except Exception as e:
        logger.error(f"Failed to replace queue file: {e}")
        try:
            os.remove(temp_path)
        except Exception:
            pass
        raise