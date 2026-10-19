# CS2 ESP – Kästen und Blickrichtung

Windows-x64-Prototyp mit externer Anzeige von Gegner-Kästen, Namen, Lebenspunkten und einem türkisen Pfeil für den Blickwinkel des Spielers. Die Blickrichtung verwendet Pitch und Yaw; sie ist keine Vorhersage des nächsten Schusses. Keine Sichtbarkeitsprüfung: Die Farbe unterscheidet nicht zwischen sichtbaren und verdeckten Gegnern.

## Starten

Das ausgelieferte ZIP vollständig entpacken. `CS2-ESP.exe` und `offsets.json` müssen im selben Ordner bleiben. Die EXE öffnen. Für die Demo ist kein Spiel nötig.

Für die Spielanzeige CS2 in einem Fenster oder randlosen Fenster öffnen, einer Karte beitreten und im Bedienfenster **Mit CS2 verbinden** anklicken. Anschließend zum Spiel wechseln. Die Anzeige erscheint nur, solange das CS2-Fenster im Vordergrund ist. Im exklusiven Vollbildmodus wird das Desktop-Overlay möglicherweise nicht angezeigt. **Stoppen** beendet das Lesen; beim Schließen wird die Verbindung ebenfalls geschlossen.

Alternativ `Starten.bat` mit installiertem 64-Bit-Python 3.12+ und Tkinter verwenden. Keine zusätzlichen Python-Pakete erforderlich.

## Grenzen der Version

Diese Version wurde mit simulierten Speicherdaten und im Demo-Modus geprüft. **Eine erfolgreiche Anzeige in einem laufenden CS2-Spiel wurde hier nicht getestet.** Nicht als funktionsfähige oder unentdeckte Lösung für geschützte Online-Spiele zugesichert. Cheat-Nutzung kann zu einer Kontosperre führen. Nur in einer eigenen, dafür vorgesehenen Testumgebung verwenden.

Die App liest den Prozess über die normalen Windows-Funktionen `OpenProcess`/`ReadProcessMemory`. Sie schreibt nicht in den Spielspeicher, lädt keine DLL in das Spiel und installiert keine Treiber. Sie verändert keine Anti-Cheat- oder Sicherheitseinstellungen. Wenn Windows oder das Spiel den Zugriff verweigert, wird eine Fehlermeldung angezeigt; Schutzmechanismen werden nicht umgangen. Der Hauptprozess der App enthält keinen automatischen Netzwerkzugriff.

Spielupdates ändern Speicherstrukturen. Die App enthält einen Snapshot von [a2x/cs2-dumper](https://github.com/a2x/cs2-dumper), Commit `f0c84252829602347757ecbb0810d74d3c837a4b`. Sie probiert zwei bekannte Größen der Entity-Einträge (0x70 und 0x78), prüft Team, Gesundheit und Positionen und überspringt unlesbare Einträge. Das ist keine Garantie, dass die Daten zum installierten Spiel passen. Bei leeren oder falsch positionierten Anzeigen nicht auf die Darstellung verlassen.

Zum Aktualisieren die App schließen und `Offsets-aktualisieren.bat` ausführen (Python erforderlich). Dieses Hilfsprogramm lädt ausschließlich JSON-Daten aus dem genannten Repository über HTTPS. Es lädt keinen ausführbaren Code. Für die EXE ist anschließend kein neuer Build nötig; sie liest `offsets.json` neben der EXE. Neue Offsets lösen Änderungen an der Entity-Struktur oder andere inkompatible Spieländerungen nicht automatisch.

## Entwicklung

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name CS2-ESP app.py
Copy-Item offsets.json dist\offsets.json
```

Die EXE ist nicht signiert. Quellcode und EXE sind lokal erstellt; kein unabhängiges Sicherheitsaudit. Der Demo-Modus ist zum Prüfen von Aussehen, Projektion und Richtungslinien gedacht.

Offset-Quelle: [offsets.json](https://github.com/a2x/cs2-dumper/blob/f0c84252829602347757ecbb0810d74d3c837a4b/output/offsets.json), [client_dll.json](https://github.com/a2x/cs2-dumper/blob/f0c84252829602347757ecbb0810d74d3c837a4b/output/client_dll.json). Lizenzhinweis siehe `THIRD-PARTY.txt`.
