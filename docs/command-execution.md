# VSS command execution contract

The command engine is exposed through the `vss` CLI and a language-neutral
JSON envelope. Commands are discovered from modules under
`src/vss_commands/commands`; adding a module with a `CommandMetadata` value and
`@register(METADATA)` handler makes it available without changing CLI
dispatch code.

Examples:

```bash
vss list
vss describe system.info
vss run system.info --environment development
vss run system.info --environment development --dry-run
vss run system.info --environment development --input request.json
```

The request model is:

```json
{
  "schema_version": "1",
  "command": "system.info",
  "environment": "development",
  "correlation_id": "optional-32-character-hex-id",
  "dry_run": false,
  "input": {}
}
```

The response model is deterministic JSON:

```json
{
  "schema_version": "1",
  "command": "system.info",
  "correlation_id": "...",
  "status": "success",
  "exit_code": 0,
  "started_at": "2026-07-26T21:00:00.000Z",
  "completed_at": "2026-07-26T21:00:00.001Z",
  "duration_ms": 1,
  "output": {
    "command_name": "system.info",
    "command_version": "1.0.0",
    "os": "Linux",
    "python_version": "3.12.3",
    "environment": "development",
    "dry_run": false
  },
  "errors": []
}
```

Exit codes are centralized in `vss_commands.exit_codes`: `0` success, `2`
usage, `10` invalid configuration, `11` invalid input, `12` unknown command,
`20` execution failure, `21` timeout, and `30` internal framework error.

The runner loads and validates configuration through `vss_config` before a
handler executes. Input is schema-validated first, output is sorted JSON, and
the reference command deliberately excludes usernames, hostnames, credentials,
environment-variable values, and secrets. Future handlers should preserve
these security boundaries and use the timeout parameter for blocking work.
