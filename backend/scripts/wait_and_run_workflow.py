"""
Monitor extraction and run workflow when JSONL is ready.
"""

import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

JSONL_PATH = Path("data/hts_tariff/structured_hts_codes_v2_clean.jsonl")
EXTRACTOR_PID = 9358  # Current PID
CHECK_INTERVAL = 10  # Check every 10 seconds
MAX_WAIT = 3600  # Max 1 hour wait

def check_process_running(pid):
    """Check if process is still running."""
    try:
        result = subprocess.run(['ps', '-p', str(pid)], capture_output=True, text=True)
        return str(pid) in result.stdout
    except:
        return False

def check_file_exists():
    """Check if JSONL file exists and has content."""
    jsonl_path = Path(__file__).parent.parent.parent / JSONL_PATH
    if jsonl_path.exists():
        # Check if file has content (not just created empty)
        try:
            size = jsonl_path.stat().st_size
            if size > 1000:  # At least 1KB
                return True, size
        except:
            pass
    return False, 0

def check_file_stable(jsonl_path, stability_window=60):
    """
    Check if file size is stable (unchanged for stability_window seconds).
    
    Returns: (is_stable, current_size, last_change_time)
    """
    if not jsonl_path.exists():
        return False, 0, None
    
    try:
        current_size = jsonl_path.stat().st_size
        current_mtime = jsonl_path.stat().st_mtime
        
        # Check if file was modified recently
        time_since_mod = time.time() - current_mtime
        
        # File is stable if it hasn't been modified in the last stability_window seconds
        is_stable = time_since_mod >= stability_window
        
        return is_stable, current_size, current_mtime
    except:
        return False, 0, None

def main():
    """Monitor and run workflow when ready."""
    print("=" * 80)
    print("Extraction Monitor - Waiting for JSONL file")
    print("=" * 80)
    print(f"Monitoring process PID: {EXTRACTOR_PID}")
    print(f"Waiting for file: {JSONL_PATH}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Stability window: 60 seconds")
    print()
    
    start_time = time.time()
    last_status = None
    file_size_history = {}  # Track file sizes over time
    stability_window = 60  # File must be stable for 60 seconds
    
    jsonl_path = Path(__file__).parent.parent.parent / JSONL_PATH
    
    while True:
        elapsed = int(time.time() - start_time)
        
        # Step 1: Check if process is still running
        process_running = check_process_running(EXTRACTOR_PID)
        
        if process_running:
            status = f"[{elapsed}s] Waiting for PID {EXTRACTOR_PID} to exit..."
            if status != last_status:
                print(status)
                last_status = status
            time.sleep(CHECK_INTERVAL)
            continue
        
        # Step 2: Process finished, check if file exists
        file_exists, file_size = check_file_exists()
        
        if not file_exists:
            status = f"[{elapsed}s] Process finished. Waiting for JSONL file to exist..."
            if status != last_status:
                print(status)
                last_status = status
            time.sleep(CHECK_INTERVAL)
            continue
        
        # Step 3: File exists, check if size is stable
        is_stable, current_size, last_mtime = check_file_stable(jsonl_path, stability_window)
        
        # Track file size over time
        now = time.time()
        file_size_history[now] = current_size
        
        # Remove old entries (older than stability_window)
        cutoff = now - stability_window
        file_size_history = {t: s for t, s in file_size_history.items() if t > cutoff}
        
        # Check if size has been constant
        if len(file_size_history) > 1:
            sizes = list(file_size_history.values())
            size_constant = all(s == current_size for s in sizes)
            time_since_first_check = max(file_size_history.keys()) - min(file_size_history.keys())
            
            if size_constant and time_since_first_check >= stability_window:
                is_stable = True
        
        if not is_stable:
            time_since_mod = now - last_mtime if last_mtime else 0
            status = f"[{elapsed}s] Waiting for JSONL size to stabilize... (current: {current_size:,} bytes, modified {int(time_since_mod)}s ago)"
            if status != last_status:
                print(status)
                last_status = status
            time.sleep(CHECK_INTERVAL)
            continue
        
        # All conditions met: process finished, file exists, size is stable
        print()
        print("=" * 80)
        print("✅ All conditions met!")
        print("=" * 80)
        print(f"Process PID {EXTRACTOR_PID}: FINISHED")
        print(f"File exists: {jsonl_path}")
        print(f"File size: {current_size:,} bytes ({current_size / 1024 / 1024:.2f} MB)")
        print(f"Size stable for: {stability_window} seconds")
        print()
        print("Running workflow script...")
        print()
        
        # Run the workflow
        workflow_script = Path(__file__).parent / "run_new_version_workflow.py"
        result = subprocess.run(
            [sys.executable, str(workflow_script)],
            cwd=str(Path(__file__).parent.parent),
            capture_output=False
        )
        
        sys.exit(result.returncode)
        
        if elapsed > MAX_WAIT:
            print()
            print(f"❌ Timeout after {MAX_WAIT} seconds")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
