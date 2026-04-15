# KONTINUUM – Roadmap zur 3-Repo-Architektur

> **Status:** Phase 1 aktiv – Core-Module-Port läuft  
> **Stand:** April 2026  
> **Architektur:** Drei eigenständige Repositories (durch Maintainer angelegt)

---

## 1. Zielarchitektur

```
┌──────────────────────────────────────────────────────────┐
│  REPO 1: kontinuum-core                                  │
│  ───────────────────────────   │
│  • Reines Python-Package (PyPI: kontinuum-core)          │
│  • KEINE Home-Assistant-Abhängigkeit                     │
│  • Lizenz: AGPLv3 (+ kommerzielle Dual-Lizenz möglich)   │
│  • Enthält alle 18 Brain-Module + Engine                  │
└──────────────────────────────────────────────────────────┘
         ▲                                  ▲
         │ pip-dep via manifest.json        │
         │                                  │
┌────────┼───────────────┐    ┌─────────┼──────────────┐
│  REPO 2: ha-kontinuum  │    │  REPO 3: ha-kontinuum-lite │
│  (Pro)                 │    │  (Headless)                │
│  ───────────────────   │    │  ────────────────────────  │
│  • Volle UI            │    │  • KEINE UI                │
│  • Alle Brain-Module   │    │  • Nur Core + Wrapper      │
│  • Sensoren + Dashboard│    │  • 3 Sensoren, 1 Service,  │
│  • Brand-Assets        │    │    1 Event                 │
│  • Domain: kontinuum   │    │  • Domain: kontinuum_lite  │
└────────────────────────┘    └──────────────────────────┘
```

**Begründung der Trennung:**
- **Saubere Installation:** Lite-Nutzer bekommen 0 Bytes vom Pro-Paket auf die Platte.
- **Schutz vor Kopie:** AGPLv3 auf Core zwingt kommerzielle Verwerter zum Dialog.
- **Plattform-Charakter:** Core wird zur Substrat-Schicht für spätere Domänen-Layer
  (`anomaly`, `control`, `forecast` – bewusst auf später vertagt).

---

## 2. Aktueller Stand (April 2026)

**Repos:**
| Repo | Status |
|---|---|
| `kontinuum-core` | ✅ Existiert, v0.1.0 auf PyPI, Phase-1-Port aktiv |
| `ha-kontinuum` | ✅ Pro-Integration, aktiv gewartet |
| `ha-kontinuum-lite` | ⚠️ Repo existiert, aber Engine noch nicht mit Core verknüpft |

**HA-Abhängigkeiten** in ha-kontinuum (`from homeassistant ...`):
- `__init__.py` – 19 Imports (HA-Setup, **bleibt** in Pro-Integration)
- `sensor.py` – 5 Imports (UI, **bleibt** in Pro-Integration)
- `config_flow.py` – 3 Imports (UI, **bleibt** in Pro-Integration)
- `metaplasticity.py` – 2 Imports → **refaktoriert** in Phase 1 (Scheduler-Protocol)

---

## 3. Modul-Zuordnung

### → kontinuum-core (Repo 1)

Entscheidung: **alle 18 Brain-Module** gehen in Core (nicht nur die ursprünglich geplanten 8).
Das macht Core zum vollständigen Substrat – beide HA-Integrationen delegieren vollständig.

| Modul | LOC (ha-kont.) | Status in kontinuum-core |
|---|---|---|
| `hippocampus.py` | 464 | ✅ Gemergt (PR #2) |
| `predictive_processing.py` | 193 | ✅ Gemergt (PR #2) |
| `cerebellum.py` | 420 | ✅ Gemergt (PR #2) |
| `basal_ganglia.py` | 311 | ✅ Gemergt (PR #2) |
| `neurorhythms.py` | 280 | ✅ Gemergt (PR #2) |
| `sleep_consolidation.py` | 276 | ✅ Gemergt (PR #2) |
| `scheduler.py` | – | ✅ Gemergt (PR #2, neu) |
| `types.py` | – | ✅ Gemergt (PR #2, neu) |
| `amygdala.py` | ~200 | ✅ Branch `review-project-status` |
| `anterior_cingulate.py` | ~250 | ✅ Branch (+ `AnteriorCingulate`-Alias) |
| `entorhinal_cortex.py` | ~80 | ✅ Branch |
| `hypothalamus.py` | ~400 | ✅ Branch |
| `insula.py` | ~280 | ✅ Branch |
| `locus_coeruleus.py` | ~50 | ✅ Branch |
| `nucleus_accumbens.py` | ~50 | ✅ Branch |
| `reticular.py` | ~120 | ✅ Branch (+ `Reticular`-Alias) |
| `spatial_cortex.py` | ~360 | ✅ Branch |
| `thalamus.py` | 1062 | ✅ Branch (dieser PR) |
| `prefrontal_cortex.py` | ~750 | ✅ Branch (dieser PR) |
| `metaplasticity.py` | 200 | ✅ Branch, HA-refaktoriert (dieser PR) |

**Klassenname-Aliase** (engine.py-Kompatibilität):
- `AnteriorCingulate = AnteriorCingulateCortex`
- `Reticular = ReticularFormation`
- `Metaplasticity = MetaPlasticity`

### → ha-kontinuum (Repo 2, Pro)

Alle bisherigen Module **plus** Core-Dependency. Kein Code-Verlust.
- `__init__.py`, `sensor.py`, `config_flow.py`, `const.py`, `services.yaml`
- Brain-Module bleiben für HA-spezifische Erweiterungen (UI, Events, Services)
- `assets/`, `brand/`, `translations/`, `icons/`

**TODO:** `manifest.json` auf `requirements: ["kontinuum-core>=0.1.0"]` umstellen.

### → ha-kontinuum-lite (Repo 3)

Schlanke HA-Integration, Phase-0-Prototyp vorhanden:
- `__init__.py`, `sensor.py`, `config_flow.py`, `const.py`, `services.yaml`, `manifest.json`

**TODO:** `engine.py` auf `kontinuum_core.KontinuumEngine` umstellen (Phase-1-TODO-Kommentar vorhanden).

---

## 4. Core-API (verbindlicher Vertrag)

`kontinuum-core` exportiert genau eine öffentliche Klasse + Daten-Typen:

```python
# kontinuum_core/__init__.py
from kontinuum_core.engine import KontinuumEngine
from kontinuum_core.types import Observation, Prediction, MemoryState

__all__ = ["KontinuumEngine", "Observation", "Prediction", "MemoryState"]
```

```python
# Minimalvertrag der Engine
class KontinuumEngine:
    def __init__(self, config: dict | None = None,
                 scheduler: Scheduler | None = None) -> None: ...

    # Datenfluss
    def observe(self, obs: Observation) -> None: ...
    def predict(self) -> Prediction: ...
    def consolidate(self) -> None:     # Sleep-Consolidation-Tick

    # Persistenz
    def to_dict(self) -> MemoryState: ...
    def load_dict(self, state: MemoryState) -> None: ...

    # Beobachtbarkeit
    @property
    def surprise(self) -> float: ...
    @property
    def learning_rate(self) -> float: ...
```

`Scheduler` ist ein **Protocol** mit einer Methode
`schedule_interval(callback, seconds)`. HA liefert einen Adapter, der
`async_track_time_interval` einkapselt → so verschwindet die HA-Dependency
aus `metaplasticity.py`.

---

## 5. Phasenplan

### Phase 0 – Vorarbeit ✅ Abgeschlossen
**Ziel:** Lite als Prototyp in eigenem Repo, ohne Core-Repo zu splitten.

- [x] `ha-kontinuum-lite` Repository angelegt (Maintainer)
- [x] `manifest.json` (Domain `kontinuum_lite`)
- [x] `__init__.py` mit minimalem `async_setup_entry`
- [x] `config_flow.py`
- [x] `sensor.py` mit drei Entitys:
  - `sensor.kontinuum_lite_surprise`
  - `binary_sensor.kontinuum_lite_anomaly`
  - `sensor.kontinuum_lite_learning_state`
- [x] `services.yaml` mit `kontinuum_lite.evaluate`
- [x] Event `kontinuum_lite_anomaly` definiert

### Phase 1 – Core-Refactor 🔄 Aktiv
**Ziel:** Alle Brain-Module sauber von HA isolieren, in `kontinuum-core` publizieren.

- [x] `kontinuum-core` Repository + PyPI-Link (Maintainer, v0.1.0 released)
- [x] Verzeichnis `src/kontinuum_core/` angelegt
- [x] Scheduler-Protocol (`scheduler.py`) implementiert
- [x] Typen (`types.py`) definiert
- [x] 6 Basis-Module gemergt: hippocampus, cerebellum, basal_ganglia, neurorhythms, predictive_processing, sleep_consolidation (PR #2)
- [x] 9 Erweiterungs-Module gemergt: amygdala, anterior_cingulate, entorhinal_cortex, hypothalamus, insula, locus_coeruleus, nucleus_accumbens, reticular, spatial_cortex
- [x] `thalamus.py` (1062 LOC, Tokenizer) portiert – dieser PR
- [x] `prefrontal_cortex.py` portiert – dieser PR
- [x] `metaplasticity.py` HA-frei refaktoriert (Scheduler-Protocol) – dieser PR
- [ ] `engine.py` `observe()`/`predict()` auf echte Modul-Interfaces umstellen (derzeit Skeleton mit `.update()`-Aufrufen)
- [ ] `ha-kontinuum` `manifest.json` auf `requirements: ["kontinuum-core>=0.1.0"]` setzen
- [ ] `ha-kontinuum-lite` `engine.py` auf `KontinuumEngine` delegieren
- [ ] `HAScheduler`-Adapter in beiden HA-Integrationen anlegen
- [ ] Version auf `0.1.1` bumpen + PyPI-Release via GitHub-Tag

**Akzeptanzkriterien Phase 1:**
- `python -c "from kontinuum_core import KontinuumEngine; print('OK')"` läuft **ohne installiertes HA**.
- Keine Datei in `src/kontinuum_core/` enthält `from homeassistant`.
- Beide HA-Integrationen funktionieren weiter wie zuvor.

### Phase 2 – Repo-Split ✅ Teilweise abgeschlossen
**Ziel:** Drei eigenständige GitHub-Repos.

- [x] Maintainer hat `Chance-Konstruktion/kontinuum-core` angelegt
- [x] Maintainer hat `Chance-Konstruktion/ha-kontinuum-lite` angelegt
- [x] PyPI-Release `kontinuum-core 0.1.0`
- [ ] Beide HA-`manifest.json` auf `requirements: ["kontinuum-core>=0.1.0"]` setzen
- [ ] HACS-Eintrag für `ha-kontinuum-lite` (falls noch nicht vorhanden)
- [ ] README in allen drei Repos kreuzverlinken

**Akzeptanzkriterien Phase 2:**
- Frischer HA-Container kann `ha-kontinuum-lite` über HACS installieren, Core wird automatisch via pip nachgezogen.
- `ha-kontinuum-lite` Installation legt **keine** Pro-Dateien auf der Platte ab.

### Phase 3 – Lizenz & Schutz
- [ ] `LICENSE` in allen drei Repos auf AGPLv3 setzen
- [ ] `NOTICE`-Datei mit Copyright + Hinweis auf kommerzielle Lizenz
- [ ] Optional: CLA für Contributor (ermöglicht spätere Dual-Lizenz)
- [ ] Optional: Wort-/Bildmarke „KONTINUUM“ beim DPMA/EUIPO anmelden

### Phase 4 – Domänen-Layer (bewusst zurückgestellt)

Erst nach Phase 2/3 anfassen:
- `kontinuum-anomaly` (z.B. KFZ-Predictive-Maintenance via OBD)
- `kontinuum-control`
- `kontinuum-forecast`

---

## 6. Was ein Coding-Agent jetzt tun kann

**Direkt machbar ohne weitere Rückfrage:**
1. `engine.py` in kontinuum-core: `observe()`/`predict()` auf echte Modul-Interfaces umstellen.
2. `ha-kontinuum-lite/custom_components/kontinuum_lite/engine.py`: Phase-1-TODO umsetzen – `KontinuumEngine` aus kontinuum-core importieren und delegieren.
3. `manifest.json` beider HA-Integrationen: `requirements: ["kontinuum-core>=0.1.0"]` hinzufügen.
4. `HAScheduler`-Adapter schreiben: kapselt `async_track_time_interval` für das Scheduler-Protocol.

**Erfordert Maintainer-Entscheidung vorab:**
- Version auf `0.1.1` bumpen und PyPI-Release via GitHub-Tag auslösen.
- Lizenz-Wechsel auf AGPLv3 (falls bisher andere Lizenz).

**Tabu für Agents (manuell durch Maintainer):**
- Neue Repos auf GitHub anlegen.
- PyPI-Releases manuell pushen (läuft über GitHub-Tag-Trigger).
- Lizenz-Marken-Anmeldungen.

---

## 7. Risiko-Register

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| Core-API zu früh stabilisiert | mittel | Phase 1 vollständig abschließen bevor erste externe Konsumenten |
| `engine.py` Skeleton nicht mit realen Interfaces kompatibel | hoch | engine.py-Refactor als nächsten Schritt priorisieren |
| ha-kontinuum-lite bleibt unverbunden | mittel | Phase-1-TODO in lite/engine.py hat höchste Priorität |
| Doppelte Maintenance-Last | hoch | CI-Templates zwischen Repos teilen |
| Breaking Changes bei `kontinuum-core` Updates | mittel | SemVer strikt, `requirements: ["kontinuum-core>=0.1,<0.2"]` |

---

## 8. Offene Fragen an den Maintainer

1. Soll `engine.py` sofort mit echten Modul-Interfaces verknüpft werden, oder erst
   nach dem Lite-Wiring? (Empfehlung: Lite-Wiring zuerst – gibt ein konkretes Ziel vor.)
2. Welche Lizenz hat das Repo aktuell, und ist ein Wechsel auf **AGPLv3** in
   Ordnung? (Schutz vor kommerzieller Übernahme.)
3. Soll Version `0.1.1` via GitHub-Tag released werden, sobald Phase-1-PR gemergt ist?
   (Empfehlung: ja, Changelogs/Release Notes vorbereiten.)
4. Ist der `HAScheduler`-Adapter als Teil von ha-kontinuum oder als separates
   Paket (`kontinuum-ha-scheduler`) gewünscht? (Empfehlung: direkt in ha-kontinuum.)

---

*Diese Roadmap ist ein lebendiges Dokument. Änderungen bitte als PR gegen
dies Datei einreichen, damit alle beteiligten Agents (Codex, Claude etc.) auf
demselben Stand arbeiten.*
