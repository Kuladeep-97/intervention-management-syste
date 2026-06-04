import subprocess
import os
import signal

out = subprocess.check_output(['ps', 'aux']).decode('utf-8')
for line in out.splitlines():
    if 'tracker_app/main.py' in line and 'grep' not in line:
        parts = line.split()
        pid = int(parts[1])
        try:
            print(f"Killing PID {pid}")
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            print(f"Failed to kill {pid}: {e}")
