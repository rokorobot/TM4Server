# TM4 Operator Workflow

How to submit, monitor, and troubleshoot experiments.

## Submitting a Job
Use the `submit_run.py` script:
```bash
python -m tm4server.submit_run --exp-id EXP-AUT-101 --task main_eval --model gpt-4o
```
This writes a JSON manifest to `queue/queued/`.

## Monitoring Status
1. **Runner Logs**:
   ```bash
   tail -f /var/log/tm4/tm4-runner.log
   ```
2. **Current State**:
   ```bash
   cat /var/lib/tm4/state/status.json
   ```
3. **Execution Folder**:
   ```bash
   ls -R /var/lib/tm4/runs/EXP-AUT-101
   ```

## Handling Failures
If a job enters `queue/failed/`:
1. Check `runs/<exp-id>/stdout.log` for error details.
2. Fix the issues (code or configuration).
3. Re-submit by moving the manifest back to `queue/queued/` (manual or script) or run a new `submit_run.py` with a new version tag.

## Artifact Collection
Finished jobs store their primary results in `results.json` and logs in `stdout.log` within their dedicated run folders. Large outputs should be directed into `artifacts/`.
