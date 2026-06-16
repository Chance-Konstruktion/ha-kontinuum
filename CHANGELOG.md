# Changelog

## v0.28.1 – Schönere Dropdowns im Config-/Options-Flow (2026-06-16)

### Changed
- **Statische Auswahlfelder als echte Dropdown-`SelectSelector`** statt HAs
  Basis-Rendering: **Persönlichkeit**, **Betriebsmodus**, **Tracking-Modus**
  (Allgemein) sowie **Rolle** und **Provider** (Agent-Setup) sind jetzt
  durchsuchbare, sauber gestylte Dropdowns. Werte bleiben unverändert (Strings)
  → keine Verhaltens-/Persistenz-Änderung. Dynamische Listen (Modell, Menü) und
  das Diskussionsrunden-Feld bleiben wie sie sind.

## v0.28.0 – Interval Timing in der Pro-Pipeline (innere Stoppuhr) (2026-06-16)

### Added
- **Interval Timing** (aus `kontinuum-core 0.6.0`) in die Pro-Pipeline verdrahtet:
  lernt die **Dauer zwischen Wiederholungen** eines Tokens und blendet eine
  überfällige, regelmäßige Kadenz (z.B. „Staubsauger alle 4 Wochen") als
  Vorhersage ein. Injektion erfolgt **nach** der Surprise-Berechnung → kein
  Einfluss auf das Anomalie-Signal. Persistenz als eigene `interval_timing.json.gz`.
- Ergänzt den Suprachiasmatischen Nukleus (Tagesuhr) um das **Dauer-/Kadenzgefühl**.

### Changed
- `kontinuum-core`-Anforderung auf **`>=0.6.0`** angehoben.

## v0.27.1 – Cortex-Options-Flow: klarere Texte & Feld-Hinweise (2026-06-16)

### Changed
- **Cortex-Schritte im Options-Flow lesbarer gemacht** (reine Übersetzungs-/Text-
  Politur in `strings.json` + `translations/de.json` + `translations/en.json`,
  keine Logik-Änderung):
  - Jedes Feld hat jetzt einen **Hinweistext** (`data_description`) — z. B. unter
    **URL**: „Nur die Basis-URL … `/v1/chat/completions` wird automatisch
    angehängt", unter **Provider** der Hinweis auf **Custom/OpenAI-kompatibel
    (OpenCLAW)**, unter **Diskussionsrunden**/**Sequential Mode** eine kurze
    Erklärung.
  - Klarere Schritt-Beschreibungen (Cortex ist optional; bis zu 4 Agents) und
    ein 🧠-Titel.

### Docs
- **`docs/SETTINGS.md`** neu — vollständige Einstellungs-Referenz (Presets,
  Betriebsmodi, Tracking/Labels, Home-Only, Gerätetypen, **Cortex inkl.
  OpenCLAW**, Services, Events, Sensoren).
- `docs/ARCHITECTURE.md`: veralteten „8 Module"-Stand korrigiert + Verweise auf
  die Core-Modul-/Pipeline-Referenz.

## v0.27.0 – Erweiterte Hirnareale & Botenstoffe (2026-06-15)

> Baut auf v0.26.0 auf (die engine-only Observability-Entitäten wurden parallel
> nach `main` gemergt; daher diese Version 0.27.0 statt 0.26.0).

### Added
- **Sieben neue neuro-inspirierte Module** aus `kontinuum-core 0.5.0`, in die
  Pro-Pipeline verdrahtet — alle O(1) pro Event, Raspberry-Pi-tauglich, starten
  neutral (kein verändertes Verhalten, bis etwas gelernt wurde):
  - **Laterale Habenula** – Anti-Reward: wiederholt abgelehnte Vorschläge werden
    im Ranking unterdrückt (Schluss mit „Nerven"). Lernt am Override-/Accept-Pfad
    mit demselben `(state, action)`-Schlüssel wie das Ranking.
  - **Nucleus Subthalamicus** – „Hold your horses"-Bremse unter Konflikt
    (verhaltenswirksam im Core; in Pro vorhanden & persistiert).
  - **Nucleus Suprachiasmaticus** – gelernte innere Uhr: moduliert die Lernrate
    nach dem echten Tagesrhythmus des Haushalts (±15 %).
  - **Cortisol** – langsames Stress-Hormon: macht das Ranking in chaotischen
    Phasen vorsichtiger (bis −30 %).
  - **Acetylcholin** – erwartete Unsicherheit: dämpft Lernen in verlässlich
    verrauschten Kontexten.
  - **Serotonin** – langsame Stimmungs-/Geduld-Baseline.
  - **BDNF** – schützt bewährte Reflexe vor pauschalem Vergessen in der
    Schlaf-Konsolidierung (Mindestgewicht statt Löschen).
- Persistenz je Modul als eigene `*.json.gz` (über `AUX_MODULE_FILES`).

### Changed
- `kontinuum-core`-Anforderung auf **`>=0.5.0`** angehoben.
- Lernraten-Pipeline, Ranking, Outcome-Lernen und Sleep-Consolidation um die
  neuen Signale erweitert — rein additiv.

## v0.26.0 – Observability: Surprise / Anomalie / Routinen / Konsolidierung als Entitäten (2026-06-15)

### Added
- **Vier neue, engine-only Observability-Entitäten** heben die wichtigsten
  Engine-Signale aus den Status-Attributen in eigenständige, graph- und
  historienfähige Entitäten – **ohne jede LLM-/Cortex-Abhängigkeit**:
  - `sensor.kontinuum_surprise` – aktuelles Surprise-Niveau (Prediction-Error,
    `0.0`–`1.0`, `state_class: measurement`). Attribute: Baseline, Durchschnitt,
    adaptive Anomalie-Schwelle, Lerngewicht, Surprise-Quote, Max.
  - `binary_sensor.kontinuum_anomaly` – `device_class: problem`, **an**, sobald
    das aktuelle Surprise die robuste (Median+MAD) Anomalie-Schwelle erreicht.
    Gleiche Semantik wie `binary_sensor.kontinuum_lite_anomaly` der Lite-Variante
    → Automationen reagieren identisch. (Neue `binary_sensor`-Plattform.)
  - `sensor.kontinuum_routines` – Roll-up gelernter Routinen (Cerebellum-Chunks
    + Basalganglien-Habits). Attribute: Chunks, Regeln, Habits, Go/NoGo, Top-Chunks.
  - `sensor.kontinuum_consolidation` – Anzahl Schlaf-Konsolidierungs-Läufe
    (`state_class: total_increasing`) plus Detailbilanz des letzten Laufs
    (pruned / reinforced / rules / dream-connections / homeostasis).

### Notes
- Die Entitäten lesen ausschließlich aus den **Kern-Gehirnmodulen** (`predictive`,
  `cerebellum`, `basal_ganglia`, `sleep_consolidation`) und sind damit **immer**
  verfügbar, auch wenn der Cortex (LLM) deaktiviert ist. Fehlt ein Modul,
  degradieren sie sauber auf `None`/leer. Bestätigt das Leitprinzip: KONTINUUM
  läuft eigenständig – LLM/OpenCLAW sind reine Features.

## v0.25.0 – Generischer Custom-/OpenAI-kompatibler Cortex-Provider (2026-06-14)

### Added
- **Custom-Provider für die Cortex-Schicht.** Neben Ollama/OpenAI/Claude/Gemini/
  Grok lässt sich jetzt **jeder OpenAI-kompatible** Endpunkt einbinden – z.B. ein
  **OpenCLAW-Bot**, ein lokaler vLLM-/LM-Studio-Server oder OpenRouter. Im
  Agent-Setup Provider **„Custom / OpenAI-kompatibel"** wählen und **Basis-URL +
  API-Key + Model** eintragen (erscheint automatisch im Dropdown, da die Liste
  aus `PROVIDERS` gebaut wird). Robust: kein erzwungenes `response_format` (nicht
  jeder Server unterstützt es) und defensives Auslesen der Antwort – die Reply
  läuft ohnehin durch `normalize_proposal`, das non-strikte JSONs verkraftet.

## v0.24.0 – Cortex-LLM-Schicht: Bridge-Fix, robustes Parsing, striktes Safety-Gate (2026-06-14)

### Security
- **Gefährliches Safety-Loch geschlossen.** Cortex-Konsens-Aktionen wurden
  **ohne jede Validierung** und **unter Ignorieren des Betriebsmodus**
  ausgeführt – sie feuerten echte `service.call`s **sogar im Shadow-Modus**.
  Neu: Aktionen werden validiert (existierende Entity + existierender Service +
  **aktivierter** Semantik-Typ) und **modus-korrekt durch dieselbe
  Confirm/Execute-Pipeline wie PFC-Entscheidungen** geroutet – Shadow / nicht
  aktiviert / nicht validierbar → nur beratend, Confirm → `queue_confirm`
  (Mensch bestätigt via `kontinuum.confirm_action`), Active → `_execute_decision`.
  Fail-safe: ausgeführt wird nur bei Active + aktiviert + validiert.
- **Gemini-API-Key** wandert von der URL-Query in einen `x-goog-api-key`-Header
  (Request-URLs landen in Proxy-/Debug-Logs).

### Fixed
- **Cortex→Gehirn-Bridge crashte** bei jedem nicht-vetoten Aktions-Konsens:
  `integrate_into_brain` rief `hippocampus._get_context()` und
  `thalamus.get_or_create_token()` auf – beide existierten im Core nicht
  (`AttributeError`), wodurch die nachfolgenden Integrationsschritte nie liefen.
  Jetzt mit echtem 21-dim-Kontextvektor + der seit **kontinuum-core 0.4.1**
  öffentlichen `get_or_create_token()`.

### Changed
- **Robustes LLM-Antwort-Parsing:** Agent-Antworten laufen durch
  `kontinuum_core.normalize_proposal` statt nacktem `json.loads` – übersteht
  ` ```json `-Fences/Prosa/JSON-Listen und koerziert `priority`/`veto` in ein
  striktes Schema (kein Bruch der Konsens-Arithmetik mehr bei String-Werten).
- **Reicherer Prompt:** `build_llm_context`/`render_llm_context` geben den Agents
  jetzt den Hirn-Zustand **inkl. Anomalie-/Surprise-Signal, 0–1-Skalen** und der
  Liste tatsächlich bekannter Entities (weniger halluzinierte `entity_id`s).
- Toten No-op-Code in `integrate_into_brain` (berechnete und verworfene
  Confidence) entfernt.
- `manifest.json` pinnt **`kontinuum-core>=0.4.1`**.

## v0.23.0 – Regelkreise geschlossen / Neuro-Wiring v2 + 3-Repo-Refactor (2026-06-14)

### Changed (Release)
- **`manifest.json`** pinnt jetzt **`kontinuum-core>=0.1.2`** (auf PyPI
  veröffentlicht) – der Core-Release mit vollständiger `to_dict`/`from_dict`-
  Persistenz und der durchverdrahteten 18-Modul-Pipeline, auf die das
  geschlossene Regelkreis-Wiring dieser Version aufsetzt.

### Regelkreise geschlossen (Neuro-Wiring v2)

### Fixed
- **UnboundLocalError im Feedback-Pfad:** Bei Override-Erkennung und
  impliziter Akzeptanz wurde `neurorhythms.register_outcome(token_id, …)`
  mit einer Variable aufgerufen, die erst ~50 Zeilen später definiert
  wird. Folge: Genau in den Momenten, in denen das System aus
  User-Feedback lernen soll, brach die Event-Pipeline mit einer
  Exception ab (Thalamus, Hippocampus, PFC liefen für dieses Event nicht
  mehr). Jetzt wird der Token der betroffenen KONTINUUM-Aktion *vor*
  `check_override()`/`check_implicit_positives()` gesichert (beide
  löschen ihre `own_actions`-Einträge) und als korrektes Dopamin-Ziel an
  Neurorhythms gemeldet.

### Changed
- **ACC-Konfliktmonitor sieht jetzt echte Konflikte:** Bisher bekam
  `acc.observe_decision()` immer nur den Hippocampus-Top-Kandidaten –
  mit einer einzigen Stimme ist Konflikt per Definition 0, und der
  Amygdala-Zweig prüfte ein Attribut (`last_risk_score`), das es im Core
  nie gab (toter Code). Neu: `_build_acc_proposals()` sammelt pro Event
  die Stimmen von Hippocampus (Top-Rohvorhersage), Cerebellum (gefeuerte
  Reflex-Regel), Basalganglien (nur wenn ihr Re-Ranking die Reihenfolge
  kippt) und Amygdala (Veto-Stimme bei `decision.risk > 0.5`).
- **Cognitive-Control-Loop geschlossen:** `acc.cognitive_control`
  (EMA aus Konfliktlevel + Fehlerrate) dämpft jetzt die Confidence im
  Basalganglien-Ranking um bis zu 25 %. Widersprechen sich die Module
  oder häufen sich falsche Outcomes, werden PFC-Entscheidungen
  automatisch vorsichtiger (mehr OBSERVE/SUGGEST statt EXECUTE); läuft
  alles rund, klingt die Dämpfung über die EMA wieder ab. Vorher wurde
  der ACC-Output nirgends konsumiert (write-only Modul).
- **Fehlerraten-Hälfte von `cognitive_control` jetzt aus echtem
  User-Feedback:** Der Cognitive-Control-Loop nutzt
  `conflict·0.6 + error_rate·0.4`, aber `acc.observe_outcome()` wurde nur
  im autonomen Execute-Pfad (ACTIVE-Modus, 3-Sekunden-Hardware-Check)
  gespeist. Für jeden Nutzer ohne autonome Aktionen (SHADOW/CONFIRM)
  blieb `error_rate` damit dauerhaft 0 – `cognitive_control` reagierte nur
  auf Modul-Uneinigkeit, nie auf tatsächliche Fehler. Jetzt meldet der
  bestehende User-Feedbackpfad Overrides als Fehler
  (`observe_outcome(False)`) und implizite Akzeptanz als Erfolg
  (`observe_outcome(True)`) an den ACC – symmetrisch zu
  Basalganglien/Accumbens/Neurorhythms, die dort längst gespeist wurden.
  Wiederholte Korrekturen bremsen das Ranking jetzt spürbar; konsistente
  Akzeptanz lässt es über die EMA wieder lockerer werden.
- **Entorhinale Antizipation aktiviert:** Der Entorhinal-Cortex lernte
  Raumübergänge, wurde aber nie abgefragt. Beim Betreten eines Raums
  wird jetzt `predict_next_room()` gestellt und Tokens im erwarteten
  nächsten Raum bekommen im Ranking einen kleinen Priming-Boost (+0.05
  Confidence) – das System denkt der wahrscheinlichsten Bewegung voraus.

### Added
- **`tests/test_wiring.py`:** 9 Unit-Tests für `_rank_with_basal_ganglia`
  und `_build_acc_proposals` – mit echten kontinuum-core-Modulen
  (Thalamus, BasalGanglia, ACC, Decision) statt Mocks. Läuft in der
  Smoke-CI mit.

### 3-Repo-Refactor (Phase 1+)

### Fixed
- **ImportError beim Laden der Integration:** `metaplasticity.py`
  importierte `DOMAIN` aus `const.py`, das nur `STORAGE_PATH` definierte –
  damit schlug `from .metaplasticity import MetaPlasticity` in
  `__init__.py` fehl und die Integration konnte gar nicht starten.
  `DOMAIN` ist jetzt zentral in `const.py` definiert; `__init__.py`,
  `config_flow.py` und `sensor.py` importieren es von dort statt es
  dreifach zu duplizieren.
- **`VERSION` in `__init__.py` (0.20.0) war hinter `manifest.json`
  (0.23.0) zurückgefallen** – Statussensor und Notifications zeigten die
  falsche Version. Synchronisiert; die neue Smoke-Test-CI erzwingt den
  Gleichstand ab jetzt.

### Changed
- **Pro-auf-Core-Migration abgeschlossen (18/18):** Die restlichen 13
  Brain-Module (`amygdala`, `anterior_cingulate`, `basal_ganglia`,
  `cerebellum`, `hippocampus`, `hypothalamus`, `insula`, `neurorhythms`,
  `predictive_processing`, `prefrontal_cortex`, `sleep_consolidation`,
  `spatial_cortex`, `thalamus`) werden aus `kontinuum_core` importiert,
  die lokalen Kopien (~5 300 LOC) sind gelöscht. Verifikation per
  AST-Vergleich: 10 Module byte-/AST-identisch, 3 nur kosmetisch
  verschieden (tote Imports, Type-Hints, Inline-Variable).
  *Hinweis:* Die Begründungs-/Anzeigetexte von Amygdala (z. B.
  „ist sicherheitskritisch“) und Hypothalamus (Batterie/Solar-Labels)
  kommen jetzt aus dem Core und sind englisch.

### Added
- **Smoke-Test-CI (`.github/workflows/smoke.yaml`):** Installiert
  Home Assistant + `kontinuum-core` (vorerst via Git-URL, bis der
  PyPI-Release existiert), kompiliert alle Python-Dateien, importiert
  beide Integrationen und prüft `VERSION` ↔ `manifest.json`. Hätte den
  o. g. ImportError sofort gefangen – hassfest/HACS-Validate prüfen so
  etwas nicht.

### Known Issues
- **`kontinuum-core` ist nicht auf PyPI** (404), obwohl beide Manifeste
  `kontinuum-core>=0.1.1` verlangen → Neuinstallationen schlagen fehl,
  bis der Maintainer den Release taggt (Details in der ROADMAP-Blocker-Box).
- **`manifest.json`** pinnt `kontinuum-core>=0.1.1`. Die neuro-inspirierte
  Lern-Engine wird ab sofort aus dem PyPI-Paket nachgezogen statt
  vendored. Existierender HA-Code (Sensoren, Services, UI) bleibt
  unverändert.
- **`metaplasticity.py`** ist jetzt ein dünner Wrapper um
  `kontinuum_core.metaplasticity.MetaPlasticity`. Externe API unverändert:
  `MetaPlasticity(hass)`, `await async_load()`, `await async_start(...)`,
  `await async_stop()`, `await async_save()`.
- **`locus_coeruleus`** wird jetzt aus `kontinuum_core` importiert
  (Pro-lokale Kopie entfernt). Erster Schritt zur Reduktion der
  Code-Duplikation zwischen Pro und Core (Roadmap-Risiko: 18 Module
  doppelt). Andere Module folgen einzeln.
- **`nucleus_accumbens`, `entorhinal_cortex`, `reticular`** ebenfalls
  aus `kontinuum_core` importiert; lokale Pro-Kopien gelöscht.
  Migrations-Stand: **4/18** doppelte Module konsolidiert.

### Added
- **`ha_scheduler.py`**: `HAScheduler` – Adapter, der das HA-freie
  `kontinuum_core.Scheduler`-Protocol auf
  `homeassistant.helpers.event.async_track_time_interval` brückt. Sync-
  Callbacks laufen im Executor, blockieren also nicht den Event-Loop.
- README-Banner (DE + EN) mit Cross-Links auf `kontinuum-core` und
  `ha-kontinuum-lite`.
- ROADMAP-Dokument konsolidiert: Phase 1 abgeschlossen, Phase 2 in
  Arbeit, Phase 3 mit konkretem Lizenz-Stand.

## v0.22.2 – Recorder-Attribut-Limit (16 KB)

### Fix
- **`sensor.kontinuum_status`-Attribute überschritten die 16 KB-Grenze** des
  HA-Recorders – mit der Folge, dass der Recorder *alle* Attribute verwarf
  ("State attributes for sensor.kontinuum_status exceed maximum size of
  16384 bytes"). Dashboard funktionierte weiter (liest Live-State), aber
  Historie war leer.
- Lösung: `_unrecorded_attributes` am Status-, Cerebellum- und
  Basal-Ganglia-Sensor gesetzt. Große / häufig wechselnde Felder
  (`pending_confirms_list`, `top_chunks`, `top_rules`, `active_habits`,
  Aux-Module-Dicts) bleiben im Live-State fürs Dashboard, werden aber
  nicht mehr in die Recorder-DB geschrieben. Die kompakten Kern-Stats
  (Counter, Modi, Konfidenzen) bleiben in der DB und damit in Historie/
  Statistik-Graphen.

## v0.22.1 – Bugfixes (Expert-Review)

Mehrere Punkte aus einem externen Code-Review behoben:

### Fixes
- **Prefrontal: Decision ohne auflösbare Entity landet nicht mehr in der
  Confirm-Queue.** Wenn `thalamus.resolve_entities()` keinen Kandidaten
  liefert, wird die Entscheidung als `OBSERVE` markiert (inkl. expliziter
  Begründung "keine Entity auflösbar"). Vorher konnten Phantom-Confirms mit
  leerer `entity_id` entstehen, die nur per Service-Call-Fehler auffielen.
- **Cortex: `brain_review()` respektiert `sequential_mode`.** Bisher wurde
  immer `asyncio.gather` genutzt – auf Single-GPU-Ollama-Setups führte das
  zu VRAM-Spikes. Jetzt identisch zu `consult()`: sequentielle Dispatcher-
  Schleife mit `keep_alive=0` pro Agent.
- **Outcome-Check: domain-bewusste State-Normalisierung.** Climate-Aktionen
  wurden fälschlich als Fehlschlag gewertet, weil der Service `heat` setzt,
  der tatsächliche State aber `heating` zurückmeldet (HVACAction). Neuer
  Helper `_states_match()` kennt die Äquivalenzen für climate, cover,
  media_player und lock – damit kein fehlerhaftes negatives RPE mehr.

Keine Verhaltensänderung in den Happy-Path-Szenarien; ausschließlich Fixes
für falsch-negative Feedback-Signale und leere Confirms.

---

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
