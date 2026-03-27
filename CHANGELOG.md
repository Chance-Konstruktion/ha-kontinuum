# Changelog

## v0.19.0 – Config Flow Redesign, Entity-Filter-Pipeline, Home-Only & Hilfsmodule

### Config Flow – Menü-basierte Navigation
- **Menü statt Durchklicken** – Options Flow nutzt `async_show_menu()` mit Kategorien: Allgemein, Cortex, Speichern
- **Agents bleiben erhalten** – Bestehende Agents werden beim Öffnen geladen und nur bei expliziter Aktion geändert
- **Agent-Übersicht** – Alle konfigurierten Agents auf einen Blick mit Bearbeiten/Entfernen/Hinzufügen
- **Kein versehentliches Löschen** – Vergessene Checkboxen löschen keine Agent-Daten mehr
- **Generische Agent-Steps** – `agent_setup` und `agent_model` mit Slot-Parameter statt 8 Einzel-Steps

### Entity-Filter-Pipeline
- **Mehrstufige Pipeline** – Labels → Hard Filter → Track Mode → Heuristik
- **3 Track Modes** – `standard` (Opt-out), `labeled` (Opt-in per `kontinuum`-Label), `auto` (Label + Heuristik)
- **`ignore_kontinuum` Label** – Entities mit diesem Label werden nie getrackt (höchste Priorität)
- **`kontinuum` Label** – Entities werden immer getrackt, auch in ignorierten Domains
- **Dynamischer Label-Refresh** – Labels alle 5 Minuten aktualisiert, kein Neustart nötig
- **Heuristik-Filter** – Erkennt verhaltensrelevante Sensoren (Bewegung, Tür, Fenster, Helligkeit etc.)

### Home-Only Modus
- **Pausiert bei Abwesenheit** – Lernen und Vorhersagen stoppen wenn niemand zuhause ist
- **Konfigurierbar** – Ein/Aus in den allgemeinen Einstellungen

### Hilfsmodule (Aux Modules)
- **Formatio Reticularis** – Burst-Filter unterdrückt Ereignis-Stürme per Cooldown
- **Nucleus Accumbens** – Belohnungssignal bei Nutzer-Feedback (Accept/Override)
- **Locus Coeruleus** – Arousal-Level aus Ereignisdichte (EMA)
- **Entorhinaler Cortex** – Raum-Transitions-Map mit automatischem Pruning
- **Persistenz** – Alle Hilfsmodule werden in eigenen gzip-JSON-Dateien gespeichert

### Übersetzungen
- **strings.json** und **de.json** an neue Menü-Struktur angepasst
- **Slot-parametrisierte Agent-Steps** – `{slot}` Platzhalter statt duplizierte Strings

---

## v0.18.0 – Betriebsmodi, Confirm-Modus, LLM-Retry & Sequential Agents

### Betriebsmodi (Shadow / Confirm / Active)
- **3 Betriebsmodi** – Shadow (nur beobachten), Confirm (Bestätigung anfordern), Active (selbständig schalten)
- **`kontinuum.set_mode`** – Service zum Umschalten: `{mode: "shadow/confirm/active"}`
- **Confirm-Modus** – KONTINUUM fragt per Notification vor dem Schalten. Bestätigung mit `kontinuum.confirm_action`
- **`kontinuum.reject_action`** – Aktionen im Confirm-Modus ablehnen (negatives Feedback)
- **Shadow-Modus jetzt deaktivierbar** – Über `set_mode` auf "active" oder "confirm" wechseln

### Cerebellum Outcome-Tracking
- **Automatische Erfolgskontrolle** – Nach EXECUTE wird nach 3s der State geprüft und `record_outcome` aufgerufen
- **Erfolg** = neuer State entspricht dem gewünschten State

### Cortex – LLM-Retry & Sequential Mode
- **Retry-Mechanismus** – Max 3 Versuche mit exponentiellem Backoff (1s → 2s → 4s) bei transienten Fehlern
- **Nur transiente Fehler** – Timeout, 5xx, ConnectionError (4xx-Fehler werden sofort weitergereicht)
- **Sequentieller Modus** – `kontinuum.cortex_sequential` für Systeme mit nur einer GPU/Ollama-Instanz
- **Agents nacheinander** statt parallel befragen (kein GPU-Memory-Overflow)

### Service-Calls mit korrekten Parametern
- **Climate** – `hvac_mode` wird automatisch als data-Parameter mitgeliefert
- **Media** – entity_id wird korrekt in data-Dict übergeben

### Dashboard-Fixes
- **Basalganglien** – Als aktives Modul angezeigt (nicht mehr "Phase 4")
- **Brain-Animation** – Module feuern zeitversetzt basierend auf tatsächlicher Aktivität
- **Betriebsmodus-Buttons** – Shadow/Confirm/Active direkt im Debug-Panel umschaltbar
- **Basalganglien-Stats** – habits, Q-Entries und Dopamin-Signal sichtbar

### API-Keys
- **Password-Feld** – API-Keys werden im Config-Flow als Password-Eingabe angezeigt

---

## v0.17.0 – Coordinator-Agent, Dashboard-Auth & Auto-Reload

### Cortex – 4. Agent-Slot mit Coordinator-Rolle
- **4 Agent-Slots** – Erweitert von 3 auf 4 konfigurierbare LLM-Agents
- **Coordinator-Rolle** – Neuer Agent-Typ: sieht alle Worker-Vorschläge und trifft die finale Entscheidung per LLM
- **Worker/Coordinator-Split** – Worker-Agents (1-3) denken parallel, Coordinator entscheidet danach
- **Safety-Veto** hat weiterhin absoluten Vorrang (auch vor dem Coordinator)
- **Coordinator-Prompt** – Spezialisierter System-Prompt für Abwägung zwischen Komfort, Energie und Sicherheit
- Services `configure_agent` und `remove_agent` unterstützen Slot 1-4

### Dashboard – Automatische Authentifizierung
- **Kein manueller Token mehr nötig** – Dashboard liest Auth-Token automatisch aus der HA-Session (same-origin iframe)
- **Token-Refresh bei 401** – Abgelaufene Tokens werden automatisch erneuert
- **Hardcodierten JWT entfernt** – Keine Secrets mehr in der HTML-Datei

### Options-Flow – Auto-Reload
- **Automatisches Neuladen** – Nach Speichern der Konfiguration wird die Integration automatisch neu geladen
- **Neue Entitäten sofort verfügbar** – Cortex-Agent-Sensoren werden ohne manuelles Neuladen erstellt

### Blocking I/O Fix
- **async_remove_entry** – `shutil.rmtree` und `os.remove` laufen jetzt im Executor-Thread statt im Event Loop

### Dokumentation
- **README.md** – Komplett überarbeitet: Dashboard-Services dokumentiert, Cortex klar als optional gekennzeichnet
- **README_EN.md** – Neue englische README für internationales Publikum
- **HACS-Readiness** – codeowners in manifest.json gesetzt

---

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
