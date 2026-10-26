"""Documented external CLI adapters. Never reads credentials or internal sessions."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from .process import run, ok

class AgentError(RuntimeError): pass

def available(name): return shutil.which(name) is not None

def command(name, prompt, *, planning=False, schema_path=None, output_path=None):
    if name == 'codex':
        args=['codex','-a','never','exec','--ephemeral','--sandbox','read-only' if planning else 'workspace-write','--json','--color','never']
        if schema_path: args += ['--output-schema',str(schema_path)]
        if output_path: args += ['-o',str(output_path)]
        return args+['-']
    if name == 'claude':
        # No permission bypass flags and no --bare: bare mode requires API auth.
        args=['claude','-p','--output-format','json','--permission-mode','default','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--settings','{"disableAllHooks":true}']
        args += ['--allowedTools','Read,Glob,Grep'] if planning else ['--allowedTools','Read,Glob,Grep,Edit,Write,Bash']
        if schema_path:
            args += ['--json-schema',Path(schema_path).read_text()]
        return args
    raise AgentError('agent must be codex or claude')

def usage(stdout):
    totals={'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}; seen=False
    for line in stdout.splitlines():
        try: event=json.loads(line)
        except (ValueError,TypeError): continue
        data=event.get('usage',{})
        if isinstance(data,dict) and 'input_tokens' in data and 'output_tokens' in data: seen=True
        for k in totals:
            value=data.get(k,0)
            if isinstance(value,int) and value>=0: totals[k]+=value
    return totals if seen else {k:None for k in totals}

def invoke(name,prompt,cwd,timeout,*,planning=False,schema_path=None,output_path=None):
    if not available(name): raise AgentError(f'{name} CLI not found on PATH')
    result=run(command(name,prompt,planning=planning,schema_path=schema_path,output_path=output_path),cwd,timeout,input_text=prompt)
    result['usage']=usage(result.pop('stdout_tail','') or result['stdout'])
    if name=='claude' and ok(result):
        try:
            body=json.loads(result['stdout'])
            if body.get('is_error'): result['error']='agent_reported_error'
            if output_path and planning:
                structured=body.get('structured_output')
                if structured is None: structured=json.loads(body.get('result',''))
                Path(output_path).write_text(json.dumps(structured))
        except (ValueError,TypeError):
            result['error']='invalid_agent_output'
    return result
