from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_phase_d_transport_operator_contract_markers() -> None:
    text = (REPO_ROOT / "contract" / "PHASE_D_TRANSPORT_OPERATOR_CONTRACT_V1.md").read_text(encoding="utf-8")
    assert "PHASE_D_TRANSPORT_OPERATOR_CONTRACT_V1" in text
    assert "phase_d_transport_operator_contract=ok" in text
    assert "phase_d_transport_queue_path=ok" in text
    assert "phase_d_runtime_regressions=ok" in text


def test_transport_mode_wiring_exists_in_test_entrypoint() -> None:
    text = (REPO_ROOT / "scripts" / "test_entrypoint.sh").read_text(encoding="utf-8")
    assert "--transport" in text
    assert "test_phase_d_transport_operator_contract.py" in text
