# 🧠 KONTINUUM – Neuroinspired Home Intelligence

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-0.10.0-blue)
![HA](https://img.shields.io/badge/Home%20Assistant-2024.x+-green)

**KONTINUUM** ist eine Home Assistant Custom Component, die dein Zuhause **ohne Konfiguration** versteht. Inspiriert von der Architektur des menschlichen Gehirns beobachtet es deine Gewohnheiten, lernt Muster und sagt vorher was als nächstes passiert – komplett lokal, ohne Cloud, ohne ML-Frameworks.

## 🎯 Das Konzept

Statt hunderte YAML-Automationen zu schreiben, beobachtet KONTINUUM einfach was in deinem Haus passiert:

- Du schaltest jeden Abend um 22:30 das Wohnzimmerlicht aus → KONTINUUM lernt das
- Nach dem Aufstehen geht immer die Kaffeemaschine an → KONTINUUM erkennt das Muster
- Wenn du das Büro verlässt, geht die Musik in Standby → KONTINUUM merkt sich das

**Zero UI** – keine Konfiguration, keine Regeln schreiben, keine Dashboards pflegen. Das System lernt still im Hintergrund.

## 🏗️ Architektur

Acht Module, inspiriert von Gehirnregionen:

```
Thalamus → Hippocampus → Cerebellum → PFC → Aktion
    ↑           ↑                       ↑
Hypothalamus  Spatial Cortex        Amygdala
    ↑           ↑
  Insula ←─────┘
```

| Modul | Biologisches Vorbild | Funktion |
|-------|---------------------|----------|
| **Thalamus** | Sensorisches Tor | Filtert HA-Events, erkennt Räume, erzeugt Tokens |
| **Hippocampus** | Gedächtnis | Lernt Muster mit N-Gramm Markov-Ketten, adaptive Kontext-Buckets |
| **Hypothalamus** | Homöostase | Absorbiert Energie/Klima-Rauschen, liefert Umweltkontext |
| **Spatial Cortex** | Raumwahrnehmung | Erkennt in welchem Raum du bist (Motion, Tracker, Presence) |
| **Insula** | Körpergefühl | Erkennt deinen Modus: sleeping, active, relaxing, away... |
| **Cerebellum** | Reflexe | Extrahiert stabile Routinen als deterministische Regeln |
| **Amygdala** | Risikobewertung | Bewertet Aktionen nach Sicherheit, kann Veto einlegen |
| **Präfrontaler Kortex** | Entscheidung | Wägt Vorhersagen ab, entscheidet ob gehandelt wird |

## 📦 Installation

### Manuell

1. Kopiere den Ordner `custom_components/kontinuum/` nach `/config/custom_components/kontinuum/`
2. Starte Home Assistant neu
3. Gehe zu **Einstellungen → Integrationen → + Hinzufügen → KONTINUUM**
4. Wähle eine Persönlichkeit (Mutig / Ausgeglichen / Konservativ)

### HACS (Custom Repository)

1. HACS öffnen → Integrationen → ⋮ → Custom Repositories
2. URL: `https://github.com/Chance-Konstruktion/ha-kontinuum`
3. Kategorie: Integration
4. Installieren und neustarten

## ⚙️ Persönlichkeits-Presets

Bei der Installation wählst du wie schnell KONTINUUM lernt:

| Preset | Lerngeschwindigkeit | Erste Regeln nach | Fehlertoleranz |
|--------|--------------------|--------------------|----------------|
| 🔥 **Mutig** | Schnell | ~1 Tag | Hoch (lernt aus Fehlern) |
| ⚖️ **Ausgeglichen** | Mittel | ~3 Tage | Mittel |
| 🛡️ **Konservativ** | Langsam | ~1 Woche | Niedrig |

Nachträglich änderbar: Integrationen → KONTINUUM → ⚙️ Konfigurieren

## 📊 Sensoren

KONTINUUM erstellt automatisch diese Sensoren:

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.kontinuum_status` | Systemstatus + Version |
| `sensor.kontinuum_events` | Anzahl verarbeiteter Events |
| `sensor.kontinuum_accuracy` | Vorhersagegenauigkeit (Shadow-Mode) |
| `sensor.kontinuum_mode` | Aktueller Modus (sleeping, active, ...) |
| `sensor.kontinuum_room` | Erkannter Raum |
| `sensor.kontinuum_persons_home` | Personen zuhause |
| `sensor.kontinuum_prediction` | Aktuelle Vorhersage |
| `sensor.kontinuum_energy` | Energiezustand |
| `sensor.kontinuum_cerebellum` | Gelernte Routinen |

## 🔧 Services

| Service | Beschreibung |
|---------|-------------|
| `kontinuum.enable_scenes` | Licht-Szenen nach Modus aktivieren |
| `kontinuum.disable_scenes` | Licht-Szenen deaktivieren |
| `kontinuum.set_scene` | Szene pro Modus konfigurieren |
| `kontinuum.status` | Detaillierten Status als Notification |

## 🎯 Events

| Event | Beschreibung |
|-------|-------------|
| `kontinuum_mode_changed` | Feuert bei Moduswechsel (old_mode, new_mode, confidence, room) |

Kann für eigene Automationen genutzt werden:

```yaml
trigger:
  platform: event
  event_type: kontinuum_mode_changed
  event_data:
    new_mode: sleeping
action:
  service: light.turn_off
  target:
    area_id: bedroom
```

## 🔬 Technische Details

- **Kein ML, kein Deep Learning** – reine Statistik (N-Gramm Markov-Ketten)
- **Komplett lokal** – keine Cloud, keine API-Calls
- **~3.200 Zeilen Python** – läuft auf Raspberry Pi 4
- **Adaptive Kontext-Buckets** – startet mit 6 Buckets (Zeit), wächst auf 48 (Zeit × Modus × Energie)
- **Persistenz** – Gehirn wird in `brain.json` gespeichert, überlebt Neustarts
- **Shadow-Mode** – beobachtet und validiert Vorhersagen bevor es handelt

## 📈 Roadmap

- [x] Grundarchitektur (8 Module)
- [x] Config Flow (Ein-Klick-Install)
- [x] Persönlichkeits-Presets
- [x] Licht-Szenen nach Modus
- [x] Adaptive Hippocampus-Buckets
- [ ] HACS-Integration
- [ ] Dashboard (Lovelace Card)
- [ ] N-Gramm Regeln im Cerebellum (Phase 4)
- [ ] Explainability Service (natürlichsprachliche Erklärungen)
- [ ] Shadow-Mode Exit (erstes aktives Handeln)

## 📝 Changelog

### v0.10.0
- Config Flow Fix (OptionsFlow für HA 2024.x+)
- Adaptive Hippocampus-Buckets (6→24→48 je nach Datenmenge)
- Self-Loop-Filter im Cerebellum
- Spatial Cortex Tuning (Hysterese 1.2, Confirmation 30s)
- Amygdala Confidence-Schwellen gesenkt
- 11 Dashboard-kompatible Sensoren
- 30+ deutsche Raum-Keywords im Thalamus

### v0.9.0
- Config Flow (kein configuration.yaml mehr)
- Persönlichkeits-Presets (Mutig/Ausgeglichen/Konservativ)
- DeepSeek-Fixes (48 Kontext-Buckets, Cooldown-Persistenz, SAFE_STATES)
- Alle Service-Calls async

### v0.8.0
- Personen-Zähler, HA Notifications, Licht-Szenen
- Services (enable_scenes, set_scene, status)
- kontinuum_mode_changed Event

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)
