# tasks/ (ADR-0504)

Per-task assertion suites (`test_*.py`): `live_read_tool` is one of
the task's own `allowed_tools`; `primary_task` appears in
`zuno.tasks`; a `project_required` task (ADR-0512) declares at least
one project-scopable resource. Static repository checks only.
