"""Hyprtasking integration. The provider remains managed by hyprpm."""
import logging
import shutil
import subprocess
import sys

from .ipc import IPCError, lua_string

LOG = logging.getLogger('floatland')
REPOSITORY = 'https://github.com/raybbian/hyprtasking'
# Audited upstream compatibility pin for efb50993780079460b0cbed1363e2166a2de1d9f.
AUDITED_PIN = '4d3c39511c3f38966abf1ec4393f5a7220ffb1a3'


def interactive(args):
    # Stream prompts without waiting for a newline; keep terminal stdin available.
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as child:
        try:
            while True:
                chunk = child.stdout.read1(4096)
                if not chunk:
                    break
                output = chunk.decode('utf-8', errors='replace')
                sys.stdout.write(output); sys.stdout.flush()
                for handler in logging.getLogger().handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.stream.write(output); handler.flush()
            return child.wait()
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
            raise


def ensure(command, plugins):
    if any(str(p.get('name', '')).casefold() == 'hyprtasking' for p in plugins()):
        return
    if not shutil.which('hyprpm'):
        raise IPCError('For overview install hyprpm, then run python3 run.py again. No separate project is needed.')
    listing = command(['hyprpm', 'list'], capture=True)
    steps = []
    if 'hyprtasking' not in listing:
        steps += [['hyprpm', 'update'], ['hyprpm', 'add', REPOSITORY]]
    steps += [['hyprpm', 'enable', 'hyprtasking'], ['hyprpm', 'reload', '-n']]
    for args in steps:
        # hyprpm may ask for confirmation: preserve terminal stdin/stdout.
        LOG.info('Overview setup: %s', ' '.join(args))
        if interactive(args):
            raise IPCError('Overview setup failed: ' + ' '.join(args))
    if not any(str(p.get('name', '')).casefold() == 'hyprtasking' for p in plugins()):
        raise IPCError('hyprpm completed, but hyprtasking is not loaded')


def configure(ipc):
    """Reserve a separate lower area for the minimized shelf, restoring settings on exit."""
    options = {'layout': 'linear', 'linear:top': 1, 'linear:height': 280.0, 'drag_button': 273, 'select_button': 272}
    monitors = ipc.query('monitors')
    if monitors:
        options['linear:height'] = max(80.0, min(320.0, min(m['height']/m.get('scale',1) for m in monitors)*.40))
    previous = {}
    for key in options:
        value = ipc.query('getoption plugin:hyprtasking:' + key)
        field = 'str' if key == 'layout' else 'float' if key == 'linear:height' else 'int'
        if field not in value:
            raise IPCError('Cannot preserve overview option: ' + key)
        previous[key] = value[field]
    apply(ipc, options)
    return previous


def apply(ipc, values):
    def literal(value):
        if isinstance(value, str): return lua_string(value)
        if isinstance(value, bool): return 'true' if value else 'false'
        return str(value)
    fields = 'layout=' + literal(values['layout']) + ',linear={top=' + literal(values['linear:top']) + ',height=' + literal(values['linear:height']) + '}'
    for name in ('drag_button', 'select_button'):
        if name in values:
            fields += ',' + name + '=' + literal(values[name])
    ipc.evaluate('hl.config({plugin={hyprtasking={' + fields + '}}})', 'overview layout')
