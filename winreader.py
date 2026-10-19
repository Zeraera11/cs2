"""Read-only Win32 process access. No injection, writes, driver or privilege changes."""
import ctypes as C
from ctypes import wintypes as W
import math
import struct

kernel = C.WinDLL('kernel32', use_last_error=True)
user = C.WinDLL('user32', use_last_error=True)
SIZE = C.c_size_t
INVALID = C.c_void_p(-1).value


class PROCESSENTRY32W(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD), ('th32ProcessID', W.DWORD),
                ('th32DefaultHeapID', SIZE), ('th32ModuleID', W.DWORD), ('cntThreads', W.DWORD),
                ('th32ParentProcessID', W.DWORD), ('pcPriClassBase', W.LONG), ('dwFlags', W.DWORD), ('szExeFile', W.WCHAR * 260)]


class MODULEENTRY32W(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('th32ModuleID', W.DWORD), ('th32ProcessID', W.DWORD),
                ('GlblcntUsage', W.DWORD), ('ProccntUsage', W.DWORD), ('modBaseAddr', C.c_void_p),
                ('modBaseSize', W.DWORD), ('hModule', W.HMODULE), ('szModule', W.WCHAR * 256), ('szExePath', W.WCHAR * 260)]


def bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function


snapshot = bind(kernel, 'CreateToolhelp32Snapshot', [W.DWORD, W.DWORD], W.HANDLE)
close_handle = bind(kernel, 'CloseHandle', [W.HANDLE], W.BOOL)
process_first = bind(kernel, 'Process32FirstW', [W.HANDLE, C.POINTER(PROCESSENTRY32W)], W.BOOL)
process_next = bind(kernel, 'Process32NextW', [W.HANDLE, C.POINTER(PROCESSENTRY32W)], W.BOOL)
module_first = bind(kernel, 'Module32FirstW', [W.HANDLE, C.POINTER(MODULEENTRY32W)], W.BOOL)
module_next = bind(kernel, 'Module32NextW', [W.HANDLE, C.POINTER(MODULEENTRY32W)], W.BOOL)
open_process = bind(kernel, 'OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
read_memory = bind(kernel, 'ReadProcessMemory', [W.HANDLE, C.c_void_p, C.c_void_p, SIZE, C.POINTER(SIZE)], W.BOOL)
exit_code = bind(kernel, 'GetExitCodeProcess', [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
get_foreground = bind(user, 'GetForegroundWindow', [], W.HWND)
window_pid = bind(user, 'GetWindowThreadProcessId', [W.HWND, C.POINTER(W.DWORD)], W.DWORD)
client_rect = bind(user, 'GetClientRect', [W.HWND, C.POINTER(W.RECT)], W.BOOL)
client_screen = bind(user, 'ClientToScreen', [W.HWND, C.POINTER(W.POINT)], W.BOOL)


def process_id():
    handle = snapshot(2, 0)
    if handle == INVALID:
        raise OSError(C.get_last_error(), 'Prozessliste nicht lesbar')
    try:
        item = PROCESSENTRY32W()
        item.dwSize = C.sizeof(item)
        valid = process_first(handle, C.byref(item))
        while valid:
            if item.szExeFile.casefold() == 'cs2.exe':
                return item.th32ProcessID
            valid = process_next(handle, C.byref(item))
    finally:
        close_handle(handle)
    raise RuntimeError('cs2.exe nicht gefunden. Starte CS2 zuerst.')


def client_module(pid):
    handle = snapshot(0x8 | 0x10, pid)
    if handle == INVALID:
        raise OSError(C.get_last_error(), 'Modulliste nicht lesbar')
    try:
        item = MODULEENTRY32W()
        item.dwSize = C.sizeof(item)
        valid = module_first(handle, C.byref(item))
        while valid:
            if item.szModule.casefold() == 'client.dll':
                return item.modBaseAddr, item.modBaseSize
            valid = module_next(handle, C.byref(item))
    finally:
        close_handle(handle)
    raise RuntimeError('client.dll noch nicht geladen.')


def game_rect(pid):
    hwnd = get_foreground()
    owner = W.DWORD()
    window_pid(hwnd, C.byref(owner))
    if owner.value != pid:
        return None
    rect, origin = W.RECT(), W.POINT(0, 0)
    if not client_rect(hwnd, C.byref(rect)) or not client_screen(hwnd, C.byref(origin)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    return (origin.x, origin.y, width, height) if width > 0 and height > 0 else None


class Reader:
    def __init__(self, offsets):
        if C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('64-Bit-Python erforderlich.')
        self.handle = None
        self.offsets = offsets
        self.pid = process_id()
        self.base, size = client_module(self.pid)
        if any(value + 64 >= size for value in offsets['globals'].values()):
            raise RuntimeError('Offsets passen nicht zu client.dll.')
        self.handle = open_process(0x10 | 0x1000, False, self.pid)
        if not self.handle:
            raise OSError(C.get_last_error(), 'CS2-Speicherzugriff nicht möglich')
        self.stride = None

    def close(self):
        if self.handle:
            close_handle(self.handle)
            self.handle = None

    def read(self, address, length):
        if not self.handle or not 0x10000 <= address < 0x0000800000000000 or not 0 < length <= 4096:
            raise ValueError('Ungültige Leseadresse')
        buffer, count = C.create_string_buffer(length), SIZE()
        if not read_memory(self.handle, address, buffer, length, C.byref(count)) or count.value != length:
            raise OSError('Speicher nicht lesbar')
        return buffer.raw

    def unpack(self, address, format):
        return struct.unpack(format, self.read(address, struct.calcsize(format)))

    def ptr(self, address):
        return self.unpack(address, '<Q')[0]

    def entity(self, listing, index, stride):
        index &= 0x7fff
        chunk = self.ptr(listing + 0x10 + 8 * (index >> 9))
        return self.ptr(chunk + stride * (index & 0x1ff)) if chunk else 0

    def frame(self):
        code = W.DWORD()
        if not exit_code(self.handle, C.byref(code)) or code.value != 259:
            raise RuntimeError('CS2 wurde beendet. Erneut verbinden.')
        g, f = self.offsets['globals'], self.offsets['fields']
        matrix = self.unpack(self.base + g['dwViewMatrix'], '<16f')
        if not all(math.isfinite(v) for v in matrix) or max(abs(v) for v in matrix) < 0.001:
            raise RuntimeError('Keine gültige Kameramatrix; Karte laden oder Offsets prüfen.')
        listing = self.ptr(self.base + g['dwEntityList'])
        local = self.ptr(self.base + g['dwLocalPlayerPawn'])
        if not listing or not local:
            raise RuntimeError('Noch kein lokaler Spieler. Einer Karte beitreten.')
        local_team = self.unpack(local + f['team'], '<B')[0]
        if local_team not in (2, 3):
            raise RuntimeError('Kein aktives Team. Einer Karte beitreten.')
        players = []
        found_layout = False
        # Entity-identity stride changes across engine updates. Try known layouts;
        # retain the layout only after validating controller -> pawn -> health/team.
        candidates = [self.stride] if self.stride else [0x70, 0x78]
        for stride in candidates:
            valid_count = 0
            batch = []
            for index in range(1, 65):
                try:
                    controller = self.entity(listing, index, stride)
                    if not controller:
                        continue
                    handle = self.unpack(controller + f['pawn_handle'], '<I')[0]
                    if handle in (0, 0xffffffff):
                        continue
                    pawn = self.entity(listing, handle, stride)
                    if not pawn:
                        continue
                    health = self.unpack(pawn + f['health'], '<i')[0]
                    team = self.unpack(pawn + f['team'], '<B')[0]
                    life = self.unpack(pawn + f['life_state'], '<B')[0]
                    if not 1 <= health <= 100 or team not in (2, 3) or life != 0:
                        continue
                    valid_count += 1
                    if pawn == local or team == local_team:
                        continue
                    node = self.ptr(pawn + f['scene_node'])
                    if self.unpack(node + f['dormant'], '<B')[0]:
                        continue
                    origin = self.unpack(node + f['origin'], '<3f')
                    offset = self.unpack(pawn + f['view_offset'], '<3f')
                    angles = self.unpack(pawn + f['eye_angles'], '<3f')
                    if not all(math.isfinite(v) for v in (*origin, *offset, *angles)):
                        continue
                    if max(abs(v) for v in origin) > 100000 or not 20 <= offset[2] <= 100:
                        continue
                    if abs(angles[0]) > 180 or abs(angles[1]) > 720:
                        continue
                    name = self.read(controller + f['name'], 128).split(b'\0', 1)[0].decode('utf-8', errors='replace')
                    name = ''.join(c for c in name if c.isprintable())[:40]
                    batch.append({'name': name or 'Spieler', 'health': health, 'origin': origin,
                                  'eye': tuple(a + b for a, b in zip(origin, offset)), 'angles': angles[:2]})
                except (OSError, ValueError, OverflowError):
                    continue
            if valid_count:
                found_layout = True
                self.stride = stride
                players = batch
                break
        if not found_layout:
            self.stride = None
            raise RuntimeError('Keine gültige Spielerstruktur. Karte/Offsets prüfen.')
        return matrix, players
