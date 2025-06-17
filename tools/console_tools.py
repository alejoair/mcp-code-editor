"""
Cross-platform Interactive Console Tools using subprocess for MCP Code Editor

Uses subprocess with threading for maximum compatibility across Windows, Linux, and macOS.
Provides tools for managing interactive console processes with snapshot and input capabilities.
"""
import subprocess
import threading
import time
import uuid
import os
import signal
import sys
import re
import queue
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class InteractiveSubprocess:
    """Manages an interactive console process using subprocess with threading."""
    
    def __init__(self, command: str, working_dir: str = None, env: dict = None, name: str = None):
        self.id = str(uuid.uuid4())[:8]
        self.command = command
        self.name = name or f"process_{self.id}"
        self.working_dir = working_dir or os.getcwd()
        self.env = env or os.environ.copy()
        self.process = None
        self.output_buffer = []
        self.start_time = time.time()
        self.end_time = None
        self.is_running = False
        self.max_buffer_lines = 2000
        self._stdout_thread = None
        self._stderr_thread = None
        self._stop_reading = False
        self._output_lock = threading.Lock()
        
    def start(self) -> Dict[str, Any]:
        """Start the interactive process with subprocess."""
        try:
            # Parse command for proper execution
            if isinstance(self.command, str):
                if sys.platform == "win32":
                    # Windows: use shell=True for better command parsing
                    cmd = self.command
                    shell = True
                else:
                    # Unix: try to parse command, fallback to shell if needed
                    import shlex
                    try:
                        cmd = shlex.split(self.command)
                        shell = False
                    except ValueError:
                        cmd = self.command
                        shell = True
            else:
                cmd = self.command
                shell = False
            
            # Start subprocess
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,  # Unbuffered for real-time output
                cwd=self.working_dir,
                env=self.env,
                shell=shell,
                universal_newlines=True
            )
            
            self.is_running = True
            self._stop_reading = False
            
            # Start background readers for stdout and stderr
            self._start_output_readers()
            
            logger.info(f"Started subprocess {self.id}: {self.command}")
            
            return {
                "success": True,
                "process_id": self.id,
                "name": self.name,
                "command": self.command,
                "working_dir": self.working_dir,
                "pid": self.process.pid,
                "backend": "subprocess",
                "message": f"Interactive subprocess started successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to start subprocess {self.id}: {e}")
            self.is_running = False
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "process_id": self.id
            }
    
    def _start_output_readers(self):
        """Start background threads to read stdout and stderr."""
        
        def read_stdout():
            """Read stdout in background thread."""
            try:
                while not self._stop_reading and self.is_running and self.process:
                    try:
                        line = self.process.stdout.readline()
                        if line:
                            with self._output_lock:
                                self.output_buffer.append({
                                    "timestamp": time.time(),
                                    "content": line.rstrip('\n\r'),
                                    "type": "stdout",
                                    "raw": False
                                })
                                # Limit buffer size
                                if len(self.output_buffer) > self.max_buffer_lines:
                                    self.output_buffer = self.output_buffer[-self.max_buffer_lines:]
                        elif self.process.poll() is not None:
                            # Process has terminated
                            break
                    except Exception as e:
                        logger.error(f"Error reading stdout for process {self.id}: {e}")
                        break
            except Exception as e:
                logger.error(f"Fatal error in stdout reader for {self.id}: {e}")
            finally:
                logger.debug(f"Stdout reader thread ended for process {self.id}")
        
        def read_stderr():
            """Read stderr in background thread."""
            try:
                while not self._stop_reading and self.is_running and self.process:
                    try:
                        line = self.process.stderr.readline()
                        if line:
                            with self._output_lock:
                                self.output_buffer.append({
                                    "timestamp": time.time(),
                                    "content": line.rstrip('\n\r'),
                                    "type": "stderr",
                                    "raw": False
                                })
                                # Limit buffer size
                                if len(self.output_buffer) > self.max_buffer_lines:
                                    self.output_buffer = self.output_buffer[-self.max_buffer_lines:]
                        elif self.process.poll() is not None:
                            # Process has terminated
                            break
                    except Exception as e:
                        logger.error(f"Error reading stderr for process {self.id}: {e}")
                        break
            except Exception as e:
                logger.error(f"Fatal error in stderr reader for {self.id}: {e}")
            finally:
                logger.debug(f"Stderr reader thread ended for process {self.id}")
        
        # Start the reader threads
        self._stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        
        self._stdout_thread.start()
        self._stderr_thread.start()
    
    def get_snapshot(self, lines: int = 50, include_timestamps: bool = False, 
                    filter_type: str = "all", since_timestamp: float = None, 
                    raw_output: bool = False) -> Dict[str, Any]:
        """Get a snapshot of recent console output."""
        try:
            with self._output_lock:
                # Filter by timestamp if specified
                filtered_buffer = self.output_buffer
                if since_timestamp:
                    filtered_buffer = [entry for entry in self.output_buffer 
                                     if entry["timestamp"] > since_timestamp]
                
                # Filter by type if specified
                if filter_type != "all":
                    filtered_buffer = [entry for entry in filtered_buffer 
                                     if entry.get("type") == filter_type]
                
                # Get recent lines
                recent_output = filtered_buffer[-lines:] if lines > 0 else filtered_buffer
            
            # Format output
            if raw_output:
                # Return raw output with line breaks
                output_text = '\n'.join([entry["content"] for entry in recent_output])
            else:
                # Process and format output
                formatted_lines = []
                for entry in recent_output:
                    content = entry["content"]
                    
                    if include_timestamps:
                        timestamp = time.strftime("%H:%M:%S", time.localtime(entry["timestamp"]))
                        type_indicator = "[ERR]" if entry["type"] == "stderr" else "[OUT]"
                        if entry["type"] == "input":
                            type_indicator = "[IN ]"
                        formatted_lines.append(f"{timestamp} {type_indicator} {content}")
                    else:
                        formatted_lines.append(content)
                
                output_text = '\n'.join(formatted_lines)
            
            # Check if process is still running
            is_alive = self.is_running and (self.process.poll() is None if self.process else False)
            if not is_alive and self.is_running:
                # Process ended, update our state
                self.is_running = False
                self.end_time = time.time()
            
            uptime = (self.end_time or time.time()) - self.start_time
            
            return {
                "success": True,
                "process_id": self.id,
                "name": self.name,
                "command": self.command,
                "is_running": is_alive,
                "output": output_text,
                "total_lines": len(self.output_buffer),
                "displayed_lines": len(recent_output),
                "uptime_seconds": uptime,
                "pid": self.process.pid if self.process else None,
                "exit_code": self.process.poll() if self.process else None,
                "filter_applied": {
                    "type": filter_type,
                    "since_timestamp": since_timestamp,
                    "lines": lines
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting snapshot for process {self.id}: {e}")
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "process_id": self.id
            }
    
    def send_input(self, input_text: str, send_enter: bool = True, 
                  wait_for_response: bool = False, response_timeout: int = 5,
                  expect_pattern: str = None, clear_input_echo: bool = True) -> Dict[str, Any]:
        """Send input to the interactive process."""
        try:
            if not self.is_running or not self.process:
                return {
                    "success": False,
                    "error": "ProcessNotRunning",
                    "message": "Process is not running",
                    "process_id": self.id
                }
            
            # Check if process is still alive
            if self.process.poll() is not None:
                self.is_running = False
                self.end_time = time.time()
                return {
                    "success": False,
                    "error": "ProcessTerminated", 
                    "message": "Process has terminated",
                    "process_id": self.id,
                    "exit_code": self.process.poll()
                }
            
            # Record current buffer size for response detection
            initial_buffer_size = len(self.output_buffer)
            
            # Send the input
            input_to_send = input_text + ('\n' if send_enter else '')
            self.process.stdin.write(input_to_send)
            self.process.stdin.flush()
            
            # Log the input to our buffer for reference
            with self._output_lock:
                self.output_buffer.append({
                    "timestamp": time.time(),
                    "content": f">>> {input_text}",
                    "type": "input",
                    "raw": False
                })
            
            result = {
                "success": True,
                "process_id": self.id,
                "input_sent": input_text,
                "message": "Input sent successfully"
            }
            
            # Wait for response if requested
            if wait_for_response or expect_pattern:
                response_data = self._wait_for_response(
                    initial_buffer_size, response_timeout, expect_pattern
                )
                result.update(response_data)
            
            logger.info(f"Sent input to process {self.id}: {input_text}")
            
            return result
            
        except BrokenPipeError:
            self.is_running = False
            self.end_time = time.time()
            return {
                "success": False,
                "error": "ProcessTerminated",
                "message": "Process pipe is broken (process may have ended)",
                "process_id": self.id
            }
        except Exception as e:
            logger.error(f"Error sending input to process {self.id}: {e}")
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "process_id": self.id
            }
    
    def _wait_for_response(self, initial_buffer_size: int, timeout: int, 
                          expect_pattern: str = None) -> Dict[str, Any]:
        """Wait for response after sending input."""
        start_time = time.time()
        response_received = False
        response_content = ""
        
        while time.time() - start_time < timeout:
            with self._output_lock:
                current_buffer_size = len(self.output_buffer)
            
            if current_buffer_size > initial_buffer_size:
                # New output received
                with self._output_lock:
                    new_entries = self.output_buffer[initial_buffer_size:]
                    new_content = '\n'.join([entry["content"] for entry in new_entries 
                                           if entry["type"] in ["stdout", "stderr"]])
                
                response_content = new_content
                
                # Check for expected pattern if specified
                if expect_pattern:
                    if re.search(expect_pattern, response_content, re.MULTILINE):
                        response_received = True
                        break
                else:
                    # If no pattern specified, wait a bit more for complete response
                    time.sleep(0.5)
                    with self._output_lock:
                        if len(self.output_buffer) == current_buffer_size:
                            # No new output for 0.5s, consider response complete
                            response_received = True
                            break
            
            time.sleep(0.1)
        
        return {
            "response_received": response_received,
            "response_content": response_content,
            "response_timeout": timeout,
            "wait_time": time.time() - start_time
        }
    
    def terminate(self, force: bool = False, timeout: int = 10) -> Dict[str, Any]:
        """Terminate the interactive process."""
        try:
            if not self.process:
                return {
                    "success": True,
                    "message": "Process was not running",
                    "process_id": self.id
                }
            
            self._stop_reading = True
            self.is_running = False
            self.end_time = time.time()
            
            exit_code = None
            
            if force:
                # Force kill immediately
                self.process.kill()
                action = "killed"
            else:
                # Try graceful termination first
                self.process.terminate()
                action = "terminated"
                
                # Wait for process to finish gracefully
                try:
                    exit_code = self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination failed
                    self.process.kill()
                    action = "force killed after timeout"
                    try:
                        exit_code = self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
            
            if exit_code is None:
                exit_code = self.process.poll()
            
            logger.info(f"Process {self.id} {action} (exit code: {exit_code})")
            
            return {
                "success": True,
                "process_id": self.id,
                "action": action,
                "exit_code": exit_code,
                "uptime_seconds": self.end_time - self.start_time,
                "message": f"Process {action} successfully"
            }
            
        except Exception as e:
            logger.error(f"Error terminating process {self.id}: {e}")
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "process_id": self.id
            }

# Global registry for active processes
_active_processes: Dict[str, InteractiveSubprocess] = {}

def start_console_process(command: str, working_dir: str = None, env_vars: dict = None, 
                         name: str = None, shell: bool = False) -> Dict[str, Any]:
    """
    Start an interactive console process.
    
    Args:
        command: The command to execute
        working_dir: Working directory for the process (optional)
        env_vars: Additional environment variables (optional)
        name: Descriptive name for the process (optional)
        shell: Whether to use shell for execution (optional, auto-detected)
        
    Returns:
        Dictionary with process information and status
    """
    try:
        # Prepare environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        # Create the interactive process
        process = InteractiveSubprocess(command, working_dir, env, name)
        
        # Start the process
        result = process.start()
        
        if result.get("success"):
            # Store in global registry
            _active_processes[process.id] = process
            result["total_active_processes"] = len(_active_processes)
        
        return result
        
    except Exception as e:
        logger.error(f"Error starting console process: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

def check_console(process_id: str, lines: int = 50, include_timestamps: bool = False,
                 filter_type: str = "all", since_timestamp: float = None, 
                 raw_output: bool = False) -> Dict[str, Any]:
    """
    Get a snapshot of console output from an interactive process.
    
    Args:
        process_id: ID of the process to check
        lines: Number of recent lines to retrieve
        include_timestamps: Whether to include timestamps in output
        filter_type: Filter output by type ("all", "stdout", "stderr", "input")
        since_timestamp: Only return output after this timestamp
        raw_output: Return raw terminal output or processed
        
    Returns:
        Dictionary with console snapshot and metadata
    """
    try:
        if process_id not in _active_processes:
            return {
                "success": False,
                "error": "ProcessNotFound",
                "message": f"Process {process_id} not found",
                "available_processes": list(_active_processes.keys())
            }
        
        process = _active_processes[process_id]
        return process.get_snapshot(lines, include_timestamps, filter_type, 
                                  since_timestamp, raw_output)
        
    except Exception as e:
        logger.error(f"Error checking console for process {process_id}: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

def send_to_console(process_id: str, input_text: str, send_enter: bool = True,
                   wait_for_response: bool = False, response_timeout: int = 5,
                   expect_pattern: str = None, clear_input_echo: bool = True) -> Dict[str, Any]:
    """
    Send input to an interactive console process.
    
    Args:
        process_id: ID of the process to send input to
        input_text: Text to send to the process
        send_enter: Whether to append newline to input
        wait_for_response: Whether to wait for response before returning
        response_timeout: Timeout in seconds for waiting for response
        expect_pattern: Regex pattern to wait for in response
        clear_input_echo: Whether to filter input echo from output
        
    Returns:
        Dictionary with send status and response if waited
    """
    try:
        if process_id not in _active_processes:
            return {
                "success": False,
                "error": "ProcessNotFound",
                "message": f"Process {process_id} not found",
                "available_processes": list(_active_processes.keys())
            }
        
        process = _active_processes[process_id]
        return process.send_input(input_text, send_enter, wait_for_response,
                                response_timeout, expect_pattern, clear_input_echo)
        
    except Exception as e:
        logger.error(f"Error sending input to process {process_id}: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

def list_console_processes(include_terminated: bool = False, summary_only: bool = True) -> Dict[str, Any]:
    """
    List all console processes.
    
    Args:
        include_terminated: Whether to include terminated processes
        summary_only: Return only summary or full details
        
    Returns:
        Dictionary with list of processes and their status
    """
    try:
        processes_info = []
        active_count = 0
        terminated_count = 0
        
        for proc_id, process in _active_processes.items():
            is_alive = process.is_running and (process.process.poll() is None if process.process else False)
            
            if not is_alive and process.is_running:
                # Update process state if it ended
                process.is_running = False
                process.end_time = time.time()
            
            if is_alive:
                active_count += 1
            else:
                terminated_count += 1
                if not include_terminated:
                    continue
            
            if summary_only:
                info = {
                    "process_id": proc_id,
                    "name": process.name,
                    "command": process.command[:50] + "..." if len(process.command) > 50 else process.command,
                    "is_running": is_alive,
                    "uptime_seconds": (process.end_time or time.time()) - process.start_time,
                    "pid": process.process.pid if process.process else None,
                    "exit_code": process.process.poll() if process.process else None
                }
            else:
                info = {
                    "process_id": proc_id,
                    "name": process.name,
                    "command": process.command,
                    "working_dir": process.working_dir,
                    "is_running": is_alive,
                    "start_time": process.start_time,
                    "end_time": process.end_time,
                    "uptime_seconds": (process.end_time or time.time()) - process.start_time,
                    "pid": process.process.pid if process.process else None,
                    "exit_code": process.process.poll() if process.process else None,
                    "buffer_lines": len(process.output_buffer)
                }
            
            processes_info.append(info)
        
        return {
            "success": True,
            "total_processes": len(_active_processes),
            "active_processes": active_count,
            "terminated_processes": terminated_count,
            "processes": processes_info
        }
        
    except Exception as e:
        logger.error(f"Error listing console processes: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

def terminate_console_process(process_id: str, force: bool = False, timeout: int = 10) -> Dict[str, Any]:
    """
    Terminate a console process.
    
    Args:
        process_id: ID of the process to terminate
        force: Whether to force kill the process
        timeout: Timeout before force killing
        
    Returns:
        Dictionary with termination status
    """
    try:
        if process_id not in _active_processes:
            return {
                "success": False,
                "error": "ProcessNotFound",
                "message": f"Process {process_id} not found",
                "available_processes": list(_active_processes.keys())
            }
        
        process = _active_processes[process_id]
        result = process.terminate(force, timeout)
        
        return result
        
    except Exception as e:
        logger.error(f"Error terminating process {process_id}: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

def cleanup_terminated_processes() -> Dict[str, Any]:
    """
    Clean up terminated processes from the registry.
    
    Returns:
        Dictionary with cleanup results
    """
    try:
        terminated_ids = []
        
        for proc_id, process in list(_active_processes.items()):
            # Check if process is actually terminated
            if not process.is_running and (not process.process or process.process.poll() is not None):
                # Process is terminated, remove from registry
                del _active_processes[proc_id]
                terminated_ids.append(proc_id)
        
        return {
            "success": True,
            "cleaned_processes": terminated_ids,
            "remaining_processes": len(_active_processes),
            "message": f"Cleaned up {len(terminated_ids)} terminated processes"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up processes: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }
