# KONTINUUM Context Expansion (Thalamus-first)

## Architektur (integrierbar)
- **Thalamus**: neue Semantiken + konfigurierbare Mapping-Regeln + Bucketing.
- **Hippocampus**: unverändert; neue Tokens laufen als normale `token_id`-Sequenzen ein.
- **Spatial Cortex**: zusätzliche Präsenzsignale (`co2`, `bed_presence`).
- **Insula**: Modus-Signale aus `cpu/gpu/steps/heartrate/sleep/gaming`.
- **Optionale Module**: `WearableProcessor`, `NetworkMonitor` liefern lose gekoppelte Token-Signale (`token`, `room`, `semantic`, `state`).

## Neue Tokenfamilien
- Computer: `office.cpu.low|medium|high`, `office.gpu.low|medium|high`, `office.gaming.on|off`
- Fahrzeug: `garage.tpms.low|normal|high`, `garage.wallbox.on|off`
- Umwelt: `livingroom.co2.good|elevated|high`
- Wearable: `house.steps.low|active|high`, `house.heartrate.low|normal|high`, `bedroom.sleep.deep|light|rem|awake`
- Netzwerk: `house.network.low|medium|high`

## Beispielintegration (3+ Quellen)

### 1) CPU-Last (Sensor)
- Entity: `sensor.office_pc_cpu_load`
- Semantik: `cpu`
- 82% -> `office.cpu.high`

### 2) CO2 (Sensor)
- Entity: `sensor.livingroom_co2`
- Semantik: `co2`
- 1200 ppm -> `livingroom.co2.high`

### 3) Smartwatch Schritte
```python
from custom_components.kontinuum.wearable_processor import WearableProcessor

wp = WearableProcessor(thalamus)
sig = wp.process_steps("chris", 8400, room="house")
_inject_token(hass, brain, sig, sig["timestamp"])
```

### 4) TPMS-Druck
- Entity: `sensor.tpms_fr_pressure`
- Semantik: `tpms`
- 2.0 bar -> `garage.tpms.low`

## Logging-Beispiel
Bei normalem Eventfluss erzeugt der Thalamus u.a.:
```json
{
  "token": "office.cpu.high",
  "semantic": "cpu",
  "state": "high"
}
```
Diese Tokens werden wie bestehende Tokens vom Hippocampus gelernt.

## Konfiguration
```python
thalamus.load_custom_profiles("/config/kontinuum/context_profile.json")
```
Siehe `docs/context_profile.example.json`.
