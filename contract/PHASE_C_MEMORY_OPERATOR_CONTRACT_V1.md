# PHASE_C_MEMORY_OPERATOR_CONTRACT_V1

## Scope
- owner_repo: `Operator_Agent`
- phase: `PHASE_C_WAVE_1`
- task_id: `phaseC_operator_wave1_execution`
- status: `DONE`

## Objective
Extend operator governance checks for Phase C memory wave execution while preserving deterministic queue/runtime behavior.

## Required Markers
- `phase_c_operator_memory_contract=ok`
- `phase_c_operator_queue_path=ok`
- `phase_c_runtime_regressions=ok`
- `bridge_policy:c2_bridge_only=ack`

## Test Wiring Contract
- `scripts/test_entrypoint.sh --memory` MUST execute `tests/test_phase_c_memory_operator_contract.py`.
- `scripts/test_entrypoint.sh --patch-runtime` MUST remain green as non-regression gate.

## Constraints
- derivation_only execution
- fail-fast on precondition violations
- no-new-agents-or-repos
