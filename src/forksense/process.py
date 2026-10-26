"""Bounded argv-only process execution with capped logs and process-group cleanup."""
from __future__ import annotations
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

MAX_LOG = 65536

# Never pass ambient provider keys or GitHub tokens to tests or agents. The CLI's
# native subscription login remains its own responsibility; no credential files read.
def clean_env():
    keep = {'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','TERM','TMPDIR','SYSTEMROOT','WINDIR'}
    env = {k:v for k,v in os.environ.items() if k in keep}
    env.update({'PYTHONDONTWRITEBYTECODE':'1','GIT_TERMINAL_PROMPT':'0','NO_COLOR':'1'})
    return env

def run(command, cwd, timeout, input_text=None, max_log=MAX_LOG):
    start=time.monotonic()
    if timeout <= 0:
        return {'command':command,'returncode':None,'duration':0.,'stdout':'','stderr':'budget exhausted','timed_out':True}
    # Files avoid deadlocks and memory growth from verbose agents. Log bytes are
    # bounded on read; disk output is monitored and the child is stopped at 8 MiB.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc=subprocess.Popen(command,cwd=cwd,env=clean_env(),stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=(os.name!='nt'))
        except OSError as exc:
            return {'command':command,'returncode':None,'duration':time.monotonic()-start,'stdout':'','stderr':str(exc),'timed_out':False,'error':'spawn_failed'}
        # Input prompts are intentionally small; communicate drives the pipe without
        # waiting on stdout. A sender thread avoids hanging on a child ignoring stdin.
        import threading
        def send():
            try:
                proc.stdin.write(input_text.encode())
                proc.stdin.close()
            except (OSError, ValueError):
                pass
        if input_text is not None:
            threading.Thread(target=send,daemon=True).start()
        reason=None
        try:
            while proc.poll() is None:
                if time.monotonic()-start >= timeout:
                    reason='timeout'; break
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > 8*1024*1024:
                    reason='output_limit'; break
                time.sleep(.025)
        except BaseException:
            _stop(proc)
            raise
        if reason:
            _stop(proc)
        else:
            # Reap descendants still holding pipes, even when the parent exited.
            _stop_group(proc)
        out.seek(0); err.seek(0)
        stdout=out.read(max_log).decode('utf-8','replace')
        stderr=err.read(max_log).decode('utf-8','replace')
        tail=''
        if os.fstat(out.fileno()).st_size>max_log:
            out.seek(max(0,os.fstat(out.fileno()).st_size-max_log)); tail=out.read(max_log).decode('utf-8','replace')
        return {'stdout_tail':tail,'command':command,'returncode':proc.returncode,'duration':time.monotonic()-start,'stdout':stdout,'stderr':stderr,'timed_out':reason=='timeout','error':reason,'truncated':os.fstat(out.fileno()).st_size>max_log or os.fstat(err.fileno()).st_size>max_log}

def _stop_group(proc):
    if os.name!='nt':
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        except PermissionError:
            if proc.poll() is None:
                raise OSError('Host denied process-group termination; execution could not be stopped')
            import warnings
            warnings.warn('Host denied process-group cleanup after parent exit; descendants could not be confirmed stopped', RuntimeWarning)

def _stop(proc):
    _stop_group(proc)
    if os.name=='nt': proc.kill()
    proc.wait()

def ok(result):
    return result.get('returncode') == 0 and not result.get('error') and not result.get('timed_out')
