# KONTINUUM – Roadmap zur 3-Repo-Architektur

> **Status:** Phase 1 abgeschlossen – Phase 2 in Arbeit  
> **Stand:** Mai 2026  
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
│  • Domain: kontinuum   │    │  • Brand-Icon (HACS-Pflicht)│
└────────────────────────┘    │  • Domain: kontinuum_lite  │
                              └────────────────────────────┘
```

**Begründung der Trennung:**
- **Saubere Installation:** Lite-Nutzer bekommen 0 Bytes vom Pro-Paket auf die Platte.
- **Schutz vor Kopie:** AGPLv3 auf Core zwingt kommerzielle Verwerter zum Dialog.
- **Plattform-Charakter:** Core wird zur Substrat-Schicht für spätere Domänen-Layer
  (`anomaly`, `control`, `forecast` – bewusst auf später vertagt).

---

## 2. Aktueller Stand (Mai 2026)

**Repos:**
| Repo | Status |
|---|---|
| `kontinuum-core` | ✅ v0.1.1 auf PyPI, alle 18 Module portiert, Engine wired |
| `ha-kontinuum` | ✅ Pro-Integration, `MetaPlasticity` delegiert an Core via `HAScheduler` |
| `ha-kontinuum-lite` | ✅ Engine delegiert vollständig an `KontinuumEngine` |

**HA-Abhängigkeiten** in ha-kontinuum (`from homeassistant ...`):
- `__init__.py` – Setup-Code, **bleibt** in Pro-Integration
- `sensor.py` – UI, **bleibt** in Pro-Integration
- `config_flow.py` – UI, **bleibt** in Pro-Integration
- `metaplasticity.py` – nur noch dünner Wrapper um `kontinuum_core.metaplasticity`
- `ha_scheduler.py` – Adapter für das Core-`Scheduler`-Protocol

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

### Phase 1 – Core-Refactor ✅ Abgeschlossen
**Ziel:** Alle Brain-Module sauber von HA isolieren, in `kontinuum-core` publizieren.

- [x] `kontinuum-core` Repository + PyPI-Link (v0.1.0, v0.1.1 released)
- [x] Verzeichnis `src/kontinuum_core/` angelegt
- [x] Scheduler-Protocol (`scheduler.py`) implementiert
- [x] Typen (`types.py`) definiert
- [x] 6 Basis-Module gemergt: hippocampus, cerebellum, basal_ganglia, neurorhythms, predictive_processing, sleep_consolidation
- [x] 9 Erweiterungs-Module gemergt: amygdala, anterior_cingulate, entorhinal_cortex, hypothalamus, insula, locus_coeruleus, nucleus_accumbens, reticular, spatial_cortex
- [x] `thalamus.py` (1062 LOC, Tokenizer) portiert
- [x] `prefrontal_cortex.py` portiert
- [x] `metaplasticity.py` HA-frei refaktoriert (Scheduler-Protocol)
- [x] `engine.py` `observe()`/`predict()` auf echte Modul-Interfaces umgestellt (kontinuum-core 0.1.1)
- [x] `KontinuumEngine.__init__(config, scheduler, storage_path)` entspricht dem Roadmap-Vertrag
- [x] `ha-kontinuum` `manifest.json` auf `requirements: ["kontinuum-core>=0.1.1"]`
- [x] `ha-kontinuum-lite` `manifest.json` auf `requirements: ["kontinuum-core>=0.1.1"]`
- [x] `ha-kontinuum-lite` `engine.py` delegiert an `KontinuumEngine`
- [x] `HAScheduler`-Adapter in `ha-kontinuum` (Pro)
- [x] `HAScheduler`-Adapter in `ha-kontinuum-lite`
- [x] Version `0.1.1` in `pyproject.toml` UND `__init__.py` synchronisiert

**Akzeptanzkriterien Phase 1:** ✅
- `python -c "from kontinuum_core import KontinuumEngine; print('OK')"` läuft **ohne installiertes HA**.
- Keine Datei in `src/kontinuum_core/` enthält `from homeassistant`.
- Beide HA-Integrationen funktionieren weiter wie zuvor.

### Phase 2 – Repo-Split 🔄 In Arbeit
**Ziel:** Drei eigenständige GitHub-Repos, sauberer Auslieferungsweg.

- [x] Maintainer hat `Chance-Konstruktion/kontinuum-core` angelegt
- [x] Maintainer hat `Chance-Konstruktion/ha-kontinuum-lite` angelegt
- [x] PyPI-Release `kontinuum-core 0.1.0`, `0.1.1` getaggt
- [x] Beide HA-`manifest.json` auf `requirements: ["kontinuum-core>=0.1.1"]`
- [x] `hacs.json` in `ha-kontinuum-lite` vorhanden
- [x] README in `kontinuum-core` verlinkt auf `ha-kontinuum` + `ha-kontinuum-lite`
- [x] README in `ha-kontinuum` (DE + EN) verlinkt auf `kontinuum-core` + `ha-kontinuum-lite`
- [x] README in `ha-kontinuum-lite` verlinkt auf `ha-kontinuum` + `kontinuum-core`
- [x] Brand-Icons in `ha-kontinuum-lite` (HACS-Validation-Pflicht; reusen Pro-Icons)
- [x] CI in `kontinuum-core` (pytest auf Python 3.9-3.12)
- [x] CI in `ha-kontinuum-lite` (HACS-validate + hassfest)
- [x] CHANGELOG.md in `ha-kontinuum-lite` angelegt
- [x] `kontinuum-core` Test-Suite (37 Tests: engine, thalamus,
  predictive_processing, hippocampus, cerebellum)
- [x] Pro-auf-Core-Migration: `locus_coeruleus`, `nucleus_accumbens`,
  `entorhinal_cortex`, `reticular` → kommen aus kontinuum-core,
  lokale Pro-Kopien entfernt (Stand: 4/18)
- [ ] Pro-auf-Core-Migration fortsetzen: restliche 14 doppelte Module
  einzeln migrieren (siehe Risiko-Register)
- [ ] HACS-Default-Repo-Antrag für `ha-kontinuum-lite` (falls Distribution über
  HACS-Default geplant; sonst custom-repo Anleitung)
- [ ] PyPI-Release `kontinuum-core 0.1.2` via GitHub-Tag (Tests + Engine-
  Vertrags-Parameter)

**Akzeptanzkriterien Phase 2:**
- Frischer HA-Container kann `ha-kontinuum-lite` über HACS installieren, Core wird automatisch via pip nachgezogen.
- `ha-kontinuum-lite` Installation legt **keine** Pro-Dateien auf der Platte ab.

### Phase 3 – Lizenz & Schutz

**Aktueller Stand (Mai 2026):**
| Repo | LICENSE-Datei | pyproject/manifest |
|---|---|---|
| `kontinuum-core` | AGPL-3.0 (Stub, verweist auf gnu.org) | `license = “AGPL-3.0”` in pyproject.toml |
| `ha-kontinuum` | MIT | — |
| `ha-kontinuum-lite` | MIT | — |

→ **Inkonsistent.** Bei einer AGPL-Bibliothek (`kontinuum-core`) sind MIT-Wrapper
zulässig (MIT ist permissiv), aber das Schutzziel der Roadmap (Schutz vor
kommerzieller Übernahme) wird so nicht erreicht: ein Forker kann beide HA-Wrapper
unter MIT weiterverwerten.

**Aufgaben:**
- [ ] Maintainer-Entscheidung: alle drei Repos auf AGPLv3 angleichen?
  (Empfehlung: ja, sonst hat Phase 3 keinen Effekt.)
- [ ] Falls ja: `LICENSE` in `ha-kontinuum` + `ha-kontinuum-lite` durch
  vollständigen AGPLv3-Text ersetzen (nicht nur Stub-Verweis wie in Core).
- [ ] `LICENSE` in `kontinuum-core` ebenfalls auf Volltext bringen
  (PyPI sieht ungern Stub-Lizenzen).
- [ ] `NOTICE`-Datei mit Copyright + Hinweis auf kommerzielle Dual-Lizenz
- [ ] Optional: CLA für Contributor (ermöglicht spätere Dual-Lizenz)
- [ ] Optional: Wort-/Bildmarke „KONTINUUM” beim DPMA/EUIPO anmelden

### Phase 4 – Domänen-Layer (bewusst zurückgestellt)

Erst nach Phase 2/3 anfassen:
- `kontinuum-anomaly` (z.B. KFZ-Predictive-Maintenance via OBD)
- `kontinuum-control`
- `kontinuum-forecast`

---

## 6. Was ein Coding-Agent jetzt tun kann

**Direkt machbar ohne weitere Rückfrage:**
1. READMEs in `kontinuum-core` und `ha-kontinuum-lite` mit Kreuzverweisen auf die anderen beiden Repos versehen (Phase 2).
2. `ha-kontinuum`-Pro schrittweise auf `kontinuum-core` umstellen: lokale Brain-Module gegen den Core austauschen, sobald die Pro-spezifischen Aufrufe gegen das Core-Interface validiert sind (vermeidet Code-Duplikation, derzeit liegen 18 Module doppelt vor).
3. Schmaler Integrations-/Smoke-Test (`tests/` in `kontinuum-core`) der die `observe()`-Pipeline und das Scheduler-Wiring der `Metaplasticity` abdeckt.

**Erfordert Maintainer-Entscheidung vorab:**
- Version `0.1.2` bumpen + PyPI-Release via GitHub-Tag, sobald der nächste Sammelfix (z. B. Kreuzverweise, Tests) gemergt ist.
- Lizenz-Wechsel auf AGPLv3 in `ha-kontinuum`-Pro (Core ist bereits AGPLv3, Lite hat eigene LICENSE-Datei – Konsistenz prüfen).
- Pro-Integration: Entscheidung, ob lokale Module entfernt werden oder als Pro-Erweiterung neben Core bestehen bleiben.

**Tabu für Agents (manuell durch Maintainer):**
- Neue Repos auf GitHub anlegen.
- PyPI-Releases manuell pushen (läuft über GitHub-Tag-Trigger).
- Lizenz-Marken-Anmeldungen.

---

## 7. Risiko-Register

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| Core-API zu früh stabilisiert | mittel | Phase 1 abgeschlossen, aber Pre-1.0: Breaking Changes erlaubt |
| ~~`engine.py` Skeleton nicht mit realen Interfaces kompatibel~~ | erledigt | Behoben in `kontinuum-core 0.1.1` |
| ~~ha-kontinuum-lite bleibt unverbunden~~ | erledigt | Lite delegiert vollständig an Core |
| **18 Brain-Module doppelt** (Pro + Core) | hoch | Pro auf Core umstellen, lokale Module entfernen (4/18 erledigt: locus_coeruleus, nucleus_accumbens, entorhinal_cortex, reticular) |
| Doppelte Maintenance-Last | hoch | CI-Templates zwischen Repos teilen, gemeinsame Tests in Core |
| Breaking Changes bei `kontinuum-core` Updates | mittel | SemVer strikt, `requirements: ["kontinuum-core>=0.1,<0.2"]` |

---

## 8. Offene Fragen an den Maintainer

1. ~~Soll `engine.py` sofort mit echten Modul-Interfaces verknüpft werden?~~
   Erledigt in `kontinuum-core 0.1.1`.
2. Welche Lizenz hat `ha-kontinuum` aktuell, und ist ein Wechsel auf **AGPLv3**
   gewünscht, um die drei Repos konsistent zu halten? (Core ist bereits AGPLv3.)
3. Soll der nächste Sammel-Release `0.1.2` heißen oder direkt `0.2.0`?
   Empfehlung `0.1.2`, da die Änderung am `__init__`-Vertrag rückwärtskompatibel ist
   (alle Parameter sind keyword + default).
4. ~~Ist der `HAScheduler`-Adapter als Teil von ha-kontinuum oder als separates
   Paket gewünscht?~~ Entschieden: pro HA-Integration eine eigene Datei
   (`ha_scheduler.py`). Beide Repos haben einen Adapter, die Bibliothek bleibt
   HA-frei.
5. Pro-Integration: lokale Brain-Module entfernen und auf Core delegieren, oder
   als Pro-Erweiterung behalten und nur einzelne Module migrieren? (Doppel-
   Maintenance vs. Code-Eigenständigkeit.)

---

*Diese Roadmap ist ein lebendiges Dokument. Änderungen bitte als PR gegen
dies Datei einreichen, damit alle beteiligten Agents (Codex, Claude etc.) auf
demselben Stand arbeiten.*
