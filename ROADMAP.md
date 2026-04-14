# KONTINUUM – Roadmap zur 3-Repo-Architektur

> **Status:** Planung / Bereit zur Umsetzung
> **Branch:** `claude/kontinuum-lite-version-GMgIL`
> **Zielarchitektur:** drei eigenständige Repositories mit klarer Verantwortung

---

## 1. Zielarchitektur

```
┌──────────────────────────────────────────────────────────┐
│  REPO 1: kontinuum-core                                  │
│  ─────────────────────────                               │
│  • Reines Python-Package (PyPI: kontinuum-core)          │
│  • KEINE Home-Assistant-Abhängigkeit                     │
│  • Lizenz: AGPLv3 (+ kommerzielle Dual-Lizenz möglich)   │
│  • Enthält die Lern-Substrat-Module                      │
└──────────────────────────────────────────────────────────┘
         ▲                                  ▲
         │ pip-dep via manifest.json        │
         │                                  │
┌────────┴───────────────┐    ┌─────────────┴──────────────┐
│  REPO 2: ha-kontinuum  │    │  REPO 3: ha-kontinuum-lite │
│  (Pro)                 │    │  (Headless)                │
│  ───────────────────   │    │  ────────────────────────  │
│  • Volle UI            │    │  • KEINE UI                │
│  • Alle Brain-Module   │    │  • Nur Core + Wrapper      │
│  • Sensoren + Dashboard│    │  • 3 Sensoren, 1 Service,  │
│  • Brand-Assets        │    │    1 Event                 │
│  • Domain: kontinuum   │    │  • Domain: kontinuum_lite  │
└────────────────────────┘    └────────────────────────────┘
```

**Begründung der Trennung:**
- **Saubere Installation:** Lite-Nutzer bekommen 0 Bytes vom Pro-Paket auf die Platte.
- **Schutz vor Kopie:** AGPLv3 auf Core zwingt kommerzielle Verwerter zum Dialog.
- **Plattform-Charakter:** Core wird zur Substrat-Schicht für spätere Domänen-Layer
  (`anomaly`, `control`, `forecast` – bewusst auf später vertagt).

---

## 2. Bestandsaufnahme (Stand Branch)

**Code-Volumen:** 9.942 LOC in 23 Python-Modulen.

**HA-Abhängigkeiten** (`from homeassistant ...`):
- `__init__.py` – 19 Imports (HA-Setup, **bleibt** in Pro-Integration)
- `sensor.py` – 5 Imports (UI, **bleibt** in Pro-Integration)
- `config_flow.py` – 3 Imports (UI, **bleibt** in Pro-Integration)
- `metaplasticity.py` – **nur 2 Imports** (`HomeAssistant`, `async_track_time_interval`) → trivial refaktorierbar

**Konsequenz:** 19 von 23 Modulen sind bereits HA-frei. Die Core-Extraktion ist
ein **leichter Refactor**, kein Großprojekt.

---

## 3. Modul-Zuordnung

### → kontinuum-core (Repo 1)

| Modul | LOC | Status |
|---|---|---|
| `hippocampus.py` | 464 | ✅ HA-frei |
| `predictive_processing.py` | 193 | ✅ HA-frei |
| `cerebellum.py` | 420 | ✅ HA-frei |
| `basal_ganglia.py` | 311 | ✅ HA-frei |
| `neurorhythms.py` | 280 | ✅ HA-frei |
| `sleep_consolidation.py` | 276 | ✅ HA-frei |
| `metaplasticity.py` | 200 | ⚠️ 2 HA-Imports refaktorieren |
| `thalamus.py` | 1062 | ✅ HA-frei (Input-Tokenizer) |
| **Summe** | **~3.200 LOC** | |

### → ha-kontinuum (Repo 2, Pro)

Alle bisherigen Module **plus** Core-Dependency. Kein Code-Verlust.
- `__init__.py`, `sensor.py`, `config_flow.py`, `const.py`, `services.yaml`
- Brain-Erweiterungen: `amygdala`, `anterior_cingulate`, `insula`, `hypothalamus`,
  `locus_coeruleus`, `nucleus_accumbens`, `prefrontal_cortex`, `spatial_cortex`,
  `reticular`, `entorhinal_cortex`, `cortex`
- `assets/`, `brand/`, `translations/`, `icons/`

### → ha-kontinuum-lite (Repo 3)

Komplett neue, schlanke HA-Integration:
- `__init__.py` (~200 LOC, nur Setup + Core-Wiring)
- `sensor.py` (~150 LOC, exakt 3 Sensoren)
- `config_flow.py` (~100 LOC, minimaler Setup)
- `const.py`, `services.yaml`, `manifest.json`
- **Kein** Brand, **keine** Assets, **keine** Brain-Visualisierung

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
    def consolidate(self) -> None: ...     # Sleep-Consolidation-Tick

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

### Phase 0 – Vorarbeit (dieser Branch)
**Ziel:** Lite als Prototyp im Mono-Repo lauffähig, ohne Core-Repo zu splitten.

- [ ] `custom_components/kontinuum_lite/` anlegen
  - [ ] `manifest.json` (Domain `kontinuum_lite`, Version `0.1.0`)
  - [ ] `__init__.py` mit minimalem `async_setup_entry`
  - [ ] `config_flow.py` (nur Name + Startwerte)
  - [ ] `sensor.py` mit drei Entitys:
    - `sensor.kontinuum_lite_surprise` (numerisch, 0..1)
    - `binary_sensor.kontinuum_lite_anomaly` (on/off)
    - `sensor.kontinuum_lite_learning_state` (z. B. `cold_start`/`learning`/`stable`)
  - [ ] `services.yaml` mit `kontinuum_lite.evaluate`
  - [ ] Event `kontinuum_lite_anomaly` definieren
- [ ] Imports zunächst aus `custom_components.kontinuum.<module>` (Re-Export)
- [ ] Smoke-Test: HA startet, Lite legt Entitys an, `evaluate` läuft durch.

**Akzeptanzkriterien Phase 0:**
- HA lädt beide Integrationen parallel ohne Konflikt.
- Lite hat **keine** UI-Sensoren der Pro-Version sichtbar.
- `homeassistant.log` zeigt < 5 Zeilen pro Stunde von Lite.

### Phase 1 – Core-Refactor im Mono-Repo
**Ziel:** Core-Module sauber von HA isolieren, weiterhin im selben Repo.

- [ ] Verzeichnis `packages/kontinuum_core/` anlegen
- [ ] Core-Module dorthin verschieben (siehe Tabelle in §3)
- [ ] `metaplasticity.py`: HA-Imports durch `Scheduler`-Protocol ersetzen
- [ ] `kontinuum_core/__init__.py`: Public-API exportieren (siehe §4)
- [ ] `pyproject.toml` für `kontinuum-core` (Build-Konfiguration, Version `0.1.0`)
- [ ] Pro-Integration (`custom_components/kontinuum/`) auf Core-Imports umstellen
- [ ] Lite-Integration auf Core-Imports umstellen
- [ ] Adapter `HAScheduler` in beiden HA-Integrationen anlegen

**Akzeptanzkriterien Phase 1:**
- `python -c "from kontinuum_core import KontinuumEngine; KontinuumEngine().observe(...)"` läuft **ohne installiertes HA**.
- Beide HA-Integrationen funktionieren weiter wie zuvor.
- Keine Datei in `packages/kontinuum_core/` enthält `from homeassistant`.

### Phase 2 – Repo-Split (manueller Schritt durch Maintainer)
**Ziel:** Drei eigenständige GitHub-Repos.

> Diese Phase erfordert manuelle GitHub-Aktionen (neue Repos anlegen).
> Codex/Agent kann die Inhalte vorbereiten, das Anlegen der Repos macht der Maintainer.

- [ ] Maintainer legt an: `Chance-Konstruktion/kontinuum-core`
- [ ] Maintainer legt an: `Chance-Konstruktion/ha-kontinuum-lite`
- [ ] Inhalt von `packages/kontinuum_core/` → neues Core-Repo (mit Git-History via `git subtree split`)
- [ ] Inhalt von `custom_components/kontinuum_lite/` → neues Lite-Repo
- [ ] Beide HA-`manifest.json` auf `requirements: ["kontinuum-core>=0.1.0"]` setzen
- [ ] PyPI-Release `kontinuum-core 0.1.0`
- [ ] HACS-Eintrag für `ha-kontinuum-lite`
- [ ] README in allen drei Repos kreuzverlinken

**Akzeptanzkriterien Phase 2:**
- Frischer HA-Container kann `ha-kontinuum-lite` über HACS installieren, Core wird automatisch via pip nachgezogen.
- `ha-kontinuum-lite` Installation legt **keine** Pro-Dateien auf der Platte ab.

### Phase 3 – Lizenz & Schutz
- [ ] `LICENSE` in allen drei Repos auf AGPLv3 setzen
- [ ] `NOTICE`-Datei mit Copyright + Hinweis auf kommerzielle Lizenz
- [ ] Optional: CLA für Contributor (ermöglicht spätere Dual-Lizenz)
- [ ] Optional: Wort-/Bildmarke „KONTINUUM" beim DPMA/EUIPO anmelden

### Phase 4 – Erst danach: Domänen-Layer
**Bewusst zurückgestellt.** Erst nach Phase 2/3 anfassen.

- `kontinuum-anomaly` (z. B. für KFZ-Predictive-Maintenance via OBD)
- `kontinuum-control`
- `kontinuum-forecast`

---

## 6. Was ein Coding-Agent (Codex etc.) sofort tun kann

**Direkt machbar ohne weitere Rückfrage:**
1. **Phase 0 komplett** – Lite-Skelett auf diesem Branch anlegen (siehe Checklist §5).
2. **Phase 1 vorbereiten** – Verzeichnis `packages/kontinuum_core/` anlegen, Core-Module hinüberkopieren (nicht verschieben!), Imports in Pro-Integration noch nicht ändern. So bleibt alles lauffähig, der Refactor lässt sich ohne Druck reviewen.

**Erfordert Maintainer-Entscheidung vorab:**
- Verschieben (statt Kopieren) der Core-Module → bricht Pro-Integration kurz.
- Anlegen neuer GitHub-Repos.
- PyPI-Account/Token für `kontinuum-core`.
- Lizenz-Wechsel auf AGPLv3 (falls bisher andere Lizenz).

**Tabu für Agents (manuell durch Maintainer):**
- Neue Repos auf GitHub anlegen.
- PyPI-Releases pushen.
- Lizenz-Marken-Anmeldungen.

---

## 7. Risiko-Register

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| Core-API zu früh stabilisiert | mittel | Phase 1 im Mono-Repo halten, bis 2-3 echte Konsumenten existieren |
| Doppelte Maintenance-Last | hoch | Mono-Repo-Phase nicht überspringen, CI-Templates wiederverwenden |
| Verwirrung Pro vs. Lite bei Nutzern | mittel | Klare README, FAQ, Vergleichstabelle |
| HACS-Konflikt (zwei Integrationen, ein Repo) | niedrig | In Phase 2 separates Repo erzwingt Trennung |
| Breaking Changes bei `kontinuum-core` Updates | mittel | SemVer strikt, `requirements: ["kontinuum-core>=0.1,<0.2"]` |

---

## 8. Offene Fragen an den Maintainer

1. Soll der Branch `claude/kontinuum-lite-version-GMgIL` nur **Phase 0** umfassen
   und Phase 1 in einem separaten PR landen? (Empfehlung: ja.)
2. Welche Lizenz hat das Repo aktuell, und ist ein Wechsel auf **AGPLv3** in
   Ordnung? (Schutz vor kommerzieller Übernahme.)
3. Soll `kontinuum-core` **synchron** (klassisch) oder **async-first** sein?
   (Empfehlung: synchron im Kern, async-Adapter im HA-Layer – maximale
   Wiederverwendbarkeit außerhalb von HA.)
4. Ziel-Python-Version für `kontinuum-core`? (Empfehlung: `>=3.11` parallel zu HA.)

---

*Diese Roadmap ist ein lebendiges Dokument. Änderungen bitte als PR gegen
diese Datei einreichen, damit alle beteiligten Agents (Codex, Claude etc.) auf
demselben Stand arbeiten.*
