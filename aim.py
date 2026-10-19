"""Head-height target selection and opt-in, hold-to-aim mouse control."""
import ctypes as C
from ctypes import wintypes as W
import math
import time

from geometry import project
from winreader import bind, game_rect, user

key_state = bind(user, 'GetAsyncKeyState', [C.c_int], C.c_short)


class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', C.c_size_t)]


class INPUTUNION(C.Union):
    _fields_ = [('mi', MOUSEINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', W.DWORD), ('data', INPUTUNION)]


send_input = bind(user, 'SendInput', [W.UINT, C.POINTER(INPUT), C.c_int], W.UINT)


def choose_target(players, matrix, width, height, radius, previous=None, center=None):
    """Select a projected eye position, retaining a target while it stays in range.

    Eye position approximates the center of the head; no bone/hitbox claim.
    Only enemy entries already validated by the read-only backend are accepted.
    """
    center = center or (width / 2, height / 2)
    candidates = []
    for index, player in enumerate(players):
        if player.get('health', 0) <= 0:
            continue
        point = project(player['eye'], matrix, width, height)
        if point is None or not (0 <= point[0] <= width and 0 <= point[1] <= height):
            continue
        distance = math.hypot(point[0] - center[0], point[1] - center[1])
        identity = player.get('id', index)
        if distance <= radius:
            candidates.append((distance, identity, point))
    if not candidates:
        return None
    return next((item for item in candidates if item[1] == previous), min(candidates, key=lambda item: item[0]))


def aim_step(point, center, strength, max_step=25):
    dx, dy = point[0] - center[0], point[1] - center[1]
    if math.hypot(dx, dy) <= 2:
        return 0, 0
    return tuple(round(max(-max_step, min(max_step, value * strength))) for value in (dx, dy))


class MouseAimer:
    def __init__(self):
        self.target = None
        self.last_time = None
        self.fractional = [0.0, 0.0]
        self.aligned_since = None
        self.last_shot = -math.inf
        self.spray_since = None
        self.recoil_fraction = 0.0

    def reset(self):
        self.target = None
        self.last_time = None
        self.fractional = [0.0, 0.0]
        self.aligned_since = None
        self.spray_since = None
        self.recoil_fraction = 0.0

    def active(self, pid):
        return bool(key_state(0x02) & 0x8000) and game_rect(pid) is not None

    def click(self, pid):
        if not self.active(pid) or key_state(0x01) & 0x8000:
            return False
        events = (INPUT * 2)()
        events[0].mi.dwFlags = 0x0002
        events[1].mi.dwFlags = 0x0004
        sent = send_input(2, events, C.sizeof(INPUT))
        if sent != 2:
            if sent == 1:
                release = INPUT()
                release.mi.dwFlags = 0x0004
                send_input(1, C.byref(release), C.sizeof(INPUT))
            self.reset()
            raise OSError('Auto-Schuss wurde von Windows nicht vollständig angenommen. Funktionen abgeschaltet.')
        return True

    def step(self, pid, players, matrix, width, height, radius, strength, age, auto_fire=False, recoil_rate=0, now=None):
        if not pid or not 0 <= age <= 0.1 or not key_state(0x02) & 0x8000 or game_rect(pid) is None:
            self.reset()
            return None
        now = time.monotonic() if now is None else now
        dt = min(0.05, max(0, now - self.last_time)) if self.last_time is not None else 1 / 30
        self.last_time = now
        target = choose_target(players, matrix, width, height, radius, self.target)
        dx = dy = 0
        if target:
            if self.target != target[1]:
                self.fractional = [0.0, 0.0]
                self.aligned_since = None
            self.target = target[1]
            error = (target[2][0] - width / 2, target[2][1] - height / 2)
            if math.hypot(*error) > 2:
                gain = 1 - (1 - max(0.01, min(0.8, strength))) ** (dt * 30)
                movement = []
                for axis in range(2):
                    value = error[axis] * gain + self.fractional[axis]
                    count = round(max(-25, min(25, value)))
                    self.fractional[axis] = value - count if abs(value) <= 25 else 0
                    movement.append(count)
                dx, dy = movement
            else:
                self.fractional = [0.0, 0.0]
            if auto_fire and math.hypot(*error) <= 4:
                if self.aligned_since is None:
                    self.aligned_since = now
            else:
                self.aligned_since = None
        else:
            self.target = None
            self.aligned_since = None
            self.fractional = [0.0, 0.0]
        left_held = bool(key_state(0x01) & 0x8000) if recoil_rate > 0 else False
        if left_held:
            if self.spray_since is None:
                self.spray_since = now
            if now - self.spray_since >= 0.12:
                self.recoil_fraction += max(0, min(120, recoil_rate)) * dt
                correction = int(self.recoil_fraction)
                self.recoil_fraction -= correction
                dy = min(25, dy + correction)
        else:
            self.spray_since = None
            self.recoil_fraction = 0
        if dx or dy:
            # Recheck focus and held button immediately before emitting movement.
            if game_rect(pid) is None or not key_state(0x02) & 0x8000:
                self.reset()
                return None
            event = INPUT()
            event.type = 0
            event.mi = MOUSEINPUT(dx, dy, 0, 0x0001, 0, 0)
            if send_input(1, C.byref(event), C.sizeof(INPUT)) != 1:
                self.reset()
                raise OSError('Windows hat die Mausbewegung nicht angenommen. Zielhilfe wurde ausgeschaltet.')
        if auto_fire and self.aligned_since is not None and now - self.aligned_since >= 0.08 and now - self.last_shot >= 0.25:
            if self.click(pid):
                self.last_shot = now
                self.aligned_since = None
        return target[2] if target else None
