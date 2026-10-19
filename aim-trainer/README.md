# Aim Lab – eigenständiger Aim-Trainer

Eine lokale 2D-Trainingsarena für Windows mit beweglichen Zielen, eigener Kopf-Trefferzone, flüssiger Zielverfolgung, automatischer Schussabgabe bei Zielerfassung und einer Rückstoßsimulation mit zuschaltbarer Korrektur.

## Windows-Version

`Aim-Trainer-Windows.zip` vollständig entpacken. Im entpackten Ordner `Aim-Trainer.exe` starten. Den Unterordner `_internal` neben der EXE lassen: Er enthält die mitgelieferte Python-/Tk-Laufzeit, sodass Python nicht installiert sein muss. Diese Ordner-Version muss beim Start nicht erst die komplette Laufzeit in einen temporären Ordner entpacken.

## Bedienung

- Maus im Arenafenster bewegen: das virtuelle Fadenkreuz bewegen.
- Rechte Maustaste **innerhalb der Arena halten**: Trackinghilfe. Sie behält ihr Ziel und folgt mit einer gedämpften Bewegung einschließlich Zielgeschwindigkeit. Maus zum Ziel bewegen, falls es außerhalb des Suchradius liegt.
- **Auto-Schuss bei Kopfziel**: Während des Trackings wird nach mindestens 60 ms innerhalb der inneren Kopfzone geschossen. Schussabstand: mindestens 150 ms. Die Wertung verwendet die Position des virtuellen Fadenkreuzes zum Schusszeitpunkt.
- Linke Maustaste halten: manuell fortlaufend schießen.
- **Rückstoßkorrektur (Simulation)**: reduziert den simulierten Ausschlag des Fadenkreuzes und beschleunigt dessen Rückkehr. Ausschalten, um die Rückstoßwirkung zu vergleichen.
- **Nachlauf** regelt die Tracking-Glättung; **Zieltempo** die Bewegungsgeschwindigkeit.
- **Esc** pausiert oder setzt fort. Beim Verlassen der Arena werden gehaltene Aktionen aufgehoben. Ein Wechsel in ein anderes Fenster pausiert die Runde; Fortsetzen muss ausdrücklich gewählt werden.
- Eine Runde dauert 60 Sekunden Simulationszeit. Schüsse, Treffer, Kopftreffer und Genauigkeit werden angezeigt. **Neue 60-Sekunden-Runde** setzt die Statistik zurück.

Alle Schüsse, Zielbewegungen und Rückstoßkorrekturen passieren ausschließlich in der eigenen Canvas-Simulation. Die App öffnet keinen Spielprozess, liest oder schreibt keinen fremden Speicher und sendet keine systemweiten Tastatur-/Mauseingaben. Sie enthält keine CS2-Offsets, DLL-Injection, Treiber, Anti-Cheat-Funktionen oder Netzwerkzugriffe. Es gibt keine Zusicherung zu VAC; diese App ist ein eigenständiges Trainingsprogramm und keine Erweiterung von CS2.

## Quellcode und Build

Python 3.12+ mit Tkinter. Für den Quellcode sind keine zusätzlichen Pakete nötig.

```powershell
py -3 app.py
py -3 -m unittest discover -s tests -v
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name Aim-Trainer app.py
```

Der komplette Ordner `dist/Aim-Trainer` ist die Windows-Ausgabe. Die EXE ist nicht digital signiert. Die Tests prüfen unter anderem Trefferwertung, Schussabstände, Pausen, Tracking-Konvergenz, Bildraten-Unabhängigkeit und simulierte Rückstoßkorrektur.
