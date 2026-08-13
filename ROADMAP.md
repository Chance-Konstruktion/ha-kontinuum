# KONTINUUM – Roadmap zur 3-Repo-Architektur

> **Status:** Phasen 0–2 abgeschlossen – 3-Repo-Split steht, Engine gehärtet,
> LLM-Schicht abgesichert, Release-Pipeline live.
> **Stand:** Juni 2026
> **Architektur:** Drei eigenständige Repositories

> ✅ **Release-Pipeline live:** `kontinuum-core` ist auf **PyPI** (neueste
> Version **0.6.0**; veröffentlichte Releases: 0.1.1 → 0.6.0) mit
> tag-getriggertem Publish-Workflow (PyPI Trusted Publishing, `skip-existing`).
> `ha-kontinuum` pinnt `kontinuum-core>=0.6.0`, `ha-kontinuum-lite` entsprechend.
> Der frühere Installations-Blocker (404) ist erledigt.
>
> **Inhaltlich erreicht:** vollständige **26-Modul**-Pipeline + Persistenz,
> robuster (median+MAD) Anomalie-Schwellwert, Reticular-Aufmerksamkeit &
> Sleep-Consolidation, LLM-Datenvertrag (`build_llm_context`/`normalize_proposal`)
> + Tag-1-Priors, abgesichertes Cortex-Safety-Gate, sowie eine erweiterte
> Areal-/Botenstoff-Schicht (Habenula, STN, SCN, Cortisol, Acetylcholin,
> Serotonin, BDNF, Interval Timing). Vollständige Referenz:
> [`kontinuum-core/docs/MODULES.md`](https://github.com/Chance-Konstruktion/kontinuum-core/blob/main/docs/MODULES.md).

---

## 1. Zielarchitektur

```
┌──────────────────────────────────────────────────────────┐
│  REPO 1: kontinuum-core                                  │
│  ───────────────────────────                             │
│  • Reines Python-Package (PyPI: kontinuum-core, 0.6.0)   │
│  • KEINE Home-Assistant-Abhängigkeit                     │
│  • Lizenz: AGPLv3 (+ kommerzielle Dual-Lizenz möglich)   │
│  • Enthält alle 26 Brain-Module + Engine + docs/         │
└──────────────────────────────────────────────────────────┘
         ▲                                  ▲
         │ pip-dep via manifest.json        │
         │                                  │
┌────────┼───────────────┐    ┌─────────┼──────────────┐
│  REPO 2: ha-kontinuum  │    │  REPO 3: ha-kontinuum-lite │
│  (Pro, 0.28.x)         │    │  (Headless)                │
│  ───────────────────   │    │  ────────────────────────  │
│  • Volle UI            │    │  • KEINE UI                │
│  • Eigene Pipeline,    │    │  • Delegiert vollständig   │
│    treibt Core-Module  │    │    an KontinuumEngine      │
│  • Sensoren + Dashboard│    │  • 3 Sensoren, 1 Service   │
│  • Cortex (LLM-Agents) │    │  • Domain: kontinuum_lite  │
│  • Domain: kontinuum   │    └────────────────────────────┘
└────────────────────────┘
```

**Begründung der Trennung:**
- **Saubere Installation:** Lite-Nutzer bekommen 0 Bytes vom Pro-Paket auf die Platte.
- **Schutz vor Kopie:** AGPLv3 auf Core zwingt kommerzielle Verwerter zum Dialog.
- **Plattform-Charakter:** Core wird zur Substrat-Schicht für spätere Domänen-Layer
  (`anomaly`, `control`, `forecast` – bewusst auf später vertagt).

---

## 2. Aktueller Stand (Juni 2026)

| Repo | Version | Status |
|---|---|---|
| `kontinuum-core` | **0.6.0** (PyPI) | ✅ 26 Module, Engine wired, `to_dict`/`from_dict`-Persistenz, `docs/` (Module + Pipeline), CI (pytest 3.9–3.12 + Replay-Benchmark-Gate, AUC ≈ 0.99) |
| `ha-kontinuum` (Pro) | **0.28.1** | ✅ treibt die Core-Module über eine eigene Pipeline; Cortex/LLM (inkl. Custom/OpenAI-kompatibel → OpenCLAW); `docs/SETTINGS.md` |
| `ha-kontinuum-lite` | – | ✅ delegiert vollständig an `KontinuumEngine` (erbt alle 26 Module automatisch) |

**HA-Abhängigkeiten** in ha-kontinuum (`from homeassistant ...`) – alle bewusst in der Pro-Integration:
`__init__.py` (Setup + Event-Pipeline), `sensor.py` / `binary_sensor.py` (UI), `config_flow.py` (UI),
`cortex.py` (LLM-Schicht), `metaplasticity.py` (dünner Wrapper), `ha_scheduler.py` (Scheduler-Adapter).

---

## 3. Modul-Zuordnung

### → kontinuum-core (Repo 1)

**Alle 26 Brain-Module** liegen in Core (HA-frei). Beide HA-Integrationen nutzen sie:
Lite delegiert vollständig an `KontinuumEngine`; Pro verdrahtet sie in seiner eigenen
Pipeline (siehe Hinweis unten).

- **Ursprüngliche 18 Module** (aus ha-kontinuum migriert, 18/18, Juni 2026): thalamus,
  hippocampus, predictive_processing, cerebellum, basal_ganglia, neurorhythms,
  sleep_consolidation, amygdala, anterior_cingulate, entorhinal_cortex, hypothalamus,
  insula, locus_coeruleus, nucleus_accumbens, reticular, spatial_cortex,
  prefrontal_cortex, metaplasticity (+ scheduler, types).
- **8 erweiterte Module** (direkt in Core entwickelt, 0.5.0/0.6.0): `habenula`
  (Anti-Reward), `subthalamic_nucleus` (Hold), `suprachiasmatic` (Tagesuhr),
  `serotonin`, `acetylcholine`, `cortisol`, `bdnf`, `interval_timing` (innere Stoppuhr).

**Klassenname-Aliase** (engine.py-Kompatibilität): `AnteriorCingulate = AnteriorCingulateCortex`,
`Reticular = ReticularFormation`, `Metaplasticity = MetaPlasticity`.

### → ha-kontinuum (Repo 2, Pro)

Volle UI + Core-Dependency. `__init__.py`, `sensor.py`, `binary_sensor.py`,
`config_flow.py`, `cortex.py`, `const.py`, `services.yaml`, `assets/`, `brand/`,
`translations/`, `docs/`.

> **Architektur-Hinweis / möglicher Refactor:** Die Pro-Integration verdrahtet die
> Core-Module in einer **eigenen** Event-Pipeline (sie nutzt nicht direkt
> `KontinuumEngine`). Folge: jedes neue Core-Modul muss in Pro **manuell** eingewoben
> werden (so geschehen für die 8 erweiterten Module). Ein künftiger Refactor könnte
> Pro – wie Lite – direkt an `KontinuumEngine` delegieren und diese Doppel-Verdrahtung
> abschaffen.

### → ha-kontinuum-lite (Repo 3)

Schlanke HA-Integration im eigenen Repo, delegiert vollständig an `KontinuumEngine`
(`__init__.py`, `sensor.py`, `config_flow.py`, `const.py`, `services.yaml`, `manifest.json`).

---

## 4. Core-API (tatsächlicher Vertrag)

`kontinuum-core` exportiert die Engine + Daten-Typen + den LLM-/Priors-Vertrag
(siehe `kontinuum_core/__init__.py`). Vollständige Referenz:
[`docs/PIPELINE.md`](https://github.com/Chance-Konstruktion/kontinuum-core/blob/main/docs/PIPELINE.md).

```python
class KontinuumEngine:
    def __init__(self, config=None, scheduler=None, storage_path=None) -> None: ...

    def register_entity(self, entity_id: str, **kwargs) -> None: ...
    def observe(self, event: dict) -> EngineSnapshot: ...   # ein Event → Snapshot
    def feedback(self, positive: bool) -> bool:             # host-getriebener Reward-Loop

    # Persistenz (SCHEMA_VERSION-geschützt, gedeckelte Maps)
    def to_dict(self) -> dict: ...
    def from_dict(self, data: dict) -> None: ...
```

`EngineSnapshot` liefert u. a. `surprise` (0–1), `anomaly`, `learning_state`,
`predictions` und ein reiches `extra`-Telemetrie-Dict (siehe Pipeline-Doku).
`Scheduler` ist ein **Protocol** (`schedule_interval(callback, seconds)`); jede
HA-Integration liefert einen eigenen Adapter (`ha_scheduler.py`), die Bibliothek
bleibt HA-frei.

---

## 5. Phasenplan

### Phase 0 – Vorarbeit ✅ Abgeschlossen
Lite als Prototyp, eigenes Repo, drei Lite-Entitäten + Service + Event.

### Phase 1 – Core-Refactor ✅ Abgeschlossen
Alle Brain-Module HA-frei nach `kontinuum-core` isoliert; Scheduler-Protocol; Typen;
`engine.py` auf echte Modul-Interfaces; beide HA-Integrationen delegieren an Core.
**Akzeptanz erfüllt:** `from kontinuum_core import KontinuumEngine` läuft ohne HA;
keine Datei in `src/kontinuum_core/` importiert `homeassistant`.

### Phase 2 – Repo-Split & Release ✅ Abgeschlossen
- [x] Drei Repos angelegt, READMEs mit Kreuzverweisen (DE+EN).
- [x] **PyPI-Release live** – Tag-getriggerter Publish-Workflow, Versionen bis 0.6.0.
- [x] HA-`manifest.json` pinnen `kontinuum-core` (Pro aktuell `>=0.6.0`).
- [x] CI: kontinuum-core (pytest 3.9–3.12 + Benchmark-Gate); ha-kontinuum
  (hassfest + HACS-validate + **Smoke-/Import-Check** mit echtem HA + Core);
  ha-kontinuum-lite (HACS-validate + hassfest).
- [x] Pro-auf-Core-Migration 18/18; lokale Duplikate entfernt.
- [x] Brain-Doku: `kontinuum-core/docs/` (MODULES + PIPELINE), `ha-kontinuum/docs/SETTINGS.md`.

> Hinweis: Die Smoke-CI in `ha-kontinuum` installiert Core **bewusst aus Git-`main`**
> (testet den unveröffentlichten Stand), obwohl PyPI live ist. Optional: für einen
> reinen „so installiert es der Nutzer"-Test auf das PyPI-Paket umstellen.

### Phase 3 – Lizenz & Schutz 🔄 Offen (Maintainer-Entscheidung)

| Repo | LICENSE |
|---|---|
| `kontinuum-core` | **AGPL-3.0** |
| `ha-kontinuum` | **MIT** |
| `ha-kontinuum-lite` | **MIT** |

→ **Inkonsistent.** MIT-Wrapper um eine AGPL-Bibliothek sind zulässig, aber das
Schutzziel (Schutz vor kommerzieller Übernahme) wird so nicht erreicht.

**Aufgaben (offen):**
- [ ] Entscheidung: alle drei Repos auf AGPLv3 angleichen? (Empfehlung: ja.)
- [ ] Falls ja: AGPLv3-Volltext in `ha-kontinuum` + `ha-kontinuum-lite`; Core-LICENSE auf Volltext.
- [ ] `NOTICE`-Datei (Copyright + Hinweis auf kommerzielle Dual-Lizenz).
- [ ] Optional: CLA für Contributor; Wort-/Bildmarke „KONTINUUM" (DPMA/EUIPO).

### Phase 4 – Domänen-Layer (bewusst zurückgestellt)
`kontinuum-anomaly` (z. B. KFZ-Predictive-Maintenance via OBD), `kontinuum-control`,
`kontinuum-forecast`.

---

## 6. Risiko-Register

| Risiko | Status | Gegenmaßnahme |
|---|---|---|
| ~~`kontinuum-core` nicht auf PyPI~~ | **erledigt** | Publish-Workflow live, Releases bis 0.6.0 |
| ~~`engine.py` nicht mit realen Interfaces kompatibel~~ | erledigt | seit 0.1.1 |
| ~~ha-kontinuum-lite unverbunden~~ | erledigt | delegiert an Core |
| ~~18 Brain-Module doppelt~~ | erledigt | 18/18 migriert |
| Pro hält eigene Pipeline (nicht `KontinuumEngine`) | mittel | jedes Core-Modul manuell einweben; optionaler Refactor auf Engine-Delegation |
| Breaking Changes bei Core-Updates | mittel | SemVer; Pre-1.0 Breaking erlaubt; Pro pinnt `>=0.6.0` |
| Lizenz-Inkonsistenz (AGPL vs. MIT) | offen | Phase 3 |

---

## 7. Offene Fragen / Entscheidungen an den Maintainer

1. **Lizenz:** Alle drei Repos auf **AGPLv3** angleichen? (Core ist AGPL, beide HA-Wrapper MIT.)
2. **Pro-Architektur:** Soll Pro langfristig direkt an `KontinuumEngine` delegieren
   (wie Lite) statt eine eigene Pipeline zu pflegen? Spart die Doppel-Verdrahtung
   bei jedem neuen Core-Modul.
3. **Smoke-CI:** Core-Install in `ha-kontinuum` von Git-`main` auf das PyPI-Paket
   umstellen (oder beides testen: main + letztes Release)?
4. **Domänen-Layer (Phase 4):** Wann starten – und welcher zuerst (anomaly/control/forecast)?

---

*Diese Roadmap ist ein lebendiges Dokument. Änderungen bitte als PR gegen diese
Datei einreichen, damit alle beteiligten Agents auf demselben Stand arbeiten.*
