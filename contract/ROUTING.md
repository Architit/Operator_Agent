# [ROUTING CONTRACT: Operator_Agent] (V1.0)

**CONTRACT_ID:** CTL-OP-ROUTING-01
**AUTHORITY:** Sentinel-Guard (GUARD-01) Verification Required

## КАНАЛЫ ДОСТУПА (OPERATIONAL ACCESS):
- `READ/WRITE`: `work/Operator_Agent/data/` (Локальные очереди)
- `READ/WRITE`: `work/Operator_Agent/matrix/` (Контекст маршрутизации)
- `READ`: `work/Operator_Agent/schemas/` (Жесткие схемы данных)

## ПРАВИЛА МАРШРУТИЗАЦИИ:
1. Любой входящий запрос должен быть проанализирован и преобразован в структуру, соответствующую `block.schema.json`.
2. Оператор обязан использовать `matrix/` для обогащения контекста задачи перед её отправкой.
3. Запрещено обращаться к `core/` или `system/` напрямую без записи в `outbox` или директивы Стража.

**ENFORCEMENT:** Любая попытка несанкционированного изменения системных файлов заблокирована Стражем.
