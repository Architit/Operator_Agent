# OperatorAgent

OperatorAgent is a system for analysing and processing archived content.  At its core it breaks large files into manageable pieces (blocks) for validation and later processing.  Each block contains metadata and a slice of the original text.  This repository implements the block reading layer along with a strict schema and validation logic.

## Blocks

The **Blocks** layer is responsible for reading JSON files that represent slices of archived text and verifying their integrity.  Each block follows a strict contract and is described by a JSON Schema located at `schemas/block.schema.json`.

### Block contract

Each block is a JSON object containing a defined set of fields; no additional properties are allowed.  The required fields and their meanings are shown below:

| Field          | Type     | Notes                                         |
|---------------|----------|-----------------------------------------------|
| `block_id`     | string   | Unique identifier for the block               |
| `parent_sha256`| string   | SHA‑256 hash of the original full text        |
| `src_file`     | string   | Name of the source file                       |
| `seq`          | integer  | Sequence number of this block (1‑based)       |
| `total_seqs`   | integer  | Total number of blocks in the sequence        |
| `encoding`     | string   | Character encoding of the text (e.g. `utf-8`) |
| `lng`          | string   | Language code (e.g. `ru`, `en`, `nl`)         |
| `status`       | string   | "ok", "damaged" or "binary"                  |
| `size_bytes`   | integer  | Reported size of the text in bytes (≤ 1 MiB)  |
| `hash_sha256`  | string   | SHA‑256 hash of the block’s text              |
| `tags`         | array    | List of tags describing the block             |
| `text`         | string   | Actual text content (≤ 20 000 characters)     |

### Validation checks

When reading a block the following additional checks are performed on top of the schema:

1. **Length**: the `text` must not exceed 20 000 characters.  If it does, a warning is logged and, in strict mode, a `BlockValidationError` is raised.
2. **Size in bytes**: the encoded text must be no larger than 1 MiB (1 048 576 bytes) and the difference between the reported `size_bytes` and the actual encoded length must not exceed 8 %.  Large discrepancies trigger warnings or errors depending on the validation mode.
3. **Hash**: the SHA‑256 hash of the encoded text must match the `hash_sha256` field.  Mismatches result in warnings or errors.
4. **Sequence bounds**: `seq` must be at least 1 and no greater than `total_seqs`.  Out‑of‑range values cause warnings or errors.
5. **Status handling**: blocks with `status` equal to `"damaged"` or `"binary"` are returned without raising integrity errors; a warning is logged to indicate their condition.
6. **Encoding**: the text is encoded using the specified `encoding`.  If the encoding is invalid or the text cannot be encoded, strict mode raises an error; in non‑strict mode a warning is logged and UTF‑8 is used as a fallback.

### Usage example

To read and validate a block from the archive:

```python
from agent.block_reader import read_block, validate_block

# Read a block from disk.  Strict validation is applied automatically
# when the block status is "ok".  Blocks marked as "damaged" or
# "binary" perform soft validation only.
blk = read_block("Archive/DataBlocks/ByFile/Example/blk_000001.json")

# You can also validate a block dictionary directly.  Set strict=False
# to convert validation errors into warnings rather than exceptions.
validate_block(blk, strict=False)
```

The field for language is named **`lng`** (not `lang`).  A block may specify any valid encoding; however, unsupported encodings cause a fallback to UTF‑8 in non‑strict mode.

## Queue

The **Queue** module orchestrates analysis tasks on data blocks.  Tasks are stored in a JSON Lines file (one JSON object per line), for example `Archive/Index/queue.analysis.jsonl`.  Each line represents a single analysis task to be processed by OperatorAgent.

### Queue entry contract

Every queue entry must follow a strict schema.  Required fields and their meanings are listed below:

| Field            | Type            | Notes                                                     |
|------------------|-----------------|-----------------------------------------------------------|
| `id`             | string          | Unique task identifier                                     |
| `block_id`       | string          | Identifier of the data block                               |
| `block_path`     | string          | Path to the block JSON file                                |
| `lng`            | string          | Language code (e.g. `"ru"`, `"en"`)                     |
| `prompt_template`| string          | Name of the prompt template to use                         |
| `status`         | string          | One of `"pending"`, `"in_progress"`, `"done"`, `"error"` |
| `priority`       | integer         | Higher value means higher priority                         |
| `created_at`     | string          | ISO 8601 timestamp when the task was created               |
| `completed_at`   | string \| null  | Completion timestamp; set when status becomes done/error   |
| `result_path`    | string \| null  | Path to result file (for done tasks)                       |
| `error_path`     | string \| null  | Path to error log/dump (for error tasks)                   |
| `error_msg`      | string \| null  | Description of the error (for error tasks)                 |

No other properties are allowed; lines that contain additional fields or invalid data types are rejected during loading.

### Queue management API

The `agent.queue_manager` module provides several functions for working with the queue:

* `load_queue(path: str) -> list[dict]` – reads the JSONL file, parses each non‑empty line as JSON and validates it against the schema.  Malformed JSON lines and entries that do not conform to the schema are skipped with an error log.
* `iter_pending(items: list[dict]) -> list[dict]` – filters tasks with `status == "pending"` and returns them sorted by descending `priority` and ascending `created_at`.
* `mark_in_progress(items, task_id)` – marks a pending task as `in_progress`.  Idempotent: if the task is already in progress or completed, nothing changes and an informative log message is issued.
* `mark_done(items, task_id, result_path, completed_at)` – sets a task’s status to `done` and records the result path and completion time.  Attempts to mark a task that is already `done` or `error` are ignored.
* `mark_error(items, task_id, error_msg, error_path, completed_at)` – sets a task’s status to `error`, recording an error message and location.  Attempts to mark a task that is already `error` or `done` are ignored.
* `save_queue_atomic(path, items)` – writes the list of tasks back to the JSONL file atomically.  The module writes to a temporary file in the same directory, flushes and fsyncs the data, then renames the temporary file over the original.  This ensures that a crash during saving never leaves the queue in a partially written state.

### Error handling

When loading the queue, the module tolerates errors to maximise throughput.  Broken JSON lines trigger a `json.JSONDecodeError` and are logged but skipped.  Entries that fail schema validation raise `jsonschema.ValidationError` during validation; these are also logged as errors and skipped.  I/O errors (such as missing files) propagate to the caller.

Status update functions are designed to be **idempotent**: calling them repeatedly with the same state does not produce duplicate side effects.  Attempts to perform illegal state transitions (for example, marking a completed task as in progress) result in an error log and no state change.

The queue file is saved atomically via the `save_queue_atomic` function: it writes to a temporary `.tmp` file, flushes and fsyncs the data, then replaces the original file via `os.replace()`.  This ensures that either the old or the new version of the queue exists on disk, even if an unexpected interruption occurs during saving.

## Results

The **Results** layer captures the outcomes of block analysis.  After a block has been processed, its summary, classification and signals are stored under `Archive/AnalysisResults/<block_id>.json`.  Each result file contains both high‑level metadata and a nested analysis object.

### Result contract

| Field             | Type             | Notes                                                                   |
|-------------------|------------------|-------------------------------------------------------------------------|
| `block_id`        | string           | Identifier of the analysed block                                         |
| `model`           | string           | Name of the model used for analysis                                      |
| `completed_at`    | string           | ISO 8601 timestamp when analysis completed                               |
| `analysis_version`| string           | Version of the analysis pipeline                                         |
| `analysis`        | object           | See analysis payload description below                                   |

The nested **analysis** object has the following structure:

| Field     | Type              | Notes                                                                    |
|-----------|-------------------|--------------------------------------------------------------------------|
| `summary` | string            | A brief summary (3–5 sentences) of the block                             |
| `keywords`| array of strings  | Up to 12 keywords extracted from the block                               |
| `class`   | string            | One of `"gold"`, `"useful"`, `"rework"`, `"trash"`                   |
| `signals` | object            | Contains arrays of `people`, `projects` and `dates` (all strings)        |
| `actions` | array of strings  | Recommended actions derived from the block                               |
| `risks`   | array of strings  | Identified risks                                                         |
| `quotes`  | array of strings  | Notable quotes or excerpts from the block                                |

The analysis object forbids additional properties.  In the `signals` sub‑object the arrays `people`, `projects` and `dates` are all required, even if they are empty.

### Writing results

Use `agent.result_writer.write_result()` to create a new result file.  This function validates the provided analysis payload, wraps it with metadata and writes it to the appropriate location.  If the file for a given `block_id` already exists, the function logs an INFO message and does not overwrite it (idempotent behaviour).

```python
from agent.result_writer import write_result

analysis = {
    "summary": "Краткий вывод по блоку…",
    "keywords": ["проект", "инновации", "2025"],
    "class": "useful",
    "signals": {
        "people": ["Иван Иванов"],
        "projects": ["Новый продукт"],
        "dates": ["2025-09-01"]
    },
    "actions": ["Связаться с командой"],
    "risks": ["Высокая стоимость"],
    "quotes": ["\"Мы делаем будущее\""]
}

result_path = write_result(
    base_dir=".",
    block_id="blk_000001",
    model="gpt-4o",
    analysis_version="v1",
    analysis_obj=analysis,
    completed_at_iso="2025-08-21T03:30:00Z"
)
print(result_path)
```

### Idempotency

Results are **never overwritten**.  If `write_result()` is called again with the same `block_id`, the existing file is preserved and a log entry is made indicating that the write was skipped.  This guarantees that subsequent analyses do not accidentally erase previous results.

## Errors

The **Errors** layer records information about failures encountered during block analysis.  When an analysis task fails, an error record is saved under `Archive/AnalysisErrors/<block_id>.json`.  Unlike results, multiple error files may exist for a single block: if an error file already exists, a new one is created with a timestamp suffix so that the history of failures is preserved.

### Error contract

| Field          | Type              | Notes                                                                  |
|---------------|-------------------|------------------------------------------------------------------------|
| `block_id`     | string            | Identifier of the block whose analysis failed                          |
| `task_id`      | string            | Identifier of the queue task that produced the error                   |
| `error_type`   | string            | One of `"Network"`, `"RateLimit"`, `"InvalidJSON"`, `"IOError"`         |
| `error_detail` | string            | Detailed description of what went wrong                                |
| `response_text`| string \| null     | Raw response text from the model or service that caused the failure    |
| `timestamp`    | string            | RFC 3339/ISO 8601 timestamp (UTC) when the error occurred              |

No other fields are allowed.  The `response_text` may be omitted (`null`) if there is no raw response available.

### Writing errors

To record an analysis error, use `agent.error_writer.write_error()`.  This function validates the error object, chooses an appropriate filename based on `block_id` and `timestamp`, and writes the JSON to disk.  If a file already exists for the block, the new file name is formed by appending `__<timestamp>` (with punctuation removed) to the block identifier.

```python
from agent.error_writer import write_error

path = write_error(
    base_dir=".",
    block_id="blk_000001",
    task_id="task_000123",
    error_type="InvalidJSON",
    error_detail="Expecting ',' delimiter: line 1 column 100",
    response_text="{...сырой ответ модели...}",
    timestamp_iso="2025-08-21T03:30:00Z"
)
print(path)
```

### Multiple errors per block

It is possible for the same block to encounter multiple errors (for example, repeated attempts with transient failures).  In such cases, every call to `write_error()` generates a new file with a timestamp suffix.  This design preserves the complete history of error occurrences for post‑mortem analysis.

## Logs

OperatorAgent maintains a single log file to capture operational messages, warnings and errors from all modules.  The log file is stored at `Archive/Logs/operator.log` relative to the project root.  Each log entry is formatted on one line as:

```
YYYY-MM-DDTHH:MM:SSZ [LEVEL] message
```

where the timestamp is in UTC (denoted by the trailing `Z`) and `LEVEL` is one of `DEBUG`, `INFO`, `WARNING` or `ERROR`.  Messages include details of block processing, queue operations, result writes and errors.  Secret values such as API keys or tokens should never be logged.

To prevent the log from growing indefinitely, the logger uses size‑based rotation: when `operator.log` reaches approximately 5 MB, it is renamed to `operator.log.1` and a new file is created.  Up to five backup files are kept (e.g. `operator.log.1`, `operator.log.2`, …); older logs are discarded beyond this count.

The default logging level is **INFO**.  You can override this by setting the environment variable `OPERATOR_LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING` or `ERROR` before starting OperatorAgent.  For example, running with `OPERATOR_LOG_LEVEL=DEBUG` will include detailed debug output in the logs.

### Example

To write messages to the log from your own code, obtain a logger instance via `agent.logger.get_logger()`:

```python
from agent.logger import get_logger

log = get_logger(__name__)
log.info("OperatorAgent started")
log.debug("Detailed debugging information…")
```

You can also adjust the logging level at runtime using `agent.logger.set_level('DEBUG')`.  Subsequent messages will obey the new level.
