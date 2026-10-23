"""Exact window rules; no executable configuration."""
import json
import os
from pathlib import Path
import tempfile

FLAGS = ('above', 'all_workspaces')

def atomic(path, text):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.floatland-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def selector(w):
    return {'class':w.get('class','').split('.floatland-csd-',1)[0], 'title':w.get('title','')}

class Rules:
    def __init__(self,path):
        self.path=Path(path); self.data={'version':1,'rules':[]}; self.stamp=None
        self.reload()
        if not self.path.exists(): self.save()

    def reload(self):
        if not self.path.exists(): return
        stamp=self.path.stat().st_mtime_ns
        if stamp==self.stamp: return
        data=json.loads(self.path.read_text())
        if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('rules'),list):
            raise ValueError('Invalid set-rules.json: expected version and rules')
        for rule in data['rules']:
            if not isinstance(rule,dict) or set(rule)-set(FLAGS)-{'class','title'} or any(not isinstance(rule.get(k),str) for k in ('class','title')) or any(type(rule[k]) is not bool for k in FLAGS if k in rule):
                raise ValueError('Invalid window rule: exact class/title strings and boolean flags required')
        self.data=data; self.stamp=stamp

    def save(self):
        atomic(self.path,json.dumps(self.data,indent=2,ensure_ascii=False)+'\n'); self.stamp=self.path.stat().st_mtime_ns

    def match(self,w):
        key=selector(w)
        return next((r for r in reversed(self.data['rules']) if all(r[k]==v for k,v in key.items())),None)

    def set(self,w,flag,value):
        if flag not in FLAGS or type(value) is not bool: raise ValueError('Invalid window flag')
        self.reload(); rule=self.match(w)
        if rule is None:
            rule=selector(w); self.data['rules'].append(rule)
        rule[flag]=value; self.save()

    def apply(self,c):
        self.reload()
        for w in list(c.clients):
            if not c.eligible(dict(w,pinned=False)): continue
            rule=self.match(w)
            if rule is None: continue
            record=c.record(w); signature=json.dumps(rule,sort_keys=True)
            if record.get('rule_applied')==signature: continue
            # Set desired states, never blindly toggle on each compositor event.
            if 'above' in rule and bool(record.get('above'))!=rule['above']: c.pip.toggle_above(w)
            if 'all_workspaces' in rule and bool(w.get('pinned'))!=rule['all_workspaces']:
                from .ipc import address
                c.ipc.dispatch('pinwindow',('enable' if rule['all_workspaces'] else 'disable')+','+address(w['address']))
                w['pinned']=rule['all_workspaces']
            record['rule_applied']=signature
