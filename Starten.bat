@echo off
cd /d "%~dp0"
py -3 app.py
if errorlevel 1 (
  echo Python 3.12 oder neuer in der 64-Bit-Version mit Tkinter erforderlich.
  pause
)
