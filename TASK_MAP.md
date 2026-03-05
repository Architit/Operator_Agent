# TASK_MAP

last_updated_utc: 2026-03-05T15:50:00Z
owner_repo: Operator_Agent
scope: master-plan aligned owner tasks (Phase A/B/C)

| task_id | title | state | owner | notes |
|---|---|---|---|---|
| phaseA_t005 | Task Spec envelope v1.1 ingestion | COMPLETE | OPR-01 | `agent/queue_manager.py`, `tests/test_queue_manager.py` |
| phaseA_t006 | fail-fast error codes for preconditions/integrity | COMPLETE | OPR-01 | `PRECONDITION_FAILED`, `INTEGRITY_MISMATCH` |
| phaseA_closure | Phase A owner closure evidence | COMPLETE | OPR-01 | `gov/report/phaseA_t005_t006_closure_2026-03-05.md` |
| phaseB_B1 | patch runtime guardrails | COMPLETE | OPR-01 | `devkit/patch.sh` (`--sha256/--task-id/--spec-file`) |
| phaseB_B2 | patch runtime contract + tests + wiring | COMPLETE | OPR-01 | `contract/PATCH_RUNTIME_CONTRACT_V1.md`, `tests/test_phase_b_patch_runtime_contract.py`, `scripts/test_entrypoint.sh --patch-runtime` |
| phaseB_closure | Phase B owner closure evidence | COMPLETE | OPR-01 | `gov/report/phaseB_operator_owner_closure_2026-03-05.md` |
| phaseC_C3 | Phase C owner memory wave execution | COMPLETE | OPR-01 | `contract/PHASE_C_MEMORY_OPERATOR_CONTRACT_V1.md`, `tests/test_phase_c_memory_operator_contract.py`, `gov/report/phaseC_operator_wave1_execution_2026-03-05.md` |
