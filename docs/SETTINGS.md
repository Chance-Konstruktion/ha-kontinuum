# KONTINUUM — Einstellungen & Konfiguration

Alle Optionen der Integration, was sie bewirken und empfohlene Werte.
Erreichbar über **Einstellungen → Geräte & Dienste → KONTINUUM → Konfigurieren**.

Die Gehirn-Module selbst sind in der Engine `kontinuum-core` dokumentiert:
[MODULES.md](https://github.com/Chance-Konstruktion/kontinuum-core/blob/main/docs/MODULES.md) ·
[PIPELINE.md](https://github.com/Chance-Konstruktion/kontinuum-core/blob/main/docs/PIPELINE.md).

---

## 1. Persönlichkeit (Preset)

Bestimmt, wie schnell/mutig gelernt und gehandelt wird. Jederzeit änderbar.

| Preset | Lerngeschwindigkeit | Erste Regeln nach | Fehlertoleranz |
|--------|--------------------|--------------------|----------------|
| **Mutig** | schnell | ~1 Tag | hoch (lernt aus Fehlern) |
| **Ausgeglichen** *(Default)* | mittel | ~3 Tage | mittel |
| **Konservativ** | langsam | ~1 Woche | niedrig |

## 2. Betriebsmodus (`operation_mode`)

Steuert, **ob** KONTINUUM handeln darf. Auch per Service `kontinuum.set_mode`
oder über die Dashboard-Buttons umschaltbar.

| Modus | Verhalten | Wann nutzen |
|-------|-----------|-------------|
| **Shadow** *(Start)* | beobachtet & lernt nur, führt **nichts** aus | Einlernphase (Tage 1–n) |
| **Confirm** | stellt Aktionen in eine Bestätigungs-Queue (Dashboard-Karten) | empfohlene Einstiegsphase – du bestätigst/ablehnst, das System lernt aus jeder Korrektur (negatives RPE bei Ablehnen) |
| **Active** | schaltet **freigeschaltete** Gerätetypen selbständig | wenn du den Vorhersagen vertraust |

Selbst im Active-Modus handelt KONTINUUM **nur** für Gerätetypen, die du explizit
freigeschaltet hast (`kontinuum.activate`).

## 3. Entity-Tracking (`track_mode`) & Labels

Welche Entities beobachtet werden. Pipeline: **Labels > Hard-Filter > Track-Mode > Heuristik**.

| Modus | Beschreibung |
|-------|-------------|
| **Standard** *(Default)* | alle relevanten Entities (Opt-out per Label) |
| **Labeled** | nur Entities mit Label `kontinuum` (Opt-in) |
| **Auto** | Label-Entities + heuristische Auswahl |

| Label | Wirkung |
|-------|---------|
| `kontinuum` | Entity wird **immer** getrackt |
| `ignore_kontinuum` | Entity wird **nie** getrackt (höchste Priorität) |

Labels wirken **ohne Neustart** (Refresh alle 5 Min).

## 4. Home-Only Modus

Wenn aktiv, **pausiert** KONTINUUM Lernen/Vorhersage, wenn niemand zuhause ist —
spart Ressourcen und vermeidet Rauschen durch leere Räume.

## 5. Freischalten von Gerätetypen

| Service | Wirkung |
|---------|---------|
| `kontinuum.activate` | schaltet autonome Ausführung für einen Typ frei: `light, switch, fan, cover, climate, media, automation, vacuum` |
| `kontinuum.deactivate` | deaktiviert (pro Typ oder `all`) |

> Hochrisiko-Geräte (z. B. Herd) werden bewusst nicht autonom geschaltet – die
> Amygdala kann hier ein Veto einlegen.

---

## 6. Cortex (LLM-Agents) — optional

> **KONTINUUM funktioniert vollständig ohne LLM.** Der Cortex ergänzt komplexe
> Entscheidungen durch bis zu **4 Agents**. Aktivierung: Konfigurieren → Menü
> „Cortex Agents (LLM)" → **Enable Cortex**.

| Option | Bedeutung | Empfehlung |
|--------|-----------|-----------|
| **Enable Cortex** | LLM-Schicht an/aus | aus = reines lokales Lernen |
| **Sequential Mode** | Agents nacheinander statt parallel anfragen | **an** bei nur einer GPU/Ollama-Instanz |
| **Diskussionsrunden** | wie oft Agents bei Uneinigkeit revidieren (1–3) | 2 (mehr = gründlicher, langsamer) |

### Rollen
**Comfort** (Licht/Temperatur/Stimmung) · **Energy** (Solar/Batterie/Verbrauch) ·
**Safety** (Anomalien, **Veto-Recht**) · **Coordinator** (entscheidet final über
die anderen) · **Custom** (eigener System-Prompt).
**Safety-Veto hat immer absoluten Vorrang** – auch vor dem Coordinator.

### Provider
Ollama (lokal, kein Key), OpenAI, Claude, Gemini, Grok sowie
**Custom / OpenAI-kompatibel** — alles über pure HTTP.

#### Einen Agenten einrichten
1. Agent-Übersicht → „Neuen Agent hinzufügen"
2. **Rolle** + **Provider** wählen
3. **URL / Host**:
   - Ollama: Host genügt (`localhost` oder `192.168.1.100`)
   - **Custom/OpenAI-kompatibel (z. B. OpenCLAW):** nur die **Basis-URL**
     (z. B. `http://192.168.1.50:8080`) — **`/v1/chat/completions` wird
     automatisch angehängt**, nicht selbst eintragen.
4. **API-Key**: nur Cloud-/Custom-Provider; bei Ollama leer lassen.
   (Custom: wird als `Authorization: Bearer <key>` gesendet.)
5. **Modell**: bei Ollama Dropdown der installierten Modelle; bei Cloud/Custom
   den Modellnamen eintragen.

> **OpenCLAW & Co.:** Voraussetzung ist ein **OpenAI-kompatibler**
> Chat-Completions-Endpunkt mit Bearer-Auth. Es wird **kein** `response_format`
> erzwungen (max. Kompatibilität); die Antwort läuft durch `normalize_proposal`,
> das non-striktes JSON verkraftet.

### Cortex-Services
| Service | Funktion |
|---------|---------|
| `kontinuum.cortex_consult` | manuelle Beratung aller Agents auslösen |
| `kontinuum.brain_review` | Brain-Analyse (Health-Score + Vorschläge) |
| `kontinuum.cortex_sequential` | Sequential-Modus umschalten |
| `kontinuum.configure_agent` / `remove_agent` | Agent per Service verwalten |

---

## 7. Kern-Services (immer verfügbar)

| Service | Funktion |
|---------|---------|
| `kontinuum.status` | detaillierten Status als Notification |
| `kontinuum.export_brain` | Brain als lesbare `brain_export.json` exportieren |
| `kontinuum.set_mode` | Betriebsmodus setzen (`shadow`/`confirm`/`active`) |
| `kontinuum.activate` / `deactivate` | Gerätetyp freischalten/sperren |
| `kontinuum.confirm_action` / `reject_action` | wartende Confirm-Aktion bestätigen/ablehnen |
| `kontinuum.enable_scenes` / `disable_scenes` / `set_scene` | Licht-Szenen pro Modus |

## 8. Events

| Event | wann |
|-------|------|
| `kontinuum_mode_changed` | Moduswechsel (`old_mode`, `new_mode`, `confidence`, `room`) |
| `kontinuum_confirm_requested` | Bestätigung steht an (Confirm-Modus) |
| `kontinuum_confirm_rejected` | Aktion abgelehnt → löst negatives RPE-Feedback aus |

## 9. Wichtige Sensoren

`sensor.kontinuum_status` (Version + alle Modul-Statistiken) ·
`sensor.kontinuum_accuracy` (Vorhersagegenauigkeit) ·
`sensor.kontinuum_mode` / `_room` / `_prediction` / `_energy` ·
`binary_sensor.kontinuum_anomaly` · `sensor.kontinuum_surprise` ·
`sensor.kontinuum_cortex_agent_1..4` (bei aktivem Cortex: `provider`, `model`,
`total_calls`, `error_rate`, …).

Vollständige Sensor-/Service-Liste: siehe [README](../README.md).
