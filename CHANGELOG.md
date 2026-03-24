# Changelog

## v0.16.0 – 4-Gramme, Brain Review & Bugfixes

### Hippocampus – Tiefere Muster
- **4-Gramm-Sequenzen** – NGRAM_SIZES erweitert auf [1,2,3,4] für 4-Schritt-Muster
- **Größerer Kontext-Buffer** – 20 → 30 Tokens für bessere Kontexterfassung
- **Mehr Muster pro Bucket** – MAX_NGRAMS_PER_BUCKET 500 → 1000 (weniger Eviction)
- **Schnelleres Lernen** – MIN_OBSERVATIONS 3 → 2
- **4-Gram Gewichtung** – Höchste Gewichtung (0.95) für kontextreichste Muster

### Cerebellum – 4-Gram Regeln
- **4-Gram Regelextraktion** – Confidence-Schwelle ≥ 35%
- **Größerer Recent-Buffer** – 10 → 15 für 4-Gram Matching
- **Statistik erweitert** – `rules_4gram` im Sensor sichtbar

### Brain Review (neu)
- **Cortex.brain_review()** – Alle Agents analysieren gemeinsam den Brain-Zustand
- **Vollständige Statistik** – Patterns, Accuracy, Regeln, Habits, Energie-Trends
- **Agent-Feedback** – health_score, strengths, weaknesses, suggestions
- **Service** – `kontinuum.brain_review` (manuell aufrufbar)
- **Automatisch monatlich** – Alle 30 Tage ab 500 Events
- **Ergebnis als persistent_notification** in Home Assistant

### Bugfixes
- **Dispatcher-Fix** – `async_dispatcher_send()` mit positional args statt kwargs (behebt TypeError)
- **Blocking I/O behoben** – `load_custom_profiles()` läuft jetzt via `async_add_executor_job` statt synchron im Event Loop
- **Profil-Warnung bereinigt** – Fehlende `kontinuum_context_profile.json` erzeugt nur noch debug-Log statt warning

---

## v0.15.0 – Cortex (Multi-Agent LLM Layer)

### Cortex – Bewusstes Denken
- **Multi-Agent-System** – Bis zu 3 LLM-Agents mit eigenen Rollen (Comfort, Energy, Safety, Custom)
- **5 Provider** – Ollama (lokal), OpenAI, Claude, Gemini, Grok – alle über pure HTTP (kein SDK nötig)
- **Multi-Agent-Diskussion** – Runde 1: Jeder Agent denkt parallel. Runde 2: Agents sehen alle Vorschläge und reagieren
- **Konsens-Findung** – KONTINUUM (Prefrontal) ist der Orchestrator: Mehrheitsabstimmung + Veto-Recht des Safety-Agents
- **Cortex Bridge** – LLM-Ergebnisse fließen zurück ins Gehirn:
  - Hippocampus speichert Cortex-Events als synthetische Erfahrung
  - Basalganglien registrieren Cortex-Aktionen für TD-Learning
  - Amygdala lernt aus Veto-Signalen (Risiko-Lernen)
  - Prefrontal passt Utility-Weights aus Agent-Einigkeit an
  - Cerebellum markiert häufige Cortex-Patterns als Reflex-Kandidaten (ab 5x)
- **cortex_patterns persistent** – Werden in brain.json.gz gespeichert

### Config Flow – Ollama Model Discovery
- **URL-Normalisierung** – `localhost` → `http://localhost:11434` (http:// und Port automatisch)
- **Verbindungstest** – Prüft ob Ollama erreichbar ist, zeigt Fehlermeldung
- **Modell-Dropdown** – Fragt `/api/tags` ab und zeigt alle installierten Ollama-Modelle als Dropdown
- **Zweistufiger Agent-Flow** – Schritt 1: Provider + URL, Schritt 2: Modell wählen
- **Status-Anzeige** – "Verbunden – 5 Modelle gefunden" direkt im Config Flow

### Dashboard
- **Sidebar-Panel** – Dashboard erscheint als Eintrag in der HA-Sidebar (mdi:brain Icon)
- **Automatische Registration** – `async_register_built_in_panel("iframe")` statt nur Datei-Kopie
- **Sauberes Unload** – Panel wird bei Deinstallation automatisch entfernt

### Agent-Entitäten
- **Cortex Agent-Sensoren** – Pro konfiguriertem Agent ein eigener Sensor (`sensor.kontinuum_cortex_agent_1/2/3`)
- **Status** – active / idle / error (basierend auf letztem Call und Fehlerrate)
- **Attribute** – Rolle, Provider, Modell, Aufrufe, Fehlerrate, letzter Call
- **Rollen-Icons** – Comfort (Sofa), Energy (Solar), Safety (Shield), Custom (Robot)

### Services
- `kontinuum.configure_agent` – Agent per Service konfigurieren
- `kontinuum.cortex_consult` – Cortex-Beratung manuell auslösen
- `kontinuum.remove_agent` – Agent entfernen

---

## v0.14.0 – Native Sensor Platform + Deinstallation

- **Native Sensoren** – Alle Sensoren als echte HA-Entitäten (kein `hass.states.async_set()` mehr)
- **Aktivitäts-Sensoren** – `sensor.kontinuum_*_activity` direkt in der Integration erstellt. Die `template`-Sensoren und `input_number.k_*`-Helfer aus `configuration.yaml` können entfernt werden
- **Basalganglien-Sensor** – `sensor.kontinuum_basal_ganglia` zeigt Habits, Go/NoGo, Q-Entries
- **Area-Fix** – HA-Areas werden jetzt direkt als Raum genutzt, auch wenn sie nicht in der internen Map stehen
- **Label-Support** – HA-Labels werden als Raum-Hinweis ausgewertet
- **Saubere Deinstallation** – `async_remove_entry` löscht `brain.json.gz`, `input_number.k_*`-Helfer und alle Entitäten
- **Komprimiertes Speichern** – `brain.json` → `brain.json.gz` (gzip, ~85% kleiner)
- **SAVE_INTERVAL** – 300s → 600s (weniger SD-Schreibzugriffe)

---

## v0.13.1 – Basalganglien + Fixes

- **Basalganglien** – Belohnungslernen (Go/NoGo, Q-Values, Habits)
- **Spatial Cortex** – `area_unknown` bei Raumbestimmung ignoriert
- **Hypothalamus** – Energy Cooldown 600s → 60s

---

## v0.12.0 – Intelligenz-Upgrade

- **Sonnenstand-Bewusstsein** – Thalamus nutzt `sun.sun` für Sonnenhöhe und Tag/Nacht
- **Hypothalamus-Trends** – erkennt Temperatur-, Batterie- und Solar-Verläufe
- **Wochentag-Gedächtnis** – Hippocampus unterscheidet Werktage von Wochenenden (96 Buckets)
- **Bewegungsmuster** – Spatial Cortex lernt Raum-Sequenzen und sagt den nächsten Raum vorher
- **Zirkadiane Priors** – Insula nutzt Tageslicht für biologisch plausiblere Modus-Erkennung
- **Mode-Index-Fix** – Hippocampus las versehentlich Temperatur statt Modus
- Kontextvektor erweitert: 15 → 21 Dimensionen

---

## v0.11.0 – Unknown-Filter

- Unknown-Token-Filter: 75% Müll-Transitions eliminiert
- Entity-Whitelist: nur Entities mit bekanntem Raum erzeugen Tokens
- Min-Delay-Filter im Cerebellum
- Migrations-Logik bereinigt alte Unknown-Daten beim Update

---

## v0.10.0

- Config Flow Fix (OptionsFlow für HA 2024.x+)
- Adaptive Hippocampus-Buckets (6→24→48 je nach Datenmenge)
- Self-Loop-Filter im Cerebellum
- Spatial Cortex Tuning (Hysterese 1.2, Confirmation 30s)
- 11 Dashboard-kompatible Sensoren
- 30+ deutsche Raum-Keywords im Thalamus

---

## v0.9.0

- Config Flow (kein configuration.yaml mehr)
- Persönlichkeits-Presets (Mutig/Ausgeglichen/Konservativ)
- Alle Service-Calls async

---

## v0.8.0

- Personen-Zähler, HA Notifications, Licht-Szenen
- Services (enable_scenes, set_scene, status)
- kontinuum_mode_changed Event
