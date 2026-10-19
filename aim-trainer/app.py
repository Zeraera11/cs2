"""Standalone arena: every reticle movement and shot stays in this Tk canvas."""
import math
import sys
import time
import tkinter as tk
from tkinter import ttk

from engine import Trainer


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Aim Lab • Eigenständiger Trainer')
        self.geometry('1240x820')
        self.minsize(940, 680)
        self.configure(bg='#101824')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#101824')
        style.configure('TLabel', background='#101824', foreground='#e2eaf3')
        style.configure('TCheckbutton', background='#101824', foreground='#e2eaf3')
        style.map('TCheckbutton', background=[('active', '#1d2b3c')])
        style.configure('TButton', padding=8)
        self.engine = Trainer()
        self.tracking = self.firing = False
        self.tracking_option = tk.BooleanVar(value=True)
        self.auto_option = tk.BooleanVar(value=True)
        self.recoil_option = tk.BooleanVar(value=True)
        self.smooth_option = tk.DoubleVar(value=0.12)
        self.speed_option = tk.DoubleVar(value=1.0)
        self.status = tk.StringVar()
        self.last_tick = time.monotonic()
        header = ttk.Frame(self, padding=(24, 18))
        header.pack(fill='x')
        ttk.Label(header, text='AIM LAB', font=('Segoe UI', 24, 'bold'), foreground='#50e0c1').pack(side='left')
        ttk.Label(header, text='TRACKING  /  AUTO-SCHUSS  /  RÜCKSTOSS', foreground='#9badc2').pack(side='left', padx=20)
        ttk.Button(header, text='Neue 60-Sekunden-Runde', command=self.reset).pack(side='right')
        settings = ttk.Frame(self, padding=(24, 0, 24, 12))
        settings.pack(fill='x')
        for text, variable in [('Trackinghilfe', self.tracking_option), ('Auto-Schuss bei Kopfziel', self.auto_option),
                               ('Rückstoßkorrektur (Simulation)', self.recoil_option)]:
            ttk.Checkbutton(settings, text=text, variable=variable).pack(side='left', padx=(0, 22))
        tuning = ttk.Frame(self, padding=(24, 0, 24, 12))
        tuning.pack(fill='x')
        ttk.Label(tuning, text='Nachlauf: schnell').pack(side='left')
        ttk.Scale(tuning, from_=0.05, to=0.35, variable=self.smooth_option, length=170).pack(side='left', padx=8)
        ttk.Label(tuning, text='weich').pack(side='left')
        ttk.Label(tuning, text='Zieltempo').pack(side='left', padx=(30, 8))
        ttk.Scale(tuning, from_=0.4, to=2.2, variable=self.speed_option, length=180).pack(side='left')
        self.pause_button = ttk.Button(tuning, text='Pause · Esc', command=self.toggle_pause)
        self.pause_button.pack(side='right')
        self.canvas = tk.Canvas(self, bg='#152235', highlightthickness=1, highlightbackground='#293b51', cursor='crosshair')
        self.canvas.pack(fill='both', expand=True, padx=24)
        self.canvas.bind('<Motion>', self.move)
        self.canvas.bind('<ButtonPress-1>', self.press_fire)
        self.canvas.bind('<ButtonPress-3>', self.press_track)
        self.bind('<ButtonRelease-1>', lambda e: self.release_button('fire'))
        self.bind('<ButtonRelease-3>', lambda e: self.release_button('track'))
        self.canvas.bind('<Leave>', self.leave_arena)
        self.canvas.bind('<Configure>', self.resize)
        self.bind('<Escape>', lambda e: self.toggle_pause())
        self.bind('<FocusOut>', lambda e: self.after_idle(self.check_focus))
        footer = ttk.Frame(self, padding=(24, 12, 24, 18))
        footer.pack(fill='x')
        ttk.Label(footer, textvariable=self.status, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(footer, text='Maus: zielen  ·  Rechts halten: verfolgen  ·  Links halten: schießen  ·  Esc: Pause', foreground='#9badc2').pack(anchor='w', pady=(8, 0))
        ttk.Label(footer, text='Eigenständige Simulation · kein CS2-Zugriff · keine systemweiten Mauseingaben', foreground='#6d839e').pack(anchor='w', pady=(4, 0))
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.after(16, self.tick)

    def reset(self):
        self.release_all()
        self.engine = Trainer(max(300, self.canvas.winfo_width()), max(250, self.canvas.winfo_height()))
        self.pause_button.configure(text='Pause · Esc')
        self.last_tick = time.monotonic()

    def release_all(self):
        self.tracking = self.firing = False
        self.engine.release()

    def release_button(self, button):
        if button == 'fire':
            self.firing = False
        else:
            self.tracking = False
            self.engine.release()

    def leave_arena(self, event=None):
        self.release_all()

    def move(self, event):
        if not self.tracking and not self.engine.paused and not self.engine.finished:
            self.engine.base = [event.x, event.y]
            self.engine.velocity = [0, 0]

    def press_fire(self, event):
        self.canvas.focus_set()
        self.move(event)
        self.firing = True

    def press_track(self, event):
        self.canvas.focus_set()
        self.move(event)
        self.tracking = True

    def resize(self, event):
        self.engine.resize(event.width, event.height)

    def toggle_pause(self):
        self.engine.paused = not self.engine.paused
        self.release_all()
        self.pause_button.configure(text='Fortsetzen · Esc' if self.engine.paused else 'Pause · Esc')

    def check_focus(self):
        if self.focus_displayof() is None:
            self.release_all()
            self.engine.paused = True
            self.pause_button.configure(text='Fortsetzen · Esc')

    def draw(self):
        canvas, engine = self.canvas, self.engine
        canvas.delete('all')
        width, height = engine.width, engine.height
        for x in range(0, int(width), 50):
            canvas.create_line(x, 0, x, height, fill='#1d2d43')
        for y in range(0, int(height), 50):
            canvas.create_line(0, y, width, y, fill='#1d2d43')
        canvas.create_text(20, 20, text='TRAININGSARENA', fill='#7089a6', anchor='nw', font=('Segoe UI', 10, 'bold'))
        x, y = engine.crosshair
        if self.tracking and engine.tracking_enabled:
            radius = engine.search_radius
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline='#34566c', dash=(3, 8))
        for target in engine.targets:
            tx, ty = target.x, target.y
            locked = engine.locked == (target.identity, target.generation)
            color = '#50e0c1' if locked else '#ff7585'
            canvas.create_rectangle(tx - 17, ty - 15, tx + 17, ty + 32, fill='#2c3a51', outline=color, width=2)
            hx, hy = target.head
            canvas.create_oval(hx - target.radius, hy - target.radius, hx + target.radius, hy + target.radius, fill='#3b2e41', outline=color, width=2)
            canvas.create_text(tx, ty + 47, text=f'T{target.identity + 1:02}', fill='#b6c6d9', font=('Segoe UI', 9))
            speed = math.hypot(target.vx, target.vy)
            canvas.create_line(hx, hy, hx + target.vx / speed * 35, hy + target.vy / speed * 35, fill='#6686a6', arrow=tk.LAST)
        for sx, sy, remaining, hit in engine.tracers:
            radius = 5 + (0.16 - remaining) * 80
            canvas.create_oval(sx - radius, sy - radius, sx + radius, sy + radius, outline='#50e0c1' if hit else '#ffb454', width=2)
        canvas.create_line(x - 12, y, x - 4, y, fill='white', width=2)
        canvas.create_line(x + 4, y, x + 12, y, fill='white', width=2)
        canvas.create_line(x, y - 12, x, y - 4, fill='white', width=2)
        canvas.create_line(x, y + 4, x, y + 12, fill='white', width=2)
        canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill='#50e0c1', outline='')
        if engine.paused or engine.finished:
            canvas.create_rectangle(width / 2 - 230, height / 2 - 70, width / 2 + 230, height / 2 + 70, fill='#101824', outline='#50e0c1')
            canvas.create_text(width / 2, height / 2 - 18, text='RUNDE BEENDET' if engine.finished else 'PAUSE', fill='white', font=('Segoe UI', 24, 'bold'))
            canvas.create_text(width / 2, height / 2 + 24, text='Oben eine neue Runde starten' if engine.finished else 'Esc oder Fortsetzen zum Weitermachen', fill='#9badc2', font=('Segoe UI', 11))

    def tick(self):
        now = time.monotonic()
        seconds = now - self.last_tick
        self.last_tick = now
        engine = self.engine
        engine.tracking_enabled = self.tracking_option.get()
        engine.auto_fire = self.auto_option.get()
        engine.compensate = self.recoil_option.get()
        engine.smooth_time = self.smooth_option.get()
        engine.speed = self.speed_option.get()
        engine.step(seconds, tracking=self.tracking, firing=self.firing)
        self.draw()
        self.status.set(f'{max(0, math.ceil(engine.duration - engine.elapsed)):02}s übrig   |   Schüsse {engine.shots}   |   Treffer {engine.hits}   |   Kopf {engine.headshots}   |   Genauigkeit {engine.accuracy:.0f}%')
        self.after(16, self.tick)


if __name__ == '__main__':
    App().mainloop()
