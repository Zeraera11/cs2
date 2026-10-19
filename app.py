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
from aim import MouseAimer, key_state, choose_target, aim_step

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
        self.title('CS2 ESP • Blickrichtung & Zielhilfe')
        self.geometry('720x790')
        self.minsize(700, 760)
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
        self.last_aim_frame = None
        self.aimer = MouseAimer()
        self.aim_enabled = tk.BooleanVar(value=False)
        self.auto_fire = tk.BooleanVar(value=False)
        self.recoil_enabled = tk.BooleanVar(value=False)
        self.recoil_rate = tk.DoubleVar(value=30)
        self.aim_radius = tk.DoubleVar(value=150)
        self.aim_strength = tk.DoubleVar(value=0.16)
        self.demo_crosshair = None
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
        ttk.Separator(frame).pack(fill='x', pady=10)
        ttk.Checkbutton(frame, text='Zielhilfe aktivieren · rechte Maustaste halten · F8 schaltet aus', variable=self.aim_enabled).pack(anchor='w')
        ttk.Label(frame, text='Kopfposition angenähert über Augenhöhe · F8 schaltet alle Eingaben aus', foreground='#536176').pack(anchor='w', pady=4)
        ttk.Checkbutton(frame, text='Auto-Schuss bei erfasstem Kopfziel (rechte Maustaste halten)', variable=self.auto_fire).pack(anchor='w', pady=3)
        ttk.Checkbutton(frame, text='Spray-Korrektur: bei rechts + links halten nach unten bewegen', variable=self.recoil_enabled).pack(anchor='w', pady=3)
        recoil_controls = ttk.Frame(frame)
        recoil_controls.pack(fill='x')
        ttk.Label(recoil_controls, text='Spray-Korrektur / Sekunde').pack(side='left')
        ttk.Scale(recoil_controls, from_=0, to=120, variable=self.recoil_rate, length=250).pack(side='left', padx=10)
        tuning = ttk.Frame(frame)
        tuning.pack(fill='x', pady=4)
        ttk.Label(tuning, text='Suchradius (Pixel)').grid(row=0, column=0, sticky='w')
        ttk.Scale(tuning, from_=30, to=350, variable=self.aim_radius).grid(row=0, column=1, sticky='ew', padx=10)
        ttk.Label(tuning, text='Stärke').grid(row=1, column=0, sticky='w', pady=8)
        ttk.Scale(tuning, from_=0.05, to=0.5, variable=self.aim_strength).grid(row=1, column=1, sticky='ew', padx=10)
        tuning.columnconfigure(1, weight=1)
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
                    self.publish((session, reader.pid, matrix, players, None, started))
                except (OSError, ValueError, RuntimeError) as error:
                    self.publish((session, reader.pid, None, [], str(error), started))
                    stop_event.wait(0.3)
                stop_event.wait(max(0, 1 / 30 - (time.monotonic() - started)))
        except Exception as error:
            self.publish((session, None, None, [], str(error), time.monotonic()))
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
        self.aim_enabled.set(False)
        self.auto_fire.set(False)
        self.recoil_enabled.set(False)
        self.aimer.reset()
        self.last_aim_frame = None
        self.demo_crosshair = None
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

    def aim_marker(self, canvas, width, height, center=None, target=None):
        if not self.aim_enabled.get():
            return
        x, y = center or (width / 2, height / 2)
        radius = self.aim_radius.get()
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline='#8aa1b7', dash=(3, 5))
        if center:
            canvas.create_line(x - 8, y, x + 8, y, fill='white', width=2)
            canvas.create_line(x, y - 8, x, y + 8, fill='white', width=2)
        if target:
            tx, ty = target
            canvas.create_oval(tx - 7, ty - 7, tx + 7, ty + 7, outline='#ffda66', width=2)

    def tick(self):
        if key_state(0x77) & 0x8000:  # F8: disable immediately, never toggle back on.
            self.aim_enabled.set(False)
            self.auto_fire.set(False)
            self.recoil_enabled.set(False)
            self.aimer.reset()
        try:
            while True:
                session, pid, matrix, players, error, captured = self.messages.get_nowait()
                if session != self.session:
                    continue
                self.pid = pid
                self.snapshot = (matrix, players) if matrix else None
                self.last_snapshot = captured
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
            width, height = max(1, self.demo_canvas.winfo_width()), max(1, self.demo_canvas.winfo_height())
            self.render(self.demo_canvas, players, matrix, width, height)
            if self.demo_crosshair is None:
                self.demo_crosshair = (width / 2, height / 2)
            target = choose_target(players, matrix, width, height, self.aim_radius.get(), center=self.demo_crosshair)
            if self.aim_enabled.get() and target:
                dx, dy = aim_step(target[2], self.demo_crosshair, self.aim_strength.get())
                self.demo_crosshair = (self.demo_crosshair[0] + dx, self.demo_crosshair[1] + dy)
            self.aim_marker(self.demo_canvas, width, height, self.demo_crosshair, target[2] if target else None)
        rect = game_rect(self.pid) if self.pid else None
        if rect and self.snapshot and time.monotonic() - self.last_snapshot < 0.5:
            x, y, width, height = rect
            self.overlay.geometry(f'{width}x{height}{x:+d}{y:+d}')
            if self.overlay.state() == 'withdrawn':
                self.overlay.deiconify()
            # Show without activating, even on the first frame.
            position_window(self.overlay_hwnd, W.HWND(-1), x, y, width, height, 0x10 | 0x40)
            self.render(self.canvas, self.snapshot[1], self.snapshot[0], width, height)
            target_point = None
            if self.aim_enabled.get() and self.last_aim_frame != self.last_snapshot:
                self.last_aim_frame = self.last_snapshot
                try:
                    target_point = self.aimer.step(self.pid, self.snapshot[1], self.snapshot[0], width, height,
                                                   self.aim_radius.get(), self.aim_strength.get(), time.monotonic() - self.last_snapshot,
                                                   auto_fire=self.auto_fire.get(), recoil_rate=self.recoil_rate.get() if self.recoil_enabled.get() else 0)
                except OSError as error:
                    self.aim_enabled.set(False)
                    self.auto_fire.set(False)
                    self.recoil_enabled.set(False)
                    self.status.set(str(error))
            elif not self.aim_enabled.get():
                self.aimer.reset()
            self.aim_marker(self.canvas, width, height, target=target_point)
        else:
            self.aimer.reset()
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
