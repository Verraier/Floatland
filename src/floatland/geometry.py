"""Geometry in Hyprland logical coordinates, including reserved panel space."""
from dataclasses import dataclass

ZONES = {
    "full": (0, 0, 1, 1), "left": (0, 0, .5, 1), "right": (.5, 0, 1, 1),
    "top": (0, 0, 1, .5), "bottom": (0, .5, 1, 1),
    "top-left": (0, 0, .5, .5), "top-right": (.5, 0, 1, .5),
    "bottom-left": (0, .5, .5, 1), "bottom-right": (.5, .5, 1, 1),
}


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def values(self):
        return [self.x, self.y, self.w, self.h]

    def fit(self, bounds):
        w, h = max(1, min(self.w, bounds.w)), max(1, min(self.h, bounds.h))
        return Rect(max(bounds.x, min(self.x, bounds.x + bounds.w - w)),
                    max(bounds.y, min(self.y, bounds.y + bounds.h - h)), w, h)


def workarea(monitor, gap=0):
    w, h = monitor["width"], monitor["height"]
    if monitor.get("transform", 0) % 2:
        w, h = h, w
    scale = monitor.get("scale", 1)
    left, top, right, bottom = monitor.get("reserved", [0, 0, 0, 0])
    return Rect(round(monitor["x"] + left + gap), round(monitor["y"] + top + gap),
                max(1, round(w / scale - left - right - 2 * gap)),
                max(1, round(h / scale - top - bottom - 2 * gap)))


def geometry(client):
    return Rect(*client["at"], *client["size"])


def content_rect(frame, titlebar_height):
    top = min(titlebar_height, max(0, frame.h - 1))
    return Rect(frame.x, frame.y + top, frame.w, frame.h - top)


def cascade(bounds, index, width=.65, height=.72, step=28):
    w, h = max(1, round(bounds.w * width)), max(1, round(bounds.h * height))
    offset = (index % 6) * step
    return Rect(bounds.x + (bounds.w - w) // 2 + offset,
                bounds.y + (bounds.h - h) // 2 + offset, w, h).fit(bounds)


def snap(bounds, zone, gap=0):
    x1, y1, x2, y2 = ZONES[zone]
    left = round(bounds.w * x1) + (gap // 2 if x1 else 0)
    top = round(bounds.h * y1) + (gap // 2 if y1 else 0)
    right = round(bounds.w * x2) - (gap - gap // 2 if x2 < 1 else 0)
    bottom = round(bounds.h * y2) - (gap - gap // 2 if y2 < 1 else 0)
    return Rect(bounds.x + left, bounds.y + top, max(1, right-left), max(1, bottom-top)).fit(bounds)
