# KONTINUUM – Architektur-Dokumentation

## Überblick

KONTINUUM ist ein neuroinspiriertes System das Home Assistant Events beobachtet, Muster lernt und Vorhersagen trifft. Es besteht aus 8 Modulen die jeweils einer Gehirnregion nachempfunden sind.

## Datenfluss

```
HA State Change
       │
       ▼
   [Thalamus] ──→ Filter: Domain relevant? Entity registriert?
       │                    │
       │              (nein = ignoriert)
       ▼
  Semantik + Raum zuordnen
       │
       ├──→ Energie/Klima? ──→ [Hypothalamus] absorbiert (~95%)
       │                              │
       │                    (signifikant?) ──→ Token injizieren
       │
       ├──→ Motion/Tracker? ──→ [Spatial Cortex]
       │                              │
       │                    Raumwechsel? ──→ Token injizieren
       │                              │
       │                    ──→ [Insula] Moduswechsel?
       │
       ▼
  Token erzeugen ("bedroom.light.on")
       │
       ▼
   [Hippocampus] ──→ Lernen + Vorhersagen
       │
       ├──→ Kontextvektor (15D): Zeit(9) + Energie(3) + Modus(3)
       │
       ├──→ N-Gramm Markov-Kette in Kontext-Buckets
       │
       ▼
  Top-5 Predictions
       │
       ▼
   [Cerebellum] ──→ Stabile Routinen? (compiliert alle 10 min)
       │
       ▼
   [Amygdala] ──→ Risikobewertung (ALLOW / CAUTION / VETO)
       │
       ▼
   [Präfrontaler Kortex] ──→ Entscheidung
       │
       ├──→ Shadow-Mode: OBSERVE (nur beobachten)
       ├──→ SUGGEST (Notification an User)
       └──→ EXECUTE (Aktion ausführen)
```

## Module im Detail

### Thalamus (`thalamus.py`)

Sensorisches Tor. Filtert irrelevante Events, erkennt Räume und Semantik, erzeugt Tokens.

- **Raum-Erkennung**: 3 Quellen (HA Area Registry > Friendly Name > Entity ID)
- **Semantik**: Domain-basiert + Device Class + Name-Keywords
- **Tokenisierung**: `{raum}.{semantik}.{state}` z.B. `bedroom.light.on`
- **Numerische Buckets**: Temperatur → cold/cool/comfort/warm/hot
- **Duplikat-Filter**: Gleicher Token hintereinander für gleiche Entity wird ignoriert

### Hippocampus (`hippocampus.py`)

Gedächtnissystem mit N-Gramm Markov-Ketten.

- **Arbeitsgedächtnis**: Letzte 20 Tokens als Sequenz
- **Konsolidiertes Gedächtnis**: Kontext-gewichtete Transitions pro Bucket
- **N-Gramm-Größen**: 1, 2, 3 (gewichtet 0.2, 0.5, 0.8)
- **Adaptive Buckets**: Phase 1 (<2000 Events) = 6 Buckets (nur Zeit), Phase 2 (<5000) = 24, Phase 3 = 48
- **Exponentieller Decay**: Alte Muster verblassen täglich
- **Shadow-Validierung**: Misst Accuracy ohne zu handeln
- **Speicherlimit**: Max 500 N-Gramme pro Bucket, LFU-Eviction

**Kontextvektor (15 Dimensionen):**

| Index | Dimension | Quelle |
|-------|-----------|--------|
| 0-1 | Stunde (sin/cos) | Thalamus |
| 2-3 | Wochentag (sin/cos) | Thalamus |
| 4-5 | Monat (sin/cos) | Thalamus |
| 6 | is_weekend | Thalamus |
| 7-8 | reserved | – |
| 9 | Batterie (0-1) | Hypothalamus |
| 10 | Solar (0-1) | Hypothalamus |
| 11 | Verbrauch (0-1) | Hypothalamus |
| 12 | Modus-Index (0-1) | Insula |
| 13 | Modus-Confidence (0-1) | Insula |
| 14 | Modus-Dauer (0-1) | Insula |

### Hypothalamus (`hypothalamus.py`)

Absorbiert Energie- und Klima-Events (~95% aller HA-Events). Gibt nur bei signifikanten Änderungen Tokens weiter.

- **Energie**: Batterie, Solar, Verbrauch, Grid → `house.energy.{normal|low|critical|charging}`
- **Klima**: Temperatur, Helligkeit, Heizung → `house.climate.{cold|cool|comfort|warm|hot}`
- **Cooldowns**: 10 min (Energie), 30 min (Klima)
- **Cooldowns werden persistiert** (überlebt Restart)

### Spatial Cortex (`spatial_cortex.py`)

Raumwahrnehmung mit gewichteten Signalen und Drei-Schicht-Schutz gegen Bouncing.

- **Signalquellen**: Tracker (0.9), Presence (0.7), Motion (0.5), Door (0.2)
- **Anti-Bounce**: Hysterese (1.2×) + Confirmation (30s) + Cooldown (60s)
- **Tokens**: `person.entered.{room}`, `person.left.{room}`, `person.active.{room}`

### Insula (`insula.py`)

Modus-Erkennung basierend auf akkumulierten Signalen.

- **Modi**: sleeping, waking_up, active, relaxing, cooking, away
- **Signalgewichte**: Pro (semantic, state) → Mode-Wahrscheinlichkeiten
- **Raum-Hinweise**: bedroom → sleeping+0.2, kitchen → cooking+0.3
- **Cooldown**: 300s zwischen Moduswechseln, min. 40% Confidence

### Cerebellum (`cerebellum.py`)

Extrahiert stabile Routinen als deterministische Regeln.

- **Quelle**: 1-Gramm Transitions aus dem Hippocampus
- **Filter**: MIN_OBSERVATIONS (preset-abhängig) + MIN_CONFIDENCE
- **Self-Loop-Filter**: trigger == target wird ignoriert
- **Max 50 Regeln**, sortiert nach Confidence × Count
- **Kompilierung**: Alle 10 Minuten

### Amygdala (`amygdala.py`)

Risikobewertung mit gelernten Modifikationen.

- **NEVER_AUTO**: alarm, lock (absolutes Veto)
- **SAFE_STATES**: Prüft ob Ziel-Zustand bekannt ist
- **Gestaffelte Schwellen**: Risiko <0.15 → 30% Confidence, <0.3 → 50%, <0.5 → 65%
- **Feedback-Learning**: Negative Overrides erhöhen Risiko (+0.05), positive senken (-0.02)

### Präfrontaler Kortex (`prefrontal_cortex.py`)

Entscheidungsinstanz mit Override-Erkennung.

- **Stages**: OBSERVE → PREPARE → SUGGEST → EXECUTE
- **Shadow-Mode**: Alle Entscheidungen sind OBSERVE (nur beobachten)
- **Override-Erkennung**: Wenn User eine KONTINUUM-Aktion innerhalb 60s rückgängig macht → negatives Feedback
- **Implicit Positives**: Aktion nicht rückgängig gemacht nach 300s → positives Feedback

## Persistenz

Alle Module serialisieren ihren Zustand in `brain.json` (alle 5 Minuten + bei Shutdown). Format:

```json
{
  "version": "0.10.0",
  "saved_at": "2026-03-10T18:00:00+00:00",
  "preset": "ausgeglichen",
  "thalamus": { ... },
  "hippocampus": { ... },
  "hypothalamus": { ... },
  "spatial": { ... },
  "insula": { ... },
  "amygdala": { ... },
  "cerebellum": { ... },
  "prefrontal": { ... }
}
```

## Config Flow

Installation über Integrationen → Hinzufügen → KONTINUUM. Presets steuern die Lernparameter:

| Parameter | Mutig | Ausgeglichen | Konservativ |
|-----------|-------|-------------|-------------|
| cerebellum_min_obs | 3 | 4 | 7 |
| cerebellum_min_conf | 0.60 | 0.65 | 0.80 |
| hippocampus_decay | 0.993 | 0.997 | 0.998 |
| hippocampus_min_obs | 2 | 2 | 3 |
