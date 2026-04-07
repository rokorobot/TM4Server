# TM4 Operator Workflow

How to submit, monitor, and troubleshoot experiments.

## Submitting a Job

### Basic
```bash
python -m tm4server.submit_run --exp-id EXP-AUT-0010 --task sanity_check --model qwen2.5:3b
```

### With parameters
```bash
python -m tm4server.submit_run \
  --exp-id EXP-AUT-0011 \
  --task gradient_probe \
  --model qwen2.5:3b \
  --params-json '{"anchor_regime":"A1_WEAKENED","mutation_rate":0.05}'
```

Manifests are written to `queue/queued/` as clean UTF-8 JSON files.

---

## Monitoring a Run

### Runtime state
```bash
cat local_runtime/state/status.json           # local
cat /var/lib/tm4/state/status.json            # server
```

### Live logs (server)
```bash
tail -f /var/log/tm4/tm4-runner.log
```

### Run folder contents
```bash
ls -la local_runtime/runs/EXP-AUT-0011/
```

Expected files per run:
- `manifest.json` — original job input
- `tm4_input_manifest.json` — sanitised payload handed to TM4 core
- `config.json` — full resolved config snapshot (paths, git hashes)
- `event_log.jsonl` — TM4Server event trail
- `stdout.log` — combined execution log
- `stderr.log` — subprocess stderr
- `results.json` — summary with duration and git hashes
- `status.json` — final status with `preflight_status`

---

## Reading the Event Log

Each line in `event_log.jsonl` is a JSON event:

```jsonl
{"ts_utc": "...", "event": "job_picked", "experiment_id": "EXP-AUT-0011"}
{"ts_utc": "...", "event": "preflight_passed"}
{"ts_utc": "...", "event": "subprocess_started", "command": "python", "script": "..."}
{"ts_utc": "...", "event": "subprocess_completed", "return_code": 0, "duration_s": 87.3}
{"ts_utc": "...", "event": "manifest_moved_completed", "destination": "completed"}
```

---

## Handling Failures

If a job enters `queue/failed/`:

1. Check `runs/<exp-id>/status.json` for `preflight_status` and errors.
2. Check `runs/<exp-id>/stderr.log` for subprocess errors.
3. Check `runs/<exp-id>/event_log.jsonl` to see at which stage it failed.
4. Fix the issue, then re-submit with a new `--exp-id` or re-queue the manifest.

### Re-queue a failed job (server)
```bash
mv /var/lib/tm4/queue/failed/EXP-AUT-0011.json /var/lib/tm4/queue/queued/
```

---

## Checking Queue counts

```bash
bash scripts/check_runtime.sh
```

Or manually:
```bash
echo "Queued:    $(ls local_runtime/queue/queued | wc -l)"
echo "Running:   $(ls local_runtime/queue/running | wc -l)"
echo "Completed: $(ls local_runtime/queue/completed | wc -l)"
echo "Failed:    $(ls local_runtime/queue/failed | wc -l)"
```
