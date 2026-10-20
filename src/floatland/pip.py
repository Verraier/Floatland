"""Addressed picture-in-picture policy; raising never steals keyboard focus."""
from .geometry import Rect, geometry
from .ipc import address

class PictureInPicture:
    def __init__(self, controller):
        self.c = controller

    def active(self, client):
        return bool(self.c.windows.get(client['address'], {}).get('pip'))

    def toggle(self, client):
        c = self.c
        record = c.record(client)
        if self.active(client):
            self.restore(client)
            return False
        if client.get('pinned') or client.get('fullscreen'):
            raise ValueError('Leave fullscreen or unpin this window before enabling PiP')
        record['pip'] = {'geometry': geometry(client).values(), 'floating': client['floating']}
        c.state.save()
        bounds = c.bounds(client)
        ratio = max(1, client['size'][0]) / max(1, client['size'][1])
        width = min(480, bounds.w * .32)
        height = width / ratio
        if height > bounds.h * .4:
            height = bounds.h * .4
            width = height * ratio
        try:
            c.ipc.set_pip(client, True)
            if hasattr(c.ipc, "sync_restore"):
                c.ipc.sync_restore(client, None)
            c.place(client, Rect(round(bounds.x+bounds.w-width), round(bounds.y+bounds.h-height),
                                 max(1, round(width)), max(1, round(height))))
            c.ipc.dispatch('pinwindow', 'enable,' + address(client['address']))
            client['pinned'] = True
            self.raise_all()
        except Exception:
            self.restore(client)
            raise
        c.state.save()
        return True

    def restore(self, client):
        c = self.c
        record = c.windows[client['address']]
        saved = record.get('pip')
        if not saved:
            return
        c.ipc.dispatch('pinwindow', 'disable,' + address(client['address']))
        client['pinned'] = False
        c.place(client, Rect(*saved['geometry']))
        if not saved['floating']:
            c.dispatch(client, 'settiled')
            client['floating'] = False
        c.ipc.set_pip(client, False)
        del record['pip']
        record.pop('applied', None)
        record.pop('drag_origin', None)
        c.state.save()

    def raise_all(self):
        for client in self.c.clients:
            if self.active(client) and client.get('mapped', True) and not client.get('hidden'):
                self.c.ipc.raise_window(client)
