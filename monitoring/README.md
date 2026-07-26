# Monitoring contract

Configure the environment's monitoring platform to collect the timestamped
stderr logs and `metric name=... value=... unit=...` records emitted by Bash
automation. If `METRICS_FILE` is configured, collect its `name value` lines as
a supplemental metrics source.

Required dashboards:

- Deployment attempts, success rate, failure count, and duration by environment.
- Health-check failures and rollback outcomes by release version.
- Automation error logs, searchable by `trace_id`.

Required alerts are listed in `alerts.example.yml`. Each environment must map
their `owner` to an actual on-call escalation route and choose retention that
meets its operational and compliance requirements.
