"""
API routes for system metrics and overview.
"""

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
from system_utils import collect_metrics
import asyncio
import pty
import os
import fcntl
import struct
import termios

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    """Get system metrics including CPU, memory, disk, network, and GPU."""
    return collect_metrics()


@router.get("/")
def read_root():
    """Health check endpoint."""
    return {"detail": "ok"}


@router.websocket("/shell")
async def system_shell(websocket: WebSocket):
    """Provide interactive shell access to the system via websocket."""
    await websocket.accept()
    
    try:
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start bash shell in the PTY
        pid = os.fork()
        
        if pid == 0:  # Child process
            os.close(master_fd)
            os.setsid()
            
            # Make the slave the controlling terminal
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            
            # Redirect stdin, stdout, stderr to slave
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            
            if slave_fd > 2:
                os.close(slave_fd)
            
            # Start bash
            os.execvp("bash", ["bash", "-l"])
        
        # Parent process
        os.close(slave_fd)
        
        # Set non-blocking mode
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Set terminal size (80x24 default)
        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
        
        # Task to read from PTY and send to websocket
        async def read_from_pty():
            while True:
                try:
                    await asyncio.sleep(0.01)
                    data = os.read(master_fd, 1024)
                    if data:
                        await websocket.send_text(data.decode('utf-8', errors='ignore'))
                except BlockingIOError:
                    pass
                except OSError:
                    break
                except WebSocketDisconnect:
                    break
        
        # Task to read from websocket and write to PTY
        async def write_to_pty():
            try:
                while True:
                    data = await websocket.receive_text()
                    os.write(master_fd, data.encode('utf-8'))
            except WebSocketDisconnect:
                pass
        
        # Run both tasks concurrently
        await asyncio.gather(
            read_from_pty(),
            write_to_pty(),
            return_exceptions=True
        )
        
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}\r\n")
    finally:
        try:
            os.close(master_fd)
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except:
            pass
        await websocket.close()