#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure the package is in the path so we can import tm4server
sys.path.append(str(Path(__file__).parent.parent))

from tm4server.state import StateManager
from tm4server.config import TM4_RUNTIME_ROOT

def main():
    if len(sys.argv) != 2 or sys.argv[1].lower() not in {"run", "pause", "halt"}:
        print("Usage: python scripts/set_control_mode.py [run|pause|halt]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    
    # Initialize StateManager with the configured runtime root
    # This will ensure defaults exist if they don't already
    state = StateManager(runtime_root=TM4_RUNTIME_ROOT)
    
    try:
        state.set_control_mode(mode, source="cli")
        print(f"Successfully set control mode to: {mode}")
    except Exception as e:
        print(f"Error updating control mode: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
