from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_governance_required_files_exist():
    required = [
        "INTERACTION_PROTOCOL.md",
        "ROADMAP.md",
        "DEV_LOGS.md",
        "WORKFLOW_SNAPSHOT_CONTRACT.md",
        "WORKFLOW_SNAPSHOT_STATE.md",
        "SYSTEM_STATE_CONTRACT.md",
        "SYSTEM_STATE.md",
    ]
    missing = [name for name in required if not (REPO_ROOT / name).exists()]
    assert not missing, f"missing governance files: {missing}"


def test_protocol_sync_markers_present():
    dev_logs = (REPO_ROOT / "DEV_LOGS.md").read_text(encoding="utf-8")
    roadmap = (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8")

    assert "protocol-sync-header-v1" in dev_logs
    assert "workflow-optimization-protocol-sync-v2" in dev_logs
    assert "RADRILONIUMA-PROJECT/v1.0.0@7eadfe9" in roadmap
