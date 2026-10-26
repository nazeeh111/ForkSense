"""Detached trusted-local worktrees and narrow, verified patch extraction."""
from __future__ import annotations
import contextlib
import hashlib
import os
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from .process import clean_env

class GitError(RuntimeError): pass

def _capture(command, env, input_bytes=None):
    from .process import _stop, _stop_group
    # Poll file sizes during execution and terminate the whole process group,
    # including configured Git filter children. No output-sized memory growth.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(command,stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,stdout=out,stderr=err,env=env,start_new_session=(os.name!='nt'))
        def send():
            try:
                proc.stdin.write(input_bytes); proc.stdin.close()
            except (OSError,ValueError): pass
        if input_bytes is not None: threading.Thread(target=send,daemon=True).start()
        start=time.monotonic(); failure=None
        try:
            while proc.poll() is None:
                if time.monotonic()-start>15: failure='Git operation timed out after 15 seconds'; break
                if os.fstat(out.fileno()).st_size>4*1024*1024 or os.fstat(err.fileno()).st_size>65536:
                    failure='Git output exceeds the metadata/patch capture limit'; break
                time.sleep(.025)
        except BaseException:
            _stop(proc); raise
        if failure: _stop(proc)
        else: _stop_group(proc)
        if failure: raise GitError(failure)
        if os.fstat(out.fileno()).st_size>4*1024*1024 or os.fstat(err.fileno()).st_size>65536:
            raise GitError('Git output exceeds the metadata/patch capture limit')
        out.seek(0); err.seek(0)
        data=out.read(4*1024*1024); message=err.read(65536)
        if proc.returncode: raise GitError(message.decode('utf-8','replace').strip())
        return data

def git(repo, *args, input_bytes=None):
    env=clean_env()
    env.update({'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1'})
    # Git's own hooks are suppressed for ForkSense metadata operations only.
    return _capture(['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-C',str(repo),*args],env,input_bytes)

def root(path): return Path(git(path,'rev-parse','--show-toplevel').decode().strip()).resolve()
def head(repo): return git(repo,'rev-parse','HEAD').decode().strip()
def status(repo): return git(repo,'status','--porcelain=v1','--untracked-files=all')
def require_clean(repo):
    if status(repo): raise GitError('repository must be clean, including untracked files; preserve or commit your work first')

def digest(data): return hashlib.sha256(data).hexdigest()

def allowed(name, paths):
    return any(name == p.rstrip('/') or name.startswith(p.rstrip('/')+'/') for p in paths)

@contextlib.contextmanager
def worktree(repo, base, parent, preserve=None):
    parent=Path(parent); parent.mkdir(parents=True,exist_ok=True)
    holder=Path(tempfile.mkdtemp(prefix='work-',dir=parent))
    dest=holder/'repo'
    try:
        git(repo,'worktree','add','--detach',str(dest),base)
        yield dest
    finally:
        keeping=bool(preserve and preserve())
        if dest.exists() and not keeping:
            # Only disposable worktrees created by this context are removed. The
            # report/patch is retained outside; active checkout is never cleaned.
            git(repo,'worktree','remove','--force',str(dest))
        if not keeping: holder.rmdir()

def snapshot_patch(repo, base):
    # Include staged, unstaged and untracked bytes without staging in the shared
    # index. A private index cannot affect the user or another branch.
    with tempfile.TemporaryDirectory(prefix='forksense-index-') as temp:
        index=Path(temp)/'index'
        env=clean_env(); env['GIT_INDEX_FILE']=str(index)
        def ix(*args):
            return _capture(['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-C',str(repo),*args],env)
        ix('read-tree',base)
        ix('add','-A','--','.')
        names=ix('diff','--cached','--name-only','-z',base).decode().split('\0')
        names=[n for n in names if n]
        if not names: raise GitError('candidate made no source changes')
        modes=ix('diff','--cached','--raw','--no-abbrev',base).decode()
        patch=ix('diff','--cached','--binary','--no-ext-diff','--no-renames',base,'--')
        if len(patch)>2*1024*1024: raise GitError('candidate patch exceeds 2 MiB')
        return patch,names,modes

def apply_bytes(repo, patch):
    git(repo,'apply','--check','--whitespace=nowarn','-',input_bytes=patch)
    git(repo,'apply','--whitespace=nowarn','-',input_bytes=patch)


def extract_patch(repo, base, paths):
    if head(repo) != base:
        raise GitError('agent changed HEAD; candidate rejected')
    patch,names,modes=snapshot_patch(repo,base)
    if any(not allowed(n,paths) for n in names):
        raise GitError('candidate touched paths outside editable_paths: '+', '.join(n for n in names if not allowed(n,paths)))
    for line in modes.splitlines():
        fields=line.split()
        if fields[0][1:] not in ('100644','100755','000000') or fields[1] not in ('100644','100755','000000'):
            raise GitError('symlink/submodule changes are not accepted')
    return patch,names
