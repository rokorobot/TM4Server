import re
from typing import Optional, Any

# Failure Taxonomy v1
FAILURE_CLASS_INFRA = "infra_error"
FAILURE_CLASS_EXECUTION = "execution_error"
FAILURE_CLASS_MODEL = "model_error"
FAILURE_CLASS_CONTRACT = "contract_error"
FAILURE_CLASS_INPUT = "input_error"
FAILURE_CLASS_INTERRUPTED = "interrupted"
FAILURE_CLASS_UNKNOWN = "unknown"

# Signals & Patterns
PATTERNS_INFRA = {
    r"Killed": "Process killed (possible OOM)",
    r"Out of memory": "Host OOM detected",
    r"OOM killer": "Linux OOM killer triggered",
    r"timed out": "Operation timed out",
    r"timeout": "Operation timed out",
    r"Connection refused": "Network connection refused",
    r"No space left on device": "Disk full",
}

PATTERNS_EXECUTION = {
    r"Traceback \(most recent call last\):": "Python Traceback",
    r"Exception:": "Runtime Exception",
    r"ValueError:": "ValueError",
    r"KeyError:": "KeyError",
}

EXIT_CODE_MAP = {
    137: FAILURE_CLASS_INFRA, # SIGKILL (often OOM)
    124: FAILURE_CLASS_INFRA, # Timeout command exit
}

class SignalProcessor:
    """
    Deterministic signal processor for failure classification.
    Processes exit codes, log patterns, and artifact health.
    """
    
    @staticmethod
    def classify(record: dict) -> dict[str, Any]:
        """
        Derives failure intelligence from a canonical Run Record.
        Returns a populated intelligence block.
        """
        identity = record.get("identity", {})
        execution = record.get("execution", {})
        outcome = record.get("outcome", {})
        logs = record.get("logs", {})
        gov = record.get("governance", {})
        
        status = execution.get("status")
        exit_code = outcome.get("exit_code")
        stderr_tail = logs.get("stderr", {}).get("content", "")
        
        failure_class = FAILURE_CLASS_UNKNOWN
        failure_reason = None
        source = "none"
        confidence = 0.0
        
        # 1. Success case
        if status == "success":
            return {
                "failure_class": None,
                "failure_reason": None,
                "interrupted": False,
                "retry_recommended": False,
                "confidence": 1.0,
                "source": "none"
            }

        # 2. Interrupted Detection
        if status == "interrupted":
            failure_class = FAILURE_CLASS_INTERRUPTED
            failure_reason = "Worker PID disappeared or process terminated externally"
            source = "derived_v1_status"
            confidence = 1.0

        # 3. Contract Violations (Highest Priority Forensic Signal)
        if failure_class == FAILURE_CLASS_UNKNOWN:
            if gov.get("validation_errors"):
                failure_class = FAILURE_CLASS_CONTRACT
                failure_reason = f"Spec v1 violation: {gov['validation_errors'][0]}"
                source = "derived_v1_contract"
                confidence = 1.0
            elif not record.get("artifacts_meta", {}).get("summary_present") and execution.get("is_terminal"):
                 failure_class = FAILURE_CLASS_CONTRACT
                 failure_reason = "Run marked terminal but missing run_summary.json"
                 source = "derived_v1_contract"
                 confidence = 1.0

        # 4. Exit Code Mapping
        if failure_class == FAILURE_CLASS_UNKNOWN and exit_code in EXIT_CODE_MAP:
            failure_class = EXIT_CODE_MAP[exit_code]
            failure_reason = f"Exit code {exit_code} mapped to {failure_class}"
            source = "derived_v1_exitcode"
            confidence = 1.0

        # 5. Log Pattern Matching (Stderr)
        if failure_class == FAILURE_CLASS_UNKNOWN:
            # Check Infra Patterns
            for pattern, reason in PATTERNS_INFRA.items():
                if re.search(pattern, stderr_tail, re.IGNORECASE):
                    failure_class = FAILURE_CLASS_INFRA
                    failure_reason = reason
                    source = "derived_v1_stderr"
                    confidence = 1.0
                    break
            
            # Check Execution Patterns
            if failure_class == FAILURE_CLASS_UNKNOWN:
                for pattern, reason in PATTERNS_EXECUTION.items():
                    if re.search(pattern, stderr_tail):
                        failure_class = FAILURE_CLASS_EXECUTION
                        failure_reason = reason
                        source = "derived_v1_stderr"
                        confidence = 1.0
                        break

        # 6. Retry Policy
        retry_recommended = (failure_class in {FAILURE_CLASS_INFRA, FAILURE_CLASS_INTERRUPTED})
        
        # Ensure confidence invariant: if source is derived, confidence must be > 0
        if source != "none" and confidence == 0.0:
            confidence = 0.5 # Default fallback for derived data

        return {
            "failure_class": failure_class if failure_class != FAILURE_CLASS_UNKNOWN else None,
            "failure_reason": failure_reason,
            "interrupted": (status == "interrupted"),
            "retry_recommended": retry_recommended,
            "confidence": confidence,
            "source": source
        }
