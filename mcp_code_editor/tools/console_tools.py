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
import shutil
import platform
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Set up console debugging if needed
if os.environ.get('MCP_DEBUG_CONSOLE', '').lower() in ('1', 'true', 'yes'):
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

# Universal newline normalization
def normalize_to_unix_newlines(text: str) -> str:
    """Normalize ALL text to use Unix-style \n newlines universally."""
    if not text:
        return text
    
    # Replace all variations of line endings with \n
    text = text.replace('\r\n', '\n')  # Windows CRLF -> LF
    text = text.replace('\r', '\n')    # Mac CR -> LF
    text = text.replace('\n\n', '\n')  # Remove double newlines that might be created
    
    return text

# Platform and environment detection utilities
def detect_environment() -> Dict[str, Any]:
    """Detect the current execution environment and console type."""
    env_info = {
        "platform": platform.system().lower(),
        "is_windows": sys.platform == "win32",
        "is_wsl": False,
        "is_ssh": False,
        "is_docker": False,
        "shell_type": "unknown",
        "encoding": "utf-8",
        "line_ending": "\n",
        "needs_special_handling": False
    }
    
    # Detect WSL
    try:
        if env_info["platform"] == "linux":
            # Check for WSL in multiple ways
            wsl_indicators = [
                "/proc/version",  # Contains "Microsoft" or "WSL"
                "/proc/sys/fs/binfmt_misc/WSLInterop",  # WSL2 specific
            ]
            
            for indicator in wsl_indicators:
                try:
                    if os.path.exists(indicator):
                        with open(indicator, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if 'microsoft' in content or 'wsl' in content:
                                env_info["is_wsl"] = True
                                env_info["needs_special_handling"] = True
                                break
                except (OSError, IOError):
                    continue
            
            # Additional WSL detection via environment variables
            if not env_info["is_wsl"]:
                wsl_env_vars = ["WSL_DISTRO_NAME", "WSL_INTEROP", "WSLENV"]
                if any(var in os.environ for var in wsl_env_vars):
                    env_info["is_wsl"] = True
                    env_info["needs_special_handling"] = True
    except Exception as e:
        logger.debug(f"Error detecting WSL: {e}")
    
    # Detect SSH session
    ssh_indicators = ["SSH_CLIENT", "SSH_CONNECTION", "SSH_TTY"]
    if any(var in os.environ for var in ssh_indicators):
        env_info["is_ssh"] = True
        env_info["needs_special_handling"] = True
    
    # Detect Docker
    docker_indicators = [
        os.path.exists("/.dockerenv"),
        "container" in os.environ.get("HOSTNAME", "").lower(),
        os.path.exists("/proc/1/cgroup") and "docker" in open("/proc/1/cgroup", "r").read()
    ]
    if any(docker_indicators):
        env_info["is_docker"] = True
        env_info["needs_special_handling"] = True
    
    # Determine shell type
    shell = os.environ.get("SHELL", "").lower()
    if "bash" in shell:
        env_info["shell_type"] = "bash"
    elif "zsh" in shell:
        env_info["shell_type"] = "zsh"
    elif "fish" in shell:
        env_info["shell_type"] = "fish"
    elif "powershell" in shell or "pwsh" in shell:
        env_info["shell_type"] = "powershell"
    elif env_info["is_windows"]:
        env_info["shell_type"] = "cmd"
    
    # Set platform-specific defaults
    if env_info["is_windows"]:
        env_info["encoding"] = "cp1252"  # Common Windows encoding
        env_info["line_ending"] = "\r\n"
    elif env_info["is_wsl"]:
        env_info["encoding"] = "utf-8"
        env_info["line_ending"] = "\n"
        env_info["needs_special_handling"] = True
    
    return env_info

def clean_text_output(text: str) -> str:
    """Clean text output for better console compatibility."""
    if not text:
        return text
    
    # Normalize to Unix newlines
    text = normalize_to_unix_newlines(text)
    
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Remove problematic control characters
    text = text.replace('\x00', '').replace('\x08', '')
    
    # Clean up lines - remove trailing whitespace
    lines = text.split('\n')
    cleaned_lines = [line.rstrip() for line in lines]
    
    # Remove trailing empty lines
    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()
    
    return '\n'.join(cleaned_lines)

def clean_text_input(text: str) -> bytes:
    """Clean text input and convert to UTF-8 bytes for sending to console."""
    if not text:
        return b''
    
    # Clean problematic characters
    text = text.replace('\r', '')
    text = text.replace('\\r', '').replace('\\n', '\n').replace('\\t', '\t')
    text = text.replace('\\\\r', '').replace('\\\\n', '\n')
    
    # Normalize to Unix newlines and remove control chars
    text = normalize_to_unix_newlines(text)
    text = ''.join(char for char in text if ord(char) >= 32 or char in ['\n', '\t'])
    
    # Convert to bytes
    return text.encode('utf-8')

def get_subprocess_config(env_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get optimized subprocess configuration for the current environment."""
    if env_info is None:
        env_info = detect_environment()
    
    # Use binary mode to avoid automatic newline conversion
    config = {
        "text": False,  # Use binary mode to control newlines exactly
        "bufsize": 0,  # Unbuffered
    }
    
    # Add Windows-specific configuration for better WSL support
    if env_info.get("is_windows", False):
        config.update({
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0,
            "startupinfo": subprocess.STARTUPINFO() if hasattr(subprocess, 'STARTUPINFO') else None
        })
        
        # Configure startup info to hide console window for better control
        if config["startupinfo"]:
            config["startupinfo"].dwFlags |= subprocess.STARTF_USESHOWWINDOW
            config["startupinfo"].wShowWindow = subprocess.SW_HIDE
    
    return config

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
        
        # Detect environment for optimized handling
        self.env_info = detect_environment()
        logger.info(f"Environment detected for process {self.id}: {self.env_info}")
        
        # Get subprocess configuration optimized for this environment
        self.subprocess_config = get_subprocess_config(self.env_info)
        self.start_time = time.time()
        self.end_time = None
        self.is_running = False
        self.max_buffer_lines = 2000
        self._stdout_thread = None
        self._stderr_thread = None
        self._stop_reading = False
        self._output_lock = threading.Lock()
        self.last_activity_time = time.time()
        self.awaiting_input_patterns = [
            r'>>>\s*$',  # Python prompt
            r'\$\s*$',   # Shell prompt
            r'#\s*$',    # Root shell
            r'>\s*$',    # Windows cmd
            r':\s*$',    # Some CLIs end with colon
            r'\?\s*$',   # Question prompts
        ]
        self.background_process_patterns = [
            r'server\s+(?:running|started|listening)',  # Server indicators
            r'listening\s+on\s+port',                   # Port listening
            r'serving\s+at',                            # Serving indicators
            r'daemon\s+started',                        # Daemon processes
            r'worker\s+ready',                          # Worker processes
            r'Respuesta\s+desde\s+\d+',                 # Ping responses (Spanish)
            r'Reply\s+from\s+\d+',                      # Ping responses (English)
            r'bytes=\d+\s+tiempo=\d+ms',                # Ping timing (Spanish)
            r'bytes=\d+\s+time=\d+ms',                  # Ping timing (English)
            r'ping\s+statistics',                       # Ping end statistics
        ]
        
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
            
            # Start subprocess with optimized configuration
            subprocess_kwargs = {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "env": self.env,
                "shell": shell,
            }
            
            # Set working directory if provided
            if self.working_dir:
                subprocess_kwargs["cwd"] = self.working_dir
                logger.debug(f"Setting working directory: {self.working_dir}")
            else:
                logger.debug(f"No working directory specified, using default")
            
            subprocess_kwargs.update(self.subprocess_config)
            
            self.process = subprocess.Popen(cmd, **subprocess_kwargs)
            
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
                        line_bytes = self.process.stdout.readline()
                        if line_bytes:
                            line = line_bytes.decode('utf-8', errors='replace')
                            # Debug logging for WSL issues
                            logger.debug(f"[{self.id}] Raw stdout: {repr(line_bytes[:100])}")
                            
                            with self._output_lock:
                                cleaned_line = clean_text_output(line)
                                logger.debug(f"[{self.id}] Cleaned stdout: {repr(cleaned_line)}")
                                
                                self.output_buffer.append({
                                    "timestamp": time.time(),
                                    "content": cleaned_line,
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
                        line_bytes = self.process.stderr.readline()
                        if line_bytes:
                            line = line_bytes.decode('utf-8', errors='replace')
                            # Debug logging for WSL issues
                            logger.debug(f"[{self.id}] Raw stderr: {repr(line_bytes[:100])}")
                            
                            with self._output_lock:
                                cleaned_line = clean_text_output(line)
                                logger.debug(f"[{self.id}] Cleaned stderr: {repr(cleaned_line)}")
                                
                                self.output_buffer.append({
                                    "timestamp": time.time(),
                                    "content": cleaned_line,
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
                  expect_pattern: str = None, clear_input_echo: bool = True,
                  force_send: bool = False) -> Dict[str, Any]:
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
            
            # Check if process is awaiting input (unless forced)
            if not force_send:
                input_state = self.is_awaiting_input()
                if not input_state.get("awaiting_input", False) and input_state.get("confidence", 0) > 0.7:
                    return {
                        "success": False,
                        "error": "ProcessNotAwaitingInput",
                        "message": f"Process may not be waiting for input: {input_state.get('reason', 'Unknown')}",
                        "process_id": self.id,
                        "input_state": input_state,
                        "suggestion": "Use force_send=True to send anyway, or check the process state"
                    }
            
            # Record current buffer size for response detection
            initial_buffer_size = len(self.output_buffer)
            
            # DEBUG: Log what we're actually receiving
            logger.error(f"DEBUG - Raw input received: {repr(input_text)}")
            
            # Clean input and convert to bytes
            input_bytes = clean_text_input(input_text)
            if send_enter and not input_bytes.endswith(b'\n'):
                input_bytes += b'\n'
            
            logger.error(f"DEBUG - Final bytes to send: {repr(input_bytes)}")
            
            # Write bytes directly
            self.process.stdin.write(input_bytes)
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
    
    def _find_child_processes(self, parent_pid: int) -> List[int]:
        """Find all child processes of a given parent process ID."""
        try:
            child_pids = []
            if sys.platform == "win32":
                # Windows implementation using wmic
                result = subprocess.run(
                    ["wmic", "process", "where", f"ParentProcessId={parent_pid}", "get", "ProcessId"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and line.isdigit():
                            child_pids.append(int(line))
            else:
                # Unix/Linux implementation using ps
                result = subprocess.run(
                    ["ps", "--ppid", str(parent_pid), "-o", "pid", "--no-headers"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        line = line.strip()
                        if line and line.isdigit():
                            child_pids.append(int(line))
            
            return child_pids
        except Exception as e:
            logger.warning(f"Error finding child processes for PID {parent_pid}: {e}")
            return []
    
    def _terminate_process_tree(self, pid: int, force: bool = False, timeout: int = 5) -> Dict[str, Any]:
        """Terminate a process and all its children recursively."""
        terminated_pids = []
        failed_pids = []
        
        try:
            # Find all child processes first
            child_pids = self._find_child_processes(pid)
            
            # Recursively terminate children first
            for child_pid in child_pids:
                child_result = self._terminate_process_tree(child_pid, force, timeout)
                terminated_pids.extend(child_result.get("terminated_pids", []))
                failed_pids.extend(child_result.get("failed_pids", []))
            
            # Now terminate the parent process
            try:
                if sys.platform == "win32":
                    # Windows implementation
                    if force:
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], 
                                     check=True, timeout=timeout)
                    else:
                        subprocess.run(["taskkill", "/PID", str(pid)], 
                                     check=True, timeout=timeout)
                else:
                    # Unix/Linux implementation
                    if hasattr(signal, 'SIGKILL'):
                        sig = signal.SIGKILL if force else signal.SIGTERM
                    else:
                        # Windows fallback
                        sig = signal.SIGTERM
                    os.kill(pid, sig)
                    
                terminated_pids.append(pid)
                logger.info(f"Successfully terminated PID {pid}")
                
            except subprocess.CalledProcessError as e:
                if "not found" in str(e).lower() or "no such process" in str(e).lower():
                    # Process already terminated
                    logger.info(f"PID {pid} was already terminated")
                    terminated_pids.append(pid)
                else:
                    logger.error(f"Failed to terminate PID {pid}: {e}")
                    failed_pids.append(pid)
            except ProcessLookupError:
                # Process already terminated (Unix)
                logger.info(f"PID {pid} was already terminated")
                terminated_pids.append(pid)
            except Exception as e:
                logger.error(f"Failed to terminate PID {pid}: {e}")
                failed_pids.append(pid)
                
        except Exception as e:
            logger.error(f"Error in process tree termination for PID {pid}: {e}")
            failed_pids.append(pid)
        
        return {
            "terminated_pids": terminated_pids,
            "failed_pids": failed_pids
        }
    
    def terminate(self, force: bool = False, timeout: int = 10) -> Dict[str, Any]:
        """Terminate the interactive process and all its children."""
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
            
            process_pid = self.process.pid
            exit_code = None
            action = "terminated"
            
            # First, try to terminate process tree using system tools
            tree_result = self._terminate_process_tree(process_pid, force, timeout//2)
            terminated_pids = tree_result.get("terminated_pids", [])
            failed_pids = tree_result.get("failed_pids", [])
            
            # If system-level termination worked, clean up our subprocess object
            if process_pid in terminated_pids:
                try:
                    # Process was terminated by system call, just poll for exit code
                    exit_code = self.process.poll()
                    if exit_code is None:
                        # Give it a moment to finish
                        time.sleep(0.5)
                        exit_code = self.process.poll()
                    action = "force killed" if force else "terminated"
                except Exception:
                    pass
            else:
                # Fallback to subprocess methods if system termination failed
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
                        exit_code = self.process.wait(timeout=timeout//2)
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
            
            # Prepare detailed result
            result = {
                "success": True,
                "process_id": self.id,
                "action": action,
                "exit_code": exit_code,
                "uptime_seconds": self.end_time - self.start_time,
                "terminated_pids": terminated_pids,
                "failed_pids": failed_pids,
                "total_terminated": len(terminated_pids),
                "message": f"Process {action} successfully"
            }
            
            if failed_pids:
                result["warning"] = f"Failed to terminate {len(failed_pids)} child processes: {failed_pids}"
                logger.warning(f"Process {self.id} terminated but some children failed: {failed_pids}")
            else:
                logger.info(f"Process {self.id} and all children {action} (exit code: {exit_code})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error terminating process {self.id}: {e}")
            return {
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "process_id": self.id
            }
    
    def is_awaiting_input(self) -> Dict[str, Any]:
        """Detect if the process is currently awaiting user input."""
        try:
            if not self.is_running or not self.process:
                return {
                    "awaiting_input": False,
                    "reason": "Process not running",
                    "confidence": 1.0
                }
            
            # Check if process is still alive
            if self.process.poll() is not None:
                return {
                    "awaiting_input": False,
                    "reason": "Process terminated",
                    "confidence": 1.0
                }
            
            with self._output_lock:
                if not self.output_buffer:
                    return {
                        "awaiting_input": False,
                        "reason": "No output to analyze",
                        "confidence": 0.5
                    }
                
                # Get recent output (last 5 lines)
                recent_entries = self.output_buffer[-5:]
                recent_content = '\n'.join([entry["content"] for entry in recent_entries 
                                          if entry["type"] in ["stdout", "stderr"]])
                
                # Check for background process indicators
                for pattern in self.background_process_patterns:
                    if re.search(pattern, recent_content, re.IGNORECASE | re.MULTILINE):
                        return {
                            "awaiting_input": False,
                            "reason": f"Background process detected (pattern: {pattern})",
                            "confidence": 0.9,
                            "last_output": recent_content[-100:]  # Last 100 chars
                        }
                
                # Check for interactive prompts
                last_line = self.output_buffer[-1]["content"] if self.output_buffer else ""
                for pattern in self.awaiting_input_patterns:
                    if re.search(pattern, last_line):
                        return {
                            "awaiting_input": True,
                            "reason": f"Interactive prompt detected (pattern: {pattern})",
                            "confidence": 0.8,
                            "prompt": last_line
                        }
                
                # Check output activity
                current_time = time.time()
                time_since_last_output = current_time - (self.output_buffer[-1]["timestamp"] if self.output_buffer else self.start_time)
                
                # If no output for a while and last line looks like a prompt
                if time_since_last_output > 2.0:  # 2 seconds of silence
                    if last_line.strip() and not last_line.endswith('.'):
                        # Looks like it might be waiting
                        return {
                            "awaiting_input": True,
                            "reason": "Quiet period suggests waiting for input",
                            "confidence": 0.6,
                            "silence_duration": time_since_last_output,
                            "last_line": last_line
                        }
                
                # Default: probably not waiting for input
                return {
                    "awaiting_input": False,
                    "reason": "No clear indicators of waiting for input",
                    "confidence": 0.7,
                    "last_output": recent_content[-100:] if recent_content else "No recent output"
                }
                
        except Exception as e:
            logger.error(f"Error checking input state for process {self.id}: {e}")
            return {
                "awaiting_input": False,
                "reason": f"Error during analysis: {str(e)}",
                "confidence": 0.0
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
                   expect_pattern: str = None, clear_input_echo: bool = True,
                   force_send: bool = False) -> Dict[str, Any]:
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
        force_send: Skip input-awaiting detection and send anyway
        
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
                                response_timeout, expect_pattern, clear_input_echo, force_send)
        
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

def check_console_input_state(process_id: str) -> Dict[str, Any]:
    """
    Check if a console process is currently awaiting user input.
    
    Args:
        process_id: ID of the process to check
        
    Returns:
        Dictionary with input state analysis
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
        result = process.is_awaiting_input()
        result["success"] = True
        result["process_id"] = process_id
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking input state for process {process_id}: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }
