"""
VNC WebSocket Proxy Manager for VM Console Access
"""
import subprocess
import os
import signal
from typing import Optional

PROXY_PID_FILE = "/tmp/upcode_harbor_vnc_proxy.pid"
PROXY_PORT = 6080

def is_proxy_running() -> bool:
    """Check if the VNC proxy is already running."""
    if not os.path.exists(PROXY_PID_FILE):
        return False
    
    try:
        with open(PROXY_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False

def start_proxy() -> bool:
    """Start the VNC WebSocket proxy if not already running."""
    if is_proxy_running():
        return True
    
    try:
        # Listen on 0.0.0.0:6080 and forward to localhost:5900-5999
        process = subprocess.Popen(
            ["websockify", "--web=/usr/share/novnc", f"0.0.0.0:{PROXY_PORT}", "localhost:5900"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        with open(PROXY_PID_FILE, "w") as f:
            f.write(str(process.pid))
        
        return True
    except Exception as e:
        print(f"Failed to start VNC proxy: {e}")
        return False

def stop_proxy() -> bool:
    """Stop the VNC WebSocket proxy."""
    if not os.path.exists(PROXY_PID_FILE):
        return True
    
    try:
        with open(PROXY_PID_FILE) as f:
            pid = int(f.read().strip())
        
        os.kill(pid, signal.SIGTERM)
        os.remove(PROXY_PID_FILE)
        return True
    except (OSError, ValueError) as e:
        print(f"Failed to stop VNC proxy: {e}")
        return False

def ensure_proxy_running() -> bool:
    """Ensure the VNC proxy is running, start if needed."""
    return is_proxy_running() or start_proxy()
