# Additional Brain Areas (implemented lightweight)

Neu integriert:

1. **Reticular Formation (`reticular.py`)**
   - Event-Burst-Dämpfung pro Entity
   - `should_process(entity_id, domain)` als Aufmerksamkeitsfilter
   - Persistenz: `reticular.json.gz`

2. **Nucleus Accumbens (`nucleus_accumbens.py`)**
   - Schnelle Reward-Verstärkung pro `state|action`
   - wird bei Override/implizitem Positiv-Feedback aktualisiert
   - Persistenz: `accumbens.json.gz`

3. **Locus Coeruleus (`locus_coeruleus.py`)**
   - Arousal aus Event-Dichte (EMA)
   - Persistenz: `locus.json.gz`

4. **Entorhinal Cortex (`entorhinal_cortex.py`)**
   - Raumtransitionen und nächste-Raum-Prognose
   - Persistenz: `entorhinal.json.gz`

Alle Areale werden in `__init__.py` erzeugt, geladen, periodisch gespeichert und als Sensorwerte sichtbar gemacht.
