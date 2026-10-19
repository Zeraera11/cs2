"""Head-height target selection and opt-in, hold-to-aim mouse control."""
import ctypes as C
from ctypes import wintypes as W
import math

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

    def reset(self):
        self.target = None

    def step(self, pid, players, matrix, width, height, radius, strength, age):
        if not pid or not 0 <= age <= 0.1 or not key_state(0x02) & 0x8000 or game_rect(pid) is None:
            self.reset()
            return None
        target = choose_target(players, matrix, width, height, radius, self.target)
        if target is None:
            self.reset()
            return None
        self.target = target[1]
        dx, dy = aim_step(target[2], (width / 2, height / 2), strength)
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
        return target[2]
