# Changelog

## v0.22.0 – Confirm-UI, kontextbewusstes Cerebellum, Reject-RPE, Chunking

### 🔴 Confirm-Modus UI/UX (kritisch)
- **Pro Aktion ein "Ausführen / Ablehnen"-Button im Dashboard** – die wartenden
  Bestätigungen erscheinen jetzt prominent oberhalb des Debug-Panels mit
  per-Aktion-Schaltflächen. Vorher gab es nur "Alle bestätigen", deshalb stand
  `prefrontal.total_executions` permanent bei 0.
- **Begründungstext sichtbar** – jede wartende Aktion zeigt jetzt *warum*
  KONTINUUM handeln will: gefeuerte Cerebellum-Regel inkl. n-gram-Sequenz,
  Hippocampus-Confidence + Beobachtungszahl, aktueller Insula-Modus,
  Tageszeit-Bucket, Amygdala-Hinweise. Reasoning landet auch in der
  Notification und im `kontinuum_confirm_requested`-Event.
- **Reichhaltige Sensor-Attribute** – neue `pending_confirms_list` am
  `sensor.kontinuum_prefrontal` mit allen Details (id, room, semantic, action,
  conf/util/risk, n_obs, source, reasoning, context, age_s, expires_in_s).
- **Neuer Service-Pfad `reject_action`** liefert jetzt echtes RPE statt nur
  ein Utility-Weight-Decrement (siehe nächster Punkt).

### Reinforcement Learning aktiv im Confirm-Modus
- **`reject_action` speist negatives Feedback in die Basalganglien** – das
  Q-Value der abgelehnten Aktion sinkt, NoGo-Pathway wird gestärkt. Vorher
  blieb `basal_ganglia.total_updates` bei 0, weil Rejects nirgendwo gelernt
  wurden.
- **`PrefrontalCortex.reject_pending()`** vereinheitlicht den Reject-Pfad
  (Amygdala-Risiko-Lernen, BG-RPE, PFC-Utility, Feedback-Log, Event).
- Neues Event `kontinuum_confirm_rejected` für Automationen.

### Kontextbewusstes Cerebellum
- **Regeln tragen jetzt `context_buckets`** – beim Kompilieren wird notiert
  in welchen Hippocampus-Buckets (Tageszeit × Modus × Hypothalamus) eine
  Routine signifikant beobachtet wurde. Damit lernt das Cerebellum
  `(token, context) → token` statt rein sequenziell.
- **`check()` moduliert mit Kontext** – Regeln aus dem aktuellen Bucket
  bekommen +20% Score, fremde Buckets -25%. Eine "Licht aus"-Regel um
  23 Uhr feuert weiter im Schlafkontext, aber nicht mehr morgens um 10.
- **`set_context(bucket)`** als API für den Setup-Loop.
- **`rules_context_aware`** in den Stats und im `kontinuum.rules` Sensor.

### Hierarchisches Chunking
- **`CerebellumChunk` + `_detect_chunks()`** – wiederkehrende Regelketten
  (rule_a.target == rule_b.trigger) werden als zusammenhängende
  Mehrschritt-Prozeduren erkannt (greedy, max 5 Schritte). Erster Schritt
  von Vorhersage zu Absichtserkennung – die Basis für "Filmabend starten"
  als ein Token.
- **Persistenz** – Chunks landen in `to_dict`/`from_dict` und in
  `cerebellum.stats.top_chunks` für Dashboard und Brain-Export.

### Aufgeräumt
- `prefrontal.total_executions` jetzt im `kontinuum.rules` Sensor sichtbar.

---

## v0.21.0 – Neurorhythmen, Active-Modus Fix, Cerebellum feuert, HACS-ready

### Neurorhythmen (neurorhythms.py)
- **Circadiane Modulation** – Lernrate variiert über 24h: 0.5x nachts bis 1.3x morgens (Cosinus-Kurve, Peak 8:00)
- **Phasische Dopamin-Bursts** – Unerwartet positive Outcomes (surprise > 0.5) lösen 3-8x Lernverstärkung aus
- **Synaptic Homeostasis (SHY)** – Proportionale Herunterskalierung aller Gewichte bei Überlernung (0.85-0.98x)
- **Dopamin-Dip bei Override** – Wenn User eine Aktion korrigiert, sinkt die Lernrate
- **Dashboard** – Circadian-Indikator (☀/◐/☾), Dopamin-Level, Burst-Statistiken

### Dream Replay (Sleep Consolidation erweitert)
- **Kreative Cross-Context-Rekombination** – Starke Muster aus verschiedenen Kontexten werden verknüpft (wie REM-Schlaf)
- **SHY-Integration** – Nach intensivem Lernen werden alle Hippocampus-Gewichte proportional skaliert
- **Neue Stats** – Dream-Connections, Homeostasis-Faktor im Dashboard und Status-Sensor

### Active/Confirm-Modus Fix (kritisch)
- **Active-Modus funktioniert jetzt** – Alle ACTIONABLE_SEMANTICS automatisch freigeschaltet (vorher: `activated_semantics` war leer → EXECUTE nie erreicht)
- **Confirm-Modus funktioniert jetzt** – Feuert `kontinuum_confirm_requested` Event (für HA-Automationen nutzbar)
- **MIN_OBS_EXECUTE** von 100 auf 30 gesenkt (realistischer für Smart Home)

### Cerebellum feuert Regeln
- **`cerebellum.check()` war nie aufgerufen** – 47 gelernte Regeln waren totes Wissen, jetzt werden sie bei jedem Event geprüft
- **Reflex-Predictions** – Gefeuerte Regeln werden als Top-Prediction mit höchster Priorität injiziert
- **`stats.total_fired`** – Neuer Counter für Dashboard und Status-Sensor

### HACS-Vorbereitung
- **GitHub Actions** – HACS Validate + hassfest Workflows (SHA-gepinnt)
- **Englische Übersetzung** – `translations/en.json` für internationales Publikum
- **manifest.json** – `issue_tracker` ergänzt, Keys alphabetisch sortiert
- **CONFIG_SCHEMA** – `cv.config_entry_only_config_schema` für hassfest-Kompatibilität
- **services.yaml** – 5 fehlende Services ergänzt (set_mode, confirm_action, reject_action, cortex_sequential, brain_review)
- **Codex-Überbleibsel entfernt** – 6 nicht verwendete Dateien die hassfest blockierten

### Predictive Processing (aus vorheriger Session)
- **Surprise-Based Learning** – Events die erwartet werden, werden kaum gelernt; Überraschungen maximal
- **70% Prediction Error + 30% Novelty** – Zwei Komponenten bestimmen den Surprise-Wert
- **Lerngewicht 0.2x-2.5x** – Moduliert Hippocampus-Lernen basierend auf Surprise
- **Dashboard** – Surprise-Indikator (○/◉/⚡) mit Farbkodierung

---

## v0.20.0 – Denken verbessert: Sleep Consolidation, ACC, MetaPlasticity + Dashboard

### Sleep Consolidation (Hippocampaler Replay)
- **Konsolidierung in ruhigen Phasen** – Nach 30 Min Stille werden Muster "wiedergespielt"
- **Schwache Muster vergessen** – Muster unter 1.5 Count werden beschleunigt vergessen, unter 0.3 gelöscht
- **Starke Muster verstärken** – Muster über 5.0 Count werden leicht verstärkt (Replay-Effekt)
- **Cerebellum Re-Extraction** – Regeln werden bei Konsolidierung neu extrahiert
- **Q-Value Smoothing** – Extreme Basalganglien-Werte leicht in Richtung Mittelwert gezogen
- **Cooldown 1h** – Max 1 Konsolidierung pro Stunde, min 50 Events nötig

### Anterior Cingulate Cortex (ACC) – Konfliktmonitor
- **Erkennt widersprechende Module** – z.B. Hippocampus will handeln, Amygdala will Veto
- **Dynamische Schwellen** – Bei vielen Fehlern wird vorsichtiger, bei Erfolg mutiger
- **Cognitive Control Signal** – Kombination aus Konflikt-Level und Fehlerrate
- **Cortex-Eskalation** – Bei hoher Unsicherheit wird LLM-Beratung empfohlen
- **EMA-basiert** – Sanfte Anpassung ohne Sprünge

### MetaPlasticity (einverdrahtet)
- **War toter Code, jetzt aktiv** – Passt Lernraten aller Module alle 24h an
- **Sammelt Metriken** – Error-Rate, Success-Rate, Confidence pro Modul
- **Automatische Anpassung** – Hohe Fehler → schneller lernen, hoher Erfolg → stabilisieren
- **Persistenz** – Eigene .json.gz Datei

### Dashboard – Alle neuen Areale
- **6 neue Gehirn-Regionen** in der SVG-Karte: ACC (rosa), Formatio Reticularis (grau-blau), Locus Coeruleus (violett), Entorhinaler Cortex (grün), Nucleus Accumbens (orange), Sleep Consolidation (Status)
- **Neue Neuralverbindungen** – ACC↔Prefrontal, Entorhinal↔Hippocampus, LC↔Thalamus, NAcc↔Basalganglien
- **Modul-Panel erweitert** – Alle neuen Module mit Live-Statistiken
- **Debug-Panel** – Neuromodulation-Sektion zeigt ACC, Reticular, LC, Entorhinal, Sleep, Metaplastizität
- **Brain-Animation** – Reticular und Locus feuern bei Events mit zeitversetzter Kaskade

### Sensoren
- **Neue Activity-Sensoren** – `sensor.kontinuum_acc_activity`, `sensor.kontinuum_sleepconsolidation_activity`
- **Status-Sensor erweitert** – Zeigt alle Aux-Module: Reticular, LC, Entorhinal, ACC, Sleep, Metaplastizität

---

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
