"""External ESP overlay with a standalone graphics demo. Windows x64."""
import ctypes as C
from ctypes import wintypes as W
import json
import math
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from geometry import project, player_box, look_endpoint
from offsets import validate
from winreader import Reader, game_rect, bind, user

directory = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
get_ancestor = bind(user, 'GetAncestor', [W.HWND, W.UINT], W.HWND)
get_style = bind(user, 'GetWindowLongPtrW', [W.HWND, C.c_int], C.c_ssize_t)
set_style = bind(user, 'SetWindowLongPtrW', [W.HWND, C.c_int, C.c_ssize_t], C.c_ssize_t)
position_window = bind(user, 'SetWindowPos', [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT], W.BOOL)


def draw_players(canvas, players, matrix, width, height, boxes=True, names=True, directions=True, length=100):
    canvas.delete('all')
    for player in players:
        box = player_box(player['origin'], player['eye'], matrix, width, height)
        if box is None:
            continue
        left, top, right, bottom = box
        if right < 0 or left > width or bottom < 0 or top > height:
            continue
        if boxes:
            canvas.create_rectangle(left, top, right, bottom, outline='#101820', width=4)
            canvas.create_rectangle(left, top, right, bottom, outline='#ff646f', width=2)
        if names:
            label = f"{player['name']} · {player['health']} HP"
            canvas.create_text((left + right) / 2 + 1, top - 13 + 1, text=label, fill='#101820', font=('Segoe UI', 10, 'bold'))
            canvas.create_text((left + right) / 2, top - 13, text=label, fill='white', font=('Segoe UI', 10, 'bold'))
        if directions:
            eye = project(player['eye'], matrix, width, height)
            endpoint = project(look_endpoint(player['eye'], *player['angles'], length), matrix, width, height)
            if eye and endpoint and all(abs(v) < 100000 for v in (*eye, *endpoint)):
                canvas.create_line(*eye, *endpoint, fill='#0a2429', width=5)
                canvas.create_line(*eye, *endpoint, fill='#45e6d3', width=2, arrow=tk.LAST, arrowshape=(10, 12, 5))
                canvas.create_oval(eye[0] - 3, eye[1] - 3, eye[0] + 3, eye[1] + 3, fill='#45e6d3', outline='')


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('CS2 ESP • Kästen & Blickrichtung')
        self.geometry('640x470')
        self.minsize(620, 450)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background='#edf2f6')
        style.configure('TLabel', background='#edf2f6', font=('Segoe UI', 10))
        style.configure('TButton', padding=9, font=('Segoe UI', 10))
        self.configure(bg='#edf2f6')
        self.worker = None
        self.stop_event = threading.Event()
        self.messages = queue.Queue(maxsize=1)
        self.session = 0
        self.pid = None
        self.demo = None
        self.demo_canvas = None
        self.snapshot = None
        self.last_snapshot = 0
        self.boxes, self.names, self.directions = (tk.BooleanVar(value=True) for _ in range(3))
        self.length = tk.DoubleVar(value=100)
        self.status = tk.StringVar(value='Bereit. Demo benötigt kein Spiel.')
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Kästen + Blickrichtung', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Externe Anzeige für Windows · lokal · ohne Injection').pack(anchor='w', pady=(8, 20))
        for text, variable in [('Gegner-Kästen', self.boxes), ('Namen und Lebenspunkte', self.names), ('Blickrichtung als Pfeil', self.directions)]:
            ttk.Checkbutton(frame, text=text, variable=variable).pack(anchor='w', pady=4)
        ttk.Label(frame, text='Länge der Blicklinie (Spieleinheiten)').pack(anchor='w', pady=(14, 0))
        ttk.Scale(frame, from_=30, to=220, variable=self.length).pack(fill='x', pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=14)
        ttk.Button(buttons, text='Demo öffnen', command=self.start_demo).pack(side='left')
        ttk.Button(buttons, text='Mit CS2 verbinden', command=self.start).pack(side='left', padx=8)
        ttk.Button(buttons, text='Stoppen', command=self.stop).pack(side='left')
        ttk.Label(frame, textvariable=self.status, wraplength=580).pack(anchor='w', pady=8)
        ttk.Label(frame, text='CS2 im Fenstermodus oder randlosen Fenster verwenden.\nNach einem Spielupdate können neue Offsets nötig sein.', foreground='#536176').pack(anchor='w', pady=8)
        self.overlay = tk.Toplevel(self)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg='#010203')
        self.overlay.wm_attributes('-transparentcolor', '#010203')
        self.canvas = tk.Canvas(self.overlay, bg='#010203', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.overlay.update_idletasks()
        self.overlay_hwnd = get_ancestor(self.overlay.winfo_id(), 2)
        if not self.overlay_hwnd:
            raise RuntimeError('Overlay-Fenster konnte nicht erstellt werden.')
        # Color-key transparency and click-through/no-activation desktop window.
        set_style(self.overlay_hwnd, -20, get_style(self.overlay_hwnd, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(33, self.tick)

    def publish(self, message):
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            try:
                self.messages.put_nowait(message)
            except queue.Full:
                pass

    def read_loop(self, session, data, stop_event):
        reader = None
        try:
            reader = Reader(data)
            while not stop_event.is_set():
                started = time.monotonic()
                try:
                    matrix, players = reader.frame()
                    self.publish((session, reader.pid, matrix, players, None))
                except (OSError, ValueError, RuntimeError) as error:
                    self.publish((session, reader.pid, None, [], str(error)))
                    stop_event.wait(0.3)
                stop_event.wait(max(0, 1 / 30 - (time.monotonic() - started)))
        except Exception as error:
            self.publish((session, None, None, [], str(error)))
        finally:
            if reader:
                reader.close()

    def start(self):
        self.stop()
        try:
            data = json.loads((directory / 'offsets.json').read_text('utf-8'))
            validate(data)
        except Exception as error:
            messagebox.showerror('Offsets', f'offsets.json fehlt oder ist ungültig.\n{error}')
            return
        self.status.set('Verbinde mit cs2.exe …')
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self.read_loop, args=(self.session, data, self.stop_event), daemon=True)
        self.worker.start()

    def stop(self):
        self.session += 1
        self.stop_event.set()
        self.pid = self.snapshot = None
        self.overlay.withdraw()
        self.canvas.delete('all')
        if self.demo is not None:
            self.demo.destroy()
            self.demo = self.demo_canvas = None
        self.status.set('Gestoppt. Kein Prozesszugriff.')

    def start_demo(self):
        self.stop()
        self.demo = tk.Toplevel(self)
        self.demo.title('ESP-Demo • simulierte Spieler, keine Verbindung zu CS2')
        self.demo.geometry('1000x650')
        self.demo.protocol('WM_DELETE_WINDOW', self.stop)
        self.demo_canvas = tk.Canvas(self.demo, bg='#142031', highlightthickness=0)
        self.demo_canvas.pack(fill='both', expand=True)
        self.status.set('Demo aktiv. Türkise Pfeile zeigen die Blickrichtung.')

    def render(self, canvas, players, matrix, width, height):
        draw_players(canvas, players, matrix, width, height, self.boxes.get(), self.names.get(), self.directions.get(), self.length.get())

    def tick(self):
        try:
            while True:
                session, pid, matrix, players, error = self.messages.get_nowait()
                if session != self.session:
                    continue
                self.pid = pid
                self.snapshot = (matrix, players) if matrix else None
                self.last_snapshot = time.monotonic()
                self.status.set(error or f'Verbunden · {len(players)} Gegnerdaten · Anzeige nur bei aktivem CS2-Fenster.')
        except queue.Empty:
            pass
        if self.demo_canvas is not None:
            now = time.monotonic()
            matrix = (1.3, 0, 0, 0, 0, 0, 1.8, -100, 0, 0, 1, 0, 0, 1, 0, 0)
            players = []
            for index in range(3):
                x, y = (index - 1) * 125 + math.sin(now * 0.4 + index) * 15, 300 + index * 55
                players.append({'name': f'Demo-Spieler {index + 1}', 'health': 100 - index * 25, 'origin': (x, y, 0),
                                'eye': (x, y, 64), 'angles': (math.sin(now * 0.5 + index) * 20, now * 25 + index * 120)})
            self.render(self.demo_canvas, players, matrix, max(1, self.demo_canvas.winfo_width()), max(1, self.demo_canvas.winfo_height()))
        rect = game_rect(self.pid) if self.pid else None
        if rect and self.snapshot and time.monotonic() - self.last_snapshot < 0.5:
            x, y, width, height = rect
            self.overlay.geometry(f'{width}x{height}{x:+d}{y:+d}')
            if self.overlay.state() == 'withdrawn':
                self.overlay.deiconify()
            # Show without activating, even on the first frame.
            position_window(self.overlay_hwnd, W.HWND(-1), x, y, width, height, 0x10 | 0x40)
            self.render(self.canvas, self.snapshot[1], self.snapshot[0], width, height)
        else:
            self.overlay.withdraw()
            self.canvas.delete('all')
        self.after(33, self.tick)

    def close(self):
        self.stop()
        if self.worker:
            self.worker.join(timeout=1)
        self.destroy()


def main():
    try:
        dpi = bind(user, 'SetProcessDpiAwarenessContext', [C.c_void_p], W.BOOL)
        dpi(C.c_void_p(-4))
    except AttributeError:
        user.SetProcessDPIAware()
    App().mainloop()


if __name__ == '__main__':
    main()
