# KONTINUUM

![KONTINUUM Logo](custom_components/kontinuum/assets/logo.png)

**Dein Zuhause lernt selbst.**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-0.16.0-blue)
![HA](https://img.shields.io/badge/Home%20Assistant-2024.1+-green)

KONTINUUM ist eine experimentelle Home-Assistant-Integration, die dein Zuhause ohne Regeln, ohne Konfiguration und ohne Cloud versteht.

Statt Automationen manuell zu schreiben, beobachtet KONTINUUM den kontinuierlichen Strom von Ereignissen in deinem Zuhause, erkennt Muster in deinem Verhalten und sagt voraus, was als Nächstes passieren wird – vollständig lokal und extrem ressourcenschonend.

Das Ziel ist radikal einfach:

**Installieren – und vergessen. Dein Zuhause lernt den Rest.**

---

## Die Vision: Zero UI

Moderne Smart Homes sind oft komplizierter als das Leben selbst.

Man erstellt:
- Automationen
- Dashboards
- Szenen
- Regeln
- Skripte

Am Ende verbringt man mehr Zeit damit, das Haus zu programmieren, als darin zu leben.

KONTINUUM verfolgt eine andere Idee.

Ein intelligentes Zuhause sollte nicht programmiert werden müssen. Es sollte **verstehen**.

Die Vision von KONTINUUM ist deshalb **Zero UI**:
- keine Konfiguration
- keine Regeln
- keine Dashboards
- keine manuelle Logik

Du installierst das System – und es beginnt zu beobachten, zu lernen und zu verstehen.

---

## Warum der Name „KONTINUUM"?

Der Begriff *Kontinuum* stammt vom lateinischen *continuus* und bedeutet:

> zusammenhängend, ohne Unterbrechung, lückenlos

Ein Kontinuum beschreibt etwas, das sich stetig verändert, ohne klare Grenzen zwischen einzelnen Zuständen. Zwischen zwei Zuständen existieren immer unendlich viele Zwischenzustände.

Dieses Konzept taucht in vielen Disziplinen auf.

### Mathematik

In der Mathematik bezeichnet ein Kontinuum typischerweise den Raum der reellen Zahlen. Zwischen zwei Zahlen existieren immer unendlich viele weitere.

```
0 — 0.1 — 0.01 — 0.001 — ...
```

Es gibt keine Lücken.

### Physik

In der Physik beschreibt ein Kontinuum ein Medium, das als stetig verteilt betrachtet wird:
- Wasser als kontinuierliches Fluid
- Luftströmungen
- Temperaturfelder

Dieses Modell wird in der Kontinuumsmechanik verwendet.

### Philosophie

Auch viele Prozesse unseres Lebens sind Kontinua:

```
Tageslicht → Dämmerung → Nacht
Kind → Jugendlicher → Erwachsener
Winter → Frühling → Sommer
```

Es gibt keinen exakten Moment, an dem ein Zustand plötzlich zu einem anderen wird. Alles ist Teil eines Flusses.

---

## Das Problem klassischer Smart Homes

Software arbeitet normalerweise mit diskreten Ereignissen.

Auch Smart Homes funktionieren so:

```
Tür geöffnet
Licht eingeschaltet
Bewegung erkannt
```

Klassische Automationen sehen deshalb so aus:

```
Event → Regel → Aktion
```

Zum Beispiel:

> Wenn Tür geöffnet → dann Licht einschalten

Dieses Modell ist jedoch künstlich. Denn unser Alltag besteht nicht aus isolierten Ereignissen. Er ist ein **kontinuierlicher Strom** von Gewohnheiten und Routinen.

---

## Der Ansatz von KONTINUUM

KONTINUUM betrachtet dein Zuhause nicht als Sammlung von Regeln, sondern als **lebendes System aus Mustern**.

Statt Regeln zu definieren, beobachtet das System den Fluss von Ereignissen und erkennt darin wiederkehrende Sequenzen.

```
Verhaltensfluss → Muster → Vorhersage → Aktion
```

Das Haus beginnt zu verstehen:
- wann du aufstehst
- welche Räume du nacheinander betrittst
- wann du das Licht brauchst
- wann Geräte eingeschaltet werden
- welche Routinen sich täglich wiederholen

**Dein Zuhause wird damit nicht programmiert – es lernt.**

---

## Inspiriert vom menschlichen Gehirn

Die Architektur von KONTINUUM orientiert sich lose an biologischen Strukturen.

```
Thalamus → Hippocampus → Cerebellum → PFC → Aktion
    ↑           ↑            ↑          ↑
Hypothalamus  Spatial    Basalganglien Amygdala
    ↑         Cortex    (Belohnung)
  Insula ←─────┘
                  ↓
               Cortex (LLM-Agents)
```

Die einzelnen Module erfüllen unterschiedliche Aufgaben:

### Thalamus – Das sensorische Tor

Filtert den Strom aller Home-Assistant-Events, erkennt Räume und Semantik, erzeugt normalisierte Tokens. Kennt den Sonnenstand und weiß ob es Tag oder Nacht ist.

### Hippocampus – Das Gedächtnis

Lernt Sequenzen von Ereignissen mithilfe von N-Gramm-Markov-Ketten (1- bis 4-Gramme). Hier entstehen die Muster deines Alltags. Unterscheidet zwischen Werktagen und Wochenenden und passt sich adaptiv an die Datenmenge an – von 6 bis zu 96 Kontext-Buckets.

### Hypothalamus – Die Homöostase

Beobachtet Systemzustände und deren Trends:
- Temperatur und Temperaturverlauf
- Energieverbrauch und Batterietrends
- Solarproduktion und deren Veränderung

Erkennt nicht nur *was ist*, sondern auch *wohin es sich entwickelt*.

### Spatial Cortex – Die Raumwahrnehmung

Analysiert Bewegungen im Raum:
- Raumwechsel erkennen
- Aufenthaltsdauer verfolgen
- Typische Wege durch das Haus lernen
- Den nächsten Raum vorhersagen

### Insula – Das Körpergefühl

Erkennt Verhaltensmodi wie *schlafen*, *aktiv*, *entspannen* oder *abwesend*. Nutzt den Sonnenstand für biologisch plausible Einschätzungen – nachts wird Schlaf wahrscheinlicher, nicht erst um Mitternacht.

### Cerebellum – Die Reflexe

Extrahiert stabile Routinen als deterministische Regeln. Was sich hundertmal wiederholt hat, wird zum Automatismus.

### Basalganglien – Das Belohnungslernen

Lernt aus Feedback: Welche Aktionen führen zu positiven Ergebnissen? Go-Pathway verstärkt gute Gewohnheiten, NoGo-Pathway unterdrückt schlechte. Q-Values bewerten jede Aktion im Kontext.

### Amygdala – Die Risikobewertung

Bewertet Aktionen nach Sicherheit und kann Veto einlegen, bevor etwas Unerwünschtes passiert.

### Präfrontaler Kortex – Die Entscheidung

Wägt Vorhersagen ab, bewertet Nutzen gegen Risiko und entscheidet ob gehandelt wird.

### Cortex – Bewusstes Denken (LLM-Agents)

Optional: Bis zu 3 LLM-Agents (Ollama, OpenAI, Claude, Gemini, Grok) mit eigenen Rollen:
- **Comfort-Agent** – Optimiert Beleuchtung, Temperatur und Stimmung
- **Energy-Agent** – Überwacht Solar, Batterie und Verbrauch
- **Safety-Agent** – Erkennt Anomalien und hat Veto-Recht

Die Agents diskutieren untereinander (Multi-Agent-Diskussion) und finden einen Konsens. KONTINUUM (Prefrontal) ist der Orchestrator und trifft die finale Entscheidung.

**Cortex Bridge:** LLM-Ergebnisse fließen zurück ins Gehirn – Hippocampus speichert sie als Erfahrung, Basalganglien lernen daraus, Amygdala bewertet Risiken und das Cerebellum bildet neue Reflexe. KONTINUUM wird langfristig klüger, auch wenn der Cortex später deaktiviert wird.

**Brain Review:** Monatlich (oder manuell per Service) analysieren alle Cortex-Agents gemeinsam den Brain-Zustand – Patterns, Accuracy, Regeln, Habits – und liefern einen Health-Score mit konkreten Verbesserungsvorschlägen als Notification.

---

## Warum kein Machine Learning Framework?

KONTINUUM nutzt bewusst keine großen ML-Frameworks.

Der Grund ist einfach: Viele Home-Assistant-Systeme laufen auf Geräten wie:
- Raspberry Pi
- Home Assistant Green
- Home Assistant Yellow

Diese Systeme haben begrenzte Ressourcen.

Statt neuronaler Netze verwendet KONTINUUM deshalb statistische Sequenzmodelle:

**N-Gramm Markov-Ketten**

Diese Methode ist:
- extrem schnell
- transparent
- ressourcenschonend
- vollständig lokal

Das System lernt durch einfache Statistik:

```
Ereignis A → Ereignis B → Ereignis C
```

Wenn diese Sequenz oft beobachtet wird, steigt die Wahrscheinlichkeit, dass C als nächstes passiert.

---

## Vergessen und saisonale Muster

Ein intelligentes System muss nicht nur lernen – es muss auch **vergessen** können.

KONTINUUM verwendet dafür einen Decay-Mechanismus. Alte Muster verlieren langsam an Gewicht, während neue Gewohnheiten wichtiger werden.

So kann das System:
- sich an Veränderungen anpassen
- langfristige Gewohnheiten behalten
- saisonale Muster erkennen

Beispiele:
- **Winter:** Heizung wird regelmäßig aktiviert
- **Sommer:** das gleiche Ereignis führt nicht mehr zur Heizung

---

## Beispiel

Eine typische Morgenroutine könnte so aussehen:

```
Tür Schlafzimmer geöffnet → Bewegung im Flur → Bewegung in der Küche → Kaffeemaschine
```

Nachdem diese Sequenz häufig beobachtet wurde, erkennt KONTINUUM das Muster.

Das Ergebnis: Die Kaffeemaschine wird automatisch vorbereitet, noch bevor du daran denkst.

---

## Installation

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

Danach beginnt KONTINUUM automatisch zu lernen. **Keine Konfiguration notwendig.**

---

## Persönlichkeits-Presets

Bei der Installation wählst du wie schnell KONTINUUM lernt:

| Preset | Lerngeschwindigkeit | Erste Regeln nach | Fehlertoleranz |
|--------|--------------------|--------------------|----------------|
| **Mutig** | Schnell | ~1 Tag | Hoch (lernt aus Fehlern) |
| **Ausgeglichen** | Mittel | ~3 Tage | Mittel |
| **Konservativ** | Langsam | ~1 Woche | Niedrig |

Nachträglich änderbar: Integrationen → KONTINUUM → Konfigurieren

---

## Cortex (LLM-Agents) einrichten

Optional kannst du LLM-Agents aktivieren für komplexe Entscheidungen:

1. Integrationen → KONTINUUM → Konfigurieren
2. **Enable Cortex** aktivieren
3. Agent konfigurieren:
   - **Rolle** wählen (Comfort / Energy / Safety / Custom)
   - **Provider** wählen (Ollama, OpenAI, Claude, Gemini, Grok)
   - **URL** eingeben – bei Ollama reicht z.B. `localhost` oder `192.168.1.100` (http:// und Port werden automatisch ergänzt)
4. Im nächsten Schritt: **Modell auswählen**
   - Bei Ollama werden alle installierten Modelle als Dropdown angezeigt
   - Bei Cloud-Providern wird das Default-Modell vorgeschlagen
5. Optional: Weitere Agents hinzufügen (bis zu 3)

### Ollama-Tipps

```bash
# Ollama installieren (falls noch nicht geschehen)
curl -fsSL https://ollama.ai/install.sh | sh

# Modell herunterladen
ollama pull llama3.2

# Prüfen welche Modelle installiert sind
ollama list
```

Der Config Flow prüft automatisch die Verbindung zu Ollama und zeigt die verfügbaren Modelle an.

---

## Sensoren

KONTINUUM erstellt automatisch diese Sensoren:

**Alle Sensoren sind native HA-Entitäten** – sie werden automatisch erstellt und bei Deinstallation entfernt. Kein YAML nötig.

#### System-Sensoren

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.kontinuum_status` | Systemstatus + Version |
| `sensor.kontinuum_events` | Anzahl verarbeiteter Events |
| `sensor.kontinuum_accuracy` | Vorhersagegenauigkeit (Shadow-Mode) |
| `sensor.kontinuum_mode` | Aktueller Modus (sleeping, active, ...) |
| `sensor.kontinuum_room` | Erkannter Raum |
| `sensor.kontinuum_location` | Standort mit Bewegungsvorhersage |
| `sensor.kontinuum_persons_home` | Personen zuhause |
| `sensor.kontinuum_prediction` | Aktuelle Vorhersage |
| `sensor.kontinuum_energy` | Energiezustand + Trends |
| `sensor.kontinuum_cerebellum` | Gelernte Routinen |
| `sensor.kontinuum_basal_ganglia` | Habits + Go/NoGo |
| `sensor.kontinuum_unknown_entities` | Entities ohne Raum |

#### Cortex Agent-Sensoren

Wenn Cortex aktiviert ist, wird pro konfiguriertem Agent ein Sensor erstellt:

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.kontinuum_cortex_agent_1` | Status Agent 1 (active/idle/error) |
| `sensor.kontinuum_cortex_agent_2` | Status Agent 2 |
| `sensor.kontinuum_cortex_agent_3` | Status Agent 3 |

Jeder Agent-Sensor zeigt als Attribute:
- `role` – Rolle (comfort/energy/safety/custom)
- `provider` – Provider (ollama/openai/claude/...)
- `model` – Verwendetes Modell
- `total_calls` – Anzahl Aufrufe
- `total_errors` – Fehleranzahl
- `error_rate` – Fehlerrate
- `last_call` – Letzter Aufruf (z.B. "5m ago")

#### Aktivitäts-Sensoren (Dashboard)

Diese Sensoren zeigen die Aktivität jedes Gehirnmoduls (0.0 – 1.0):

| Sensor | Beschreibung |
|--------|-------------|
| `sensor.kontinuum_thalamus_activity` | Verarbeitungsrate |
| `sensor.kontinuum_hippocampus_activity` | Lerngenauigkeit |
| `sensor.kontinuum_hypothalamus_activity` | Energie-Trends |
| `sensor.kontinuum_amygdala_activity` | Risiko-Level |
| `sensor.kontinuum_insula_activity` | Modus-Konfidenz |
| `sensor.kontinuum_cerebellum_activity` | Regelabdeckung |
| `sensor.kontinuum_prefrontal_activity` | Entscheidungsrate |
| `sensor.kontinuum_spatial_activity` | Raum-Konfidenz |
| `sensor.kontinuum_basalganglia_activity` | Gewohnheitsstärke |

---

## Dashboard

KONTINUUM enthält ein Gehirn-Visualisierungs-Dashboard. Wenn bei der Installation aktiviert, erscheint es als **Sidebar-Eintrag** in Home Assistant:

- Sidebar → **KONTINUUM** (Brain-Icon)
- Oder direkt: `/kontinuum`

Das Dashboard zeigt alle Gehirnmodule, Aktivitäten, Vorhersagen und den Systemstatus in Echtzeit.

---

## Services

| Service | Beschreibung |
|---------|-------------|
| `kontinuum.enable_scenes` | Licht-Szenen nach Modus aktivieren |
| `kontinuum.disable_scenes` | Licht-Szenen deaktivieren |
| `kontinuum.set_scene` | Szene pro Modus konfigurieren |
| `kontinuum.status` | Detaillierten Status als Notification |
| `kontinuum.export_brain` | Gehirn-Snapshot exportieren |
| `kontinuum.activate` | Semantik für autonome Aktionen aktivieren |
| `kontinuum.deactivate` | Semantik deaktivieren |
| `kontinuum.configure_agent` | Cortex-Agent konfigurieren |
| `kontinuum.cortex_consult` | Cortex-Beratung manuell auslösen |
| `kontinuum.remove_agent` | Cortex-Agent entfernen |
| `kontinuum.brain_review` | Brain-Analyse durch alle Cortex-Agents |

---

## Events

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

---

## Technische Details

- **Kein ML, kein Deep Learning** – reine Statistik (1- bis 4-Gramm Markov-Ketten)
- **Komplett lokal** – keine Cloud, keine API-Calls (Cortex optional)
- **~6.000 Zeilen Python** – läuft auf Raspberry Pi 4
- **21-dimensionaler Kontextvektor** – Zeit, Sonnenstand, Energie, Trends, Modus
- **Adaptive Kontext-Buckets** – wächst von 6 auf 96 (Zeit × Modus × Energie × Tagestyp)
- **Persistenz** – Gehirn wird in `brain.json.gz` komprimiert gespeichert (RPi-SD-schonend)
- **Shadow-Mode** – beobachtet und validiert Vorhersagen bevor es handelt
- **Label-Support** – HA-Labels als Raum-Hinweis nutzbar
- **Saubere Deinstallation** – Entfernt brain, Helfer und Entities automatisch
- **Cortex Bridge** – LLM-Ergebnisse fließen ins Gehirn zurück (Hippocampus, Basalganglien, Amygdala, Cerebellum)
- **Multi-Agent-Diskussion** – Agents diskutieren und finden Konsens
- **Ollama Model Discovery** – Config Flow erkennt installierte Modelle automatisch

---

## Projektstatus

KONTINUUM ist ein experimentelles Forschungsprojekt.

Das Ziel ist nicht nur eine weitere Smart-Home-Integration, sondern die Erforschung einer grundlegenden Frage:

> Kann ein Zuhause seine Bewohner verstehen, ohne programmiert zu werden?

---

## Philosophie

> Die beste Technologie ist die, die man nicht bemerkt.

Wenn KONTINUUM perfekt funktioniert, passiert etwas Merkwürdiges: Du denkst nicht mehr über dein Smart Home nach. Es funktioniert einfach.

So wie ein Zuhause es sollte.

---

**Lerne ein Wort. Dein Zuhause lernt den Rest.**

*KONTINUUM*

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
