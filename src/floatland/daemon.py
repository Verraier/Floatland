import asyncio
import fcntl
import json
import logging
import os
import signal

from .controller import Controller
from .ipc import Hyprland, IPCError
from .state import State
from .size_memory import SizeMemory
from .config_runtime import ConfigRuntime

LOG = logging.getLogger("floatland")
EVENTS = {"openwindow", "closewindow", "movewindowv2", "workspacev2",
          "monitoraddedv2", "monitorremoved", "configreloaded", "fullscreen"}


async def run(directory, config, config_path=None, unified=False):
    lock = (directory / "floatland.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise IPCError("Floatland is already running for this Hyprland instance")
    ipc = Hyprland(directory)
    try:
        ipc.check_api()
    except Exception:
        lock.close()
        raise
    path = directory / "floatland.sock"
    stop = asyncio.Event()
    controller = Controller(ipc, State(directory / "floatland-state.json"), config, SizeMemory())
    configuration = ConfigRuntime(controller, config_path, native=unified)
    LOG.info("Active configuration: %s | automatic reload=%s", configuration.path, unified)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    async def control(reader, writer):
        try:
            raw = await asyncio.wait_for(reader.readline(), 3)
            request = json.loads(raw)
            if not isinstance(request, dict) or not isinstance(request.get("action"), str):
                raise ValueError("Expected a JSON object with an action")
            if request["action"] == "reload":
                result = await configuration.reload()
            elif request["action"] == "stop":
                if request.get("value") == "restore":
                    controller.release()
                result = {"stopping": True}
                stop.set()
            else:
                result = controller.command(request["action"], request.get("value"))
            if request["action"] == "status":
                result['config_path'] = str(configuration.path)
                result['native_settings'] = unified
                result['config_revision'] = configuration.applied
            response = {"ok": True, "result": result}
        except Exception as error:
            LOG.warning("Command failed: %s", error)
            response = {"ok": False, "error": str(error)}
        try:
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def events():
        announced = False
        while not stop.is_set():
            writer = None
            try:
                reader, writer = await asyncio.open_unix_connection(str(directory / ".socket2.sock"))
                # Subscribe first, then enumerate so windows opened during startup are not lost.
                controller.reconcile()
                ipc.resync_bars()
                LOG.info("Startup sync: %d live windows, %d managed records", len(controller.clients), len(controller.windows))
                if not announced:
                    LOG.info("Ready: daemon connected. Ctrl+C stops the session.")
                    announced = True
                while not stop.is_set():
                    line = await reader.readline()
                    if not line:
                        raise IPCError("Hyprland event socket disconnected")
                    event, _, payload = line.decode(errors="replace").rstrip("\n").partition(">>")
                    if event == 'floatland_log':
                        level, _, message = payload.partition(',')
                        LOG.log(logging.ERROR if level == 'error' else logging.WARNING,
                                'Native: %s', message[:2048])
                        continue
                    if event == 'activewindowv2':
                        controller.refresh()
                        controller.tasks.focused('0x' + payload.removeprefix('0x'))
                    if event == 'floatland_tasks':
                        try:
                            parts = payload.split(',')
                            if parts[0] == 'prepare-tab' and len(parts) == 2:
                                ipc.prepare_switcher(int(parts[1]))
                            elif parts[0] == 'step' and len(parts) == 4:
                                controller.tasks.next_from(parts[1], int(parts[2]), parts[3] == '1')
                            elif parts[0] == 'prepare' and len(parts) == 2:
                                ipc.prepare_overview(int(parts[1]))
                            elif parts[0] == 'choose' and len(parts) == 4:
                                controller.tasks.choose(parts[1], int(parts[2]), int(parts[3]))
                            elif parts[0] == 'select' and len(parts) == 3:
                                controller.tasks.click(parts[1], int(parts[2]))
                            elif len(parts) == 1 and parts[0] in ('next', 'previous', 'commit', 'cancel', 'overview'):
                                action = {'next': 'alt-tab', 'previous': 'alt-tab', 'commit': 'alt-tab-commit', 'cancel': 'alt-tab-cancel', 'overview': 'overview'}[parts[0]]
                                controller.command(action, 'reverse' if parts[0] == 'previous' else None)
                            else:
                                raise ValueError('Invalid task event')
                        except (ValueError, IPCError) as error:
                            LOG.warning('Task action rejected: %s', error)
                        continue
                    if event == "floatland_bars":
                        try:
                            controller.bars_event(payload)
                        except (ValueError, IPCError) as error:
                            LOG.warning("Bars action rejected: %s", error)
                        continue
                    if event in EVENTS:
                        controller.reconcile()
            except (OSError, IPCError, ValueError, KeyError) as error:
                LOG.warning("Event connection: %s; retrying in 1s", error)
                await asyncio.sleep(1)
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def overview_watch():
        last_error = None
        while not stop.is_set():
            try:
                ipc.poll_overview()
                if last_error is not None:
                    LOG.info('Native overview connection recovered')
                    last_error = None
            except (IPCError, OSError) as error:
                message = str(error)
                if message != last_error:
                    LOG.warning('Native overview state: %s', message)
                    last_error = message
            await asyncio.sleep(.25)

    async def size_watch():
        while not stop.is_set():
            await asyncio.sleep(1)
            if controller.config.get("remember_sizes", True):
                try:
                    controller.refresh()
                except (OSError, IPCError, ValueError) as error:
                    LOG.warning("Size sampling failed: %s", error)

    def task_finished(task):
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            LOG.error('Background task failed: %s', error,
                      exc_info=(type(error), error, error.__traceback__))
            stop.set()

    task = None
    watcher = None
    config_watcher = None
    size_watcher = None
    try:
        path.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(control, str(path), limit=8192)
        os.chmod(path, 0o600)
        task = asyncio.create_task(events())
        size_watcher = asyncio.create_task(size_watch())
        size_watcher.add_done_callback(task_finished)
        watcher = asyncio.create_task(overview_watch())
        if unified:
            config_watcher = asyncio.create_task(configuration.watch(stop))
            config_watcher.add_done_callback(task_finished)
        task.add_done_callback(task_finished)
        watcher.add_done_callback(task_finished)
        async with server:
            LOG.info("Listening at %s", path)
            LOG.info("Running in foreground. Keep this terminal open; use a second terminal for commands.")
            await stop.wait()
    finally:
        controller.remember_sizes(controller.clients)
        controller.size_memory.flush()
        if size_watcher:
            size_watcher.cancel()
            await asyncio.gather(size_watcher, return_exceptions=True)
        if config_watcher:
            config_watcher.cancel()
            await asyncio.gather(config_watcher, return_exceptions=True)
        if watcher:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        path.unlink(missing_ok=True)
        lock.close()
        LOG.info("Daemon stopped; control socket removed.")
