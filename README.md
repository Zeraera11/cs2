# Aim Lab – eigenständiger Aim-Trainer

Die aktuelle Trainingsversion befindet sich unter [aim-trainer](aim-trainer/). Sie enthält geglättetes Tracking, Auto-Schuss bei erfasstem Kopfziel und eine zuschaltbare Rückstoßsimulation mit Korrektur. Alle Funktionen laufen ausschließlich in der eigenen Trainingsarena.

## Windows-Download

[Aim-Trainer-Windows.zip herunterladen](Aim-Trainer-Windows.zip). Das ZIP vollständig entpacken und `Aim-Trainer.exe` starten. Den mitgelieferten Unterordner `_internal` neben der EXE lassen.

## Bedienung

- Maus bewegen: virtuelles Fadenkreuz bewegen.
- Rechts halten: Trackinghilfe aktivieren.
- Auto-Schuss: schießt nach kurzer Erfassung der Kopfzone während des Trackings.
- Links halten: manuell schießen.
- Rückstoßkorrektur: simulierten Rückstoß reduzieren.
- Esc: Pause; neue Runde über die Schaltfläche oben.

[Ausführliche Anleitung und Build-Befehle](aim-trainer/README.md).

Diese eigenständige App greift nicht auf CS2 zu und sendet keine systemweiten Mauseingaben. Die älteren CS2-Dateien im Repository gehören zu früheren Prototypen; die neue Trainingsversion wird über das oben verlinkte ZIP gestartet.

Validierung: 12 Simulationstests, Oberflächentest sowie Startprüfung der gebauten Windows-App bestanden. Die EXE ist nicht digital signiert.
