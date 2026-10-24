# Die Cortex-Tafel — bringt der Cortex (LLM-Agenten) messbar etwas?

Die Messung zu **ha-kontinuum#3**: das Cortex-Organ am Messstand des Kerns
(`kontinuum-core`, `benchmarks/spur`), alle Zahlen **neu gemessen** auf
dieser Maschine — nichts übernommen. Modelle nur lokal über Ollama.
Daten nur Simulation und CASAS (Datenregel core#2 — nie echte Hausdaten).

**Urteil in einem Satz:** Als Wähler trägt der Cortex derzeit nicht — er
schlägt den Zufallsgegner knapp, verliert aber klar gegen die Engine
(„Cortex aus") und gegen das triviale „nichts tun"; **einschalten** ist von
dieser Tafel nicht gedeckt, **verbessern** ist der Weg (drei konkrete
Ansatzpunkte unten), und auf den CASAS-Spuren ist das Organ strukturell
arbeitslos (0 Beratungen, weil kein Menü entsteht).

---

## 1. Die Frage und der Aufbau

Gefragt ist: Was bringt das Organ gegen „Cortex aus"? Gemessen wird am
Messstand des Kerns — **dieselben Spuren, dieselben rollierenden
Ursprünge, dieselbe Ereigniszeit** (predict-then-learn, k Wochen Training,
Woche k+1 Test). Alles, was die Tafel hinzufügt, hängt **neben** der
Schleife, nie darin:

* **Engine** — wörtlich die Messstand-Zeile (Top-1/Top-3 gegen den
  Token-Strom; leere Listen zählen nicht). Die Zeile ist per Test
  zifferngleich gegen `benchmarks.spur.messstand.messe_ursprung` gepinnt.
* **Engine+Cortex** — dieselben Vorhersagen, aber nach einer Beratung
  zielt die erste Stelle auf das **gewählte** Token („die Wahl ist die
  Vorhersage"). Das Organ schreibt nie ins Gehirn zurück; ohne Beratung
  ist diese Zeile darum **gemessen identisch** zur Engine-Zeile.
* **B0/B1/B2** — die Gegner des Messstands auf denselben Testwochen.
* **Das echte Organ**: `baue_menue`, `anlass`, `lies_wahl`, `entscheide`,
  `Nachhall` aus `custom_components/kontinuum/cortex_organ.py`; jeder
  Modellaufruf über den echten `CortexAgent.waehle`/`_call_ollama`-Weg.
  Die Frage ist wörtlich die von `Cortex.consult` (durch Test gepinnt,
  inklusive der Nutzlast: `format=antwort_schema`, `think=false`).
* **Die zwei Wahrheits-Waagen**: die eigene `FensterWaage` (erste Option,
  die im 900-s-Nachhallfenster wirklich eintritt — sonst „nichts tun") und
  unabhängig davon `Nachhall.quoten()` des Organs selbst. Beide Waagen
  stimmen in allen 20 Läufen des Armes A Zeile für Zeile überein
  (Abweichungen nur in der 4. Dezimale = Rundung des Organs).
* **Die Abschaltprobe**: In **jedem** Lauf stimmt zusätzlich ein gesäter
  Zufallswähler ab (zieht uniform aus dem Menü) — er zählt in derselben
  Bilanz mit, ohne die Mehrheit zu beeinflussen. „Erst wenn der Cortex
  diesen Gegner schlägt, zählt ein Gewinn."

Vier Anlässe führten zu Beratungen, nie mehr: Engine unsicher
(Top-1 zwischen 0.30 und 0.75, Marge < 0.10), Anomalie, mindestens 300
gelernte Ereignisse, mindestens 900 Ereignis-Sekunden Abstand.

### Pins (der Stand, auf dem gemessen wurde)

| Was | Wert |
|---|---|
| ha-kontinuum | Branch `messbiene/cortex-tafel`, Inhalt von `5c76ca1` (alle sechs Arme) |
| kontinuum-core | lokaler Checkout `messbiene/locus-inkrementell` = `2310a3e` (Engine **und** Messstand aus einem Stand) |
| Gegenprobe Kern | Trockenlauf auf `origin/main` = `99e754f` liefert **byte-identische** Zeilen |
| Modelle (Ollama, lokal) | `llama3.2:1b` (`baf6a787fdff`), `llama3.2:3b` (`a80c4f17acd5`) |
| Maschine | AMD Ryzen 7 3800X, 6 Kerne, 9 GB RAM, **keine GPU** (reine CPU-Inferenz) |
| Testumgebung | pytest 9.0.0, pytest-asyncio 1.3.0, pytest-homeassistant-custom-component 0.13.316 (HA 2026.2.3) |

## 2. Die Arme (was gelaufen ist)

Sechs Arme, 80 Läufe, 703 104 Testereignisse:

| Arm | Was | Modell | Läufe |
|---|---|---|---|
| **A** | Simulation `klassisch`, comfort | llama3.2:1b | 5 Saaten × 4 Ursprünge |
| **B** | Simulation `klassisch`, comfort | llama3.2:3b | 5 Saaten × 4 Ursprünge |
| **C** | Simulation `klassisch`, comfort **+ safety** (Vetos) | llama3.2:3b | 3 Saaten × 4 Ursprünge |
| **D** | Simulation `geraete` (viele Aktionen), comfort | llama3.2:3b | 3 Saaten × 4 Ursprünge |
| **E** | CASAS, fünf echte Häuser | llama3.2:1b | 5 Häuser × 3 Ursprünge |
| **F** | Abschaltprobe allein: Berater **ist** der Zufall | — | 1 Lauf (Saat 17) |

Aufruf (Arm A; die anderen Arme analog mit `--modell`/`--agenten`/`--sim`/`--casas`):

```
python -m werkzeug.cortex_tafel --kern ../kontinuum-core \
    --sim klassisch --saaten 1 2 3 4 5 --ursprunge 4 5 6 7 \
    --modell llama3.2:1b --agenten comfort --ziel build/cortex/a-1b
```

## 3. Die Tafel — die Zahlen

### 3.1 Vorhersage-Ebene (Top-1 / Top-3 gegen den Token-Strom)

| Arm | n | Engine | Engine+Cortex | B0 | B1 | B2 |
|---|---|---|---|---|---|---|
| A (1b) | 4099 | **82.2 / 99.1** | 82.2 / 99.1 | 0.0 / 13.7 | 23.8 / 52.7 | 56.6 / 89.0 |
| B (3b) | 4099 | **82.2 / 99.1** | 81.9 / 99.1 | 0.0 / 13.7 | 23.8 / 52.7 | 56.6 / 89.0 |
| C (Veto) | 2460 | **82.8 / 99.2** | 82.6 / 99.2 | 0.0 / 13.7 | 23.5 / 52.5 | 56.5 / 88.9 |
| D (geräte) | 2884 | **93.6 / 99.6** | 92.5 / 99.6 | 8.7 / 14.5 | 31.3 / 92.9 | 60.7 / 98.1 |
| E (CASAS) | 689 357 | **49.5 / 81.5** | 49.5 / 81.5 | 1.8 / 15.7 | 5.3 / 19.9 | 37.5 / 60.7 |
| F (Zufall) | 205 | **82.0 / 98.5** | 78.5 / 98.5 | 0.0 / 13.7 | 24.9 / 52.2 | 50.7 / 85.4 |

Lesart: Die Engine ist auf allen Böden der beste Vorhersager (CASAS
49.5 % Top-1 — ehrlich weniger als im Simulator). Wo der Cortex
tatsächlich in die Wahl eingreift, **sinkt** die Top-1: B −0.3, C −0.2,
D −1.1, F −3.4 Punkte. Wo er nur „nichts" wählt (A: alle 214), bleibt die
Zeile unverändert. Das ist die messbare Form von „das Organ schreibt nicht ins
Gehirn": Der Verlust entsteht nur an den Stellen, an denen er die
Engine-Wahl überstimmt.

### 3.2 Wirkungs-Ebene (das 900-s-Fenster — hier zählt die Handlung)

Trefferquote je Wähler auf **denselben** Beratungen (n = Zahl der
Beratungen; `engine` = die unveränderte Engine-Wahl, `nichts` = die
triviale Grundstellung, `zufall` = der Abschaltprobe-Gegner):

| Arm | Beratungen (je 1000 Ereignisse) | Änderungen | cortex (`konsens`) | Zufall | Engine (aus) | „nichts" |
|---|---|---|---|---|---|---|
| A (1b) | 214 (52.2) | 214 (100 %) | 40.2 % | 37.9 % | **59.8 %** | 40.2 % |
| B (3b) | 214 (52.2) | 167 (78 %) | 44.4 % | 37.9 % | **59.8 %** | 40.2 % |
| C (Veto) | 135 (54.9) | 121 (90 %) | 40.0 % | 38.5 % | **62.2 %** | 37.8 % |
| D (geräte) | 306 (106.1) | 266 (87 %) | 74.2 % | 46.1 % | 20.3 % | **79.7 %** |
| F (Zufall) | 13 (63.4) | 8 (62 %) | 23.1 % | 23.1 % | **76.9 %** | 23.1 % |

Das ist die Kern-Tafel. Drei Dinge stehen darin:

1. **Die Engine schlägt den Cortex überall** (außer im Geräte-Haus, dazu
   Punkt 2) — und die Engine kostet nichts, sie ist schon da.
2. Im Geräte-Haus (D) ist „nichts tun" die beste Politik (79.7 %), weil
   dort meist gar nichts passiert; der Cortex liegt mit 74.2 % zwischen
   „nichts" und Zufall — er wählt zu oft eine echte Aktion, die dann nicht
   eintritt.
3. **Die Abschaltprobe ist knapp bestanden**: Der Cortex liegt in A/B/C/D
   über dem Zufallsgegner (+2.3 / +6.5 / +1.5 / +28.1 Punkte), aber er ist
   die schwächere der beiden nicht-trivialen Referenzen. Ein „Gewinn" gegen
   den Zufall allein trägt die Entscheidung nicht, wenn „Cortex aus"
   besser ist.

Was die Cortex-Wahl konkret war: in A **alle 214** Änderungen = „nichts
tun" (100 %). In B 165 von 167, in C 118 von 121, in D 258 von 266. Die
seltenen echten Aktionen (B: 2, C: 3, D: 8, F: 4) sind einzeln zu wenige
für belastbare Quoten; ihre Sofort-Treffer zählt das Werkzeug, die Zahl
steht unten unter „Was die Prüfung fand" bewusst **nicht** in dieser Tafel.

### 3.3 CASAS — fünf echte Häuser, je Haus

| Haus | k | Testereignisse | Engine Top-1 | Engine Top-3 | B2 Top-1 | Beratungen | Menüs |
|---|---|---|---|---|---|---|---|
| aruba | 4 | 52 993 | 51.1 % | 82.0 % | 39.1 % | 0 | 323 leer |
| aruba | 5 | 38 724 | 56.2 % | 86.2 % | 42.4 % | 0 | 283 leer |
| aruba | 6 | 55 088 | 52.5 % | 83.8 % | 40.2 % | 0 | 337 leer |
| cairo | 4 | 72 401 | 48.7 % | 82.0 % | 34.4 % | 0 | 354 leer |
| cairo | 5 | 73 587 | 46.0 % | 79.3 % | 32.9 % | 0 | 336 leer |
| cairo | 6 | 71 050 | 49.2 % | 81.9 % | 35.4 % | 0 | 355 leer |
| milan | 4 | 12 406 | 54.1 % | 82.3 % | 44.9 % | 0 | 80 leer |
| milan | 5 | 42 743 | 51.8 % | 81.5 % | 42.0 % | 0 | 286 leer |
| milan | 6 | 42 223 | 52.0 % | 81.6 % | 40.9 % | 0 | 311 leer |
| tulum1 | 4 | 17 248 | 54.9 % | 89.4 % | 45.8 % | 0 | 105 leer |
| tulum1 | 5 | 24 940 | 46.5 % | 81.8 % | 39.5 % | 0 | 105 leer |
| tulum1 | 6 | 20 415 | 43.0 % | 76.1 % | 33.6 % | 0 | 91 leer |
| tulum2 | 4 | 57 422 | 47.0 % | 80.1 % | 35.6 % | 0 | 346 leer |
| tulum2 | 5 | 60 995 | 47.5 % | 79.2 % | 36.3 % | 0 | 349 leer |
| tulum2 | 6 | 47 122 | 48.1 % | 79.8 % | 36.7 % | 0 | 312 leer |

**Der Strukturbefund:** In allen fünf Häusern und allen Ursprüngen feuert
das Organ aus eigenem Anlass (insgesamt 2 812 × „knapp" + 1 161 ×
„Anomalie"), baut 3 973 Menüs — und **jedes einzelne ist leer** („nichts
tun" ohne jede echte Option), weil in den CASAS-Tokens kein
aktionsfähiges (Dienst, Entität)-Paar vorkommt: Die Spuren sind fast
reines Motion/Temperatur/Tür. Damit gilt: **0 Beratungen, 0 Modellaufrufe,
0 Kosten** — und Engine+Cortex ist Zeile für Zeile identisch zur Engine.
Das Organ ist auf diesem Boden strukturell arbeitslos, nicht schlecht.
(Zwei Läufe der 3-Wochen-Scheibe `aruba_3w` sind als „0 Testereignisse"
ausgewiesen und zählen nicht — eine Scheibe, die keinen k≥4-Ursprung
tragen kann.)

Das sagt **nichts** über ein echtes Haus mit Lichtern und Schaltern
(.247): Dort entstehen aus denselben Regeln Menüs, sobald die Engine
aktionsfähige Tokens vorhersagt. Im Geräte-Haus (D) ist genau das der
Fall — dort wird der Cortex 306-mal gefragt. Wer .247 beurteilen will,
muss die Menüquote **dort** messen (lokal, ohne Datenversand).

### 3.4 Die Vetos (Arm C: comfort + safety, 3b)

Der safety-Agent darf als Einziger streichen (`veto` im Antwort-Schema,
wörtlich wie `CortexAgent.waehle`). Gemessen: 135 Beratungen, 46
Streichungen. Davon trafen **11** die Fenster-Wahrheit — die gestrichene
Option wäre also der Treffer gewesen: **falsch verhindert**. Die übrigen
**35** strichen eine Option, die im Fenster nicht eintrat (kein
Treffer-Verlust): **richtig verhindert**. (Die beiden Zweige sind
komplementär und erschöpfend; die Umrechnung der Rohzahlen ist exakt, s.
Abschnitt „Was die Prüfung fand".)

Zwei Nebenbefunde im selben Arm:

* Die **Stimmen** standen einzeln besser da als ihr Konsens:
  safety 46.7 %, comfort 44.4 %, — der Konsens aber nur 40.0 %. Grund ist
  die Entscheidungsregel: Eine echte Option braucht eine **absolute
  Mehrheit**, sonst gewinnt „nichts". Bei zwei sich uneinigen Stimmen
  gewinnt fast immer „nichts" — die Regel zieht das Ergebnis unter die
  beste Einzelstimme.
* Die Vetos haben den Zufallsgegner auf denselben Beratungen nicht
  geschlagen (Konsens 40.0 % vs. Zufall 38.5 %).

### 3.5 Die Kosten (aus den Ollama-Antworten, nicht geschätzt)

| Arm | Aufrufe | s je Aufruf | Prompt-Tokens | Antwort-Tokens | je 1000 Ereignisse |
|---|---|---|---|---|---|
| A (1b) | 214 | 5.8 | 327 | 24 | 52.2 Beratungen |
| B (3b) | 214 | 9.4 | 327 | 45 | 52.2 Beratungen |
| C (3b, 2 Agenten) | 270 | 7.2 | 341 | 48 | 54.9 Beratungen |
| D (3b) | 306 | 8.6 | 318 | 45 | 106.1 Beratungen |
| E (CASAS) | **0** | — | — | — | 0 (keine Menüs) |
| F (Zufall) | **0** | — | — | — | 63.4 Beratungen |

Kosten je Beratung: 5.8–9.4 s CPU (keine GPU!), ~320–340 Prompt- und
24–48 Antwort-Tokens. Ein Haus mit ~1000 Ereignissen am Tag und der
Simulationsquote von ~50–100 Beratungen je 1000 Ereignisse käme damit auf
etwa **5–15 Minuten Rechenzeit pro Tag** — der Preis ist klein; das
Problem ist der Ertrag, nicht die Rechnung.

## 4. Was die Prüfung fand (Selbstkontrolle der Tafel)

Die Tafel wurde gegen sich selbst gestellt; drei Fehler fielen dabei auf
und wurden **rot-zuerst** geheilt (Commits `5c76ca1`, `da945c8`):

1. **Die Fenster-Grenze.** Der Rauchlauf zeigte eine unmögliche Zahl
   (Engine 92.3 % im Fenster). Ursache: Das Ereignis, das ein Fenster
   *schließt*, wurde noch als Wahrheit verbucht. Die `FensterWaage` hat
   jetzt dieselbe Grenzform wie der `Nachhall` des Organs („genau auf der
   Grenze zählt noch"); vier Grenz-Tests pinnen das. Seither stimmen
   eigene Waage und Organ-Waage in allen Läufen überein.
2. **Die Veto-Richtung.** Die Zähler standen auf dem Kopf: „richtig
   verhindert" zählte den Streich auf die Wahrheit — dabei kostet genau
   der einen Treffer. Jetzt gilt: Streich == Wahrheit → **falsch
   verhindert**. Die Zahlen oben sind exakt umgerechnet (Zweige
   komplementär: aus roh 11/35 wird 35 richtig / 11 falsch); ein
   Bestätigungslauf startete am 24.10. und wurde nach 2 von 12 Läufen
   abgebrochen, weil die Maschine inzwischen unter Last 9 (bei 6 Kernen)
   stand: Modellaufrufe brauchten statt 7–9 plötzlich 40–66 s, die
   safety-Stimme lief zweimal in den 90-s-Timeout. Unter solchen
   Bedingungen hätte der Lauf die Maschine gemessen, nicht den Cortex —
   der alte C-Lauf hatte 0 Timeouts und ist die sauberere Quelle.
3. **Das Bestätigungs-Leck.** Der Zähler „Änderungs-Treffer sofort"
   öffnete sein Fenster auch für die Bestätigung der Engine-Spitze (Wahl
   1): Im Lichtstrom-Pin füllten 49 von 50 Bestätigungen den Zähler,
   obwohl nichts geändert wurde. Jetzt öffnen nur echte Änderungen. Die
   Lauf-Zahlen für diesen Zähler sind darum je nach Arm unterschiedlich
   stark verwässert und stehen **nicht** in dieser Tafel; die
   Trefferquote der Änderungen steht in der Fenster-Tafel (3.2), das ist
   die belastbare Größe.

Weitere Proben, die bestanden wurden:

* **Engine-Zeile zifferngleich** gegen den Kern-Messstand
  (`205/168/202` für klassisch, Saat 1, k=4) — per Test.
* **Zwei Kern-Stände, ein Ergebnis**: Trockenlauf auf `2310a3e` und
  `99e754f` (origin/main) byte-identisch.
* **Aruba-Wiederholung**: derselbe Lauf ein zweites Mal gemessen —
  wieder 0 Beratungen und exakt dieselben 323 leeren Menüs.
* **Frage und Nutzlast** wörtlich wie `Cortex.consult`/`CortexAgent.waehle`
  (per Test, mit gestopfter Uhr und Fake-Ollama).
* **Fremde Speicher vergleichen**: Der `zufall`-Wähler und der
  `nichts`-Wähler liefern in den Armen A und B exakt dieselben Quoten
  (81/214 bzw. 86/214) — wie es sein muss, denn beide hängen nur an den
  Wahrheiten, nicht am Modell.

## 5. Grenzen der Messung (was diese Tafel NICHT sagt)

* **Simulation ist nicht Haus.** Die Simulationsspuren sind synthetisch
  (klassischer Tagesablauf bzw. Gerätehaus); CASAS ist echt, hat aber
  keine Aktions-Tokens. Ein echtes Haus mit Licht/Schalter kann Menüs
  erzeugen — und muss dann neu gemessen werden.
* **Der Cortex wird gefragt, nie befragt**: Er sieht nur die Menüregeln
  des Organs; andere Fragen (freier Text, Erklärungen) sind nicht Teil
  dieser Messung.
* **„Richtig" heißt hier: das Fenster-Ergebnis.** Die 900-s-Waage kennt
  nur „hat das Haus genau das getan". Ob eine Aktion *gut* war, weiß sie
  nicht — Veto-Zahlen sind darum Wirkungs-, keine Sicherheitszahlen.
* **Kleine Stichproben**: A/B 214 Beratungen, C 135, F 13 — Unterschiede
  von 1–2 Punkten sind keine Befunde. Die großen Abstände (10+ Punkte)
  tragen.
* **CPU-Latenzen**: gemessen auf 6 Kernen ohne GPU; mit GPU wären die
  Sekunden kleiner, alles andere gleich.

## 6. Urteil

**Nicht einschalten** — jedenfalls nicht als Wähler, und auf .247 schon
gar nicht auf Basis dieser Zahlen. Die Abschaltprobe ist knapp bestanden
(Cortex > Zufall), aber die zwei Referenzen, die zählen, schlägt er nicht:
die Engine („Cortex aus") und im Geräte-Haus das triviale „nichts tun".

**Verbessern — drei Ansatzpunkte, alle aus den Zahlen:**

1. **Die Rolle wechseln.** Als Wähler ist der Nutzen nicht da; als
   *Melder* hat er etwas gezeigt: Er schlägt den Zufall auch dort, wo die
   Engine-Wahl im Fenster schlecht aussieht (D: Engine 20.3 % — dort war
   die Engine-Spitze fast nie das, was gleich passierte). Ein Organ, das
   bei knapper Engine-Lage **warnt** statt zu wählen, kostet nichts (nur
   Tokens) und kann später gegen die Engine-Bilanz geprüft werden.
2. **Die Entscheidungsregel entschärfen.** Absolute Mehrheit ist eine
   schlechte Regel für zwei Stimmen — sie erzeugt „nichts tun" als
   Statist. Gemessen: Konsens 40.0 % gegen beste Einzelstimme 46.7 %
   (Arm C). Eine relative Mehrheit mit Mindest-Sicherheit der Stimme
   würde das Leck schließen.
3. **Erst schlagen, dann wählen.** Ein Cortex, der nur handeln darf, wenn
   er die Engine **live** schlägt (gleitende eigene Trefferquote vs.
   Engine-Trefferquote auf denselben Fragen), kann nichts kaputtmachen —
   er schweigt, solange er schlechter ist. Diese Tafel ist die
   Messlatte dafür.

**Weglassen** ist die richtige Antwort für den heutigen Zustand: Wenn
morgen eingeschaltet würde, hieße das in Arm A „100 % der Engine-Wahlen
überstimmt, alle 214 Änderungen sind nichts tun, Trefferquote 40.2 %
statt 59.8 %". Nichts davon ist ein Gewinn. Und auf CASAS-Spuren gibt es
nichts zu entscheiden (0 Menüs) — das Organ wäre auch dort ein
Nullsummen-Zuschauer.

## 7. Reproduzieren

```
# Kern als Checkout bereitstellen (Engine UND Messstand aus EINEM Stand)
git clone <kontinuum-core> /tmp/kern && git -C /tmp/kern checkout 2310a3e

# Tests der Tafel (inkl. der Pins gegen den Kern-Messstand)
KONTINUUM_KERN=/tmp/kern python -m pytest -q \
    tests/test_cortex_tafel.py tests/test_cortex_tafel_messstand.py

# Trockenlauf (ohne Modell, für CI)
python -m werkzeug.cortex_tafel --kern /tmp/kern \
    --trocken --sim klassisch --saaten 1 --ursprunge 4 --ziel build/cortex

# Die Arme (Beispiele; Ausgabe: ein JSON je Lauf + cortex-tafel.txt)
python -m werkzeug.cortex_tafel --kern /tmp/kern --sim klassisch \
    --saaten 1 2 3 4 5 --ursprunge 4 5 6 7 --modell llama3.2:1b \
    --agenten comfort --ziel build/cortex/a-1b
python -m werkzeug.cortex_tafel --kern /tmp/kern --sim klassisch \
    --saaten 1 2 3 --ursprunge 4 5 6 7 --modell llama3.2:3b \
    --agenten comfort,safety --ziel build/cortex/c-veto
python -m werkzeug.cortex_tafel --kern /tmp/kern \
    --casas daten/casas --ursprunge 4 5 6 --modell llama3.2:1b \
    --agenten comfort --ziel build/cortex/e-casas
```

Ohne Ollama läuft `--trocken` (Drehbuch statt Modell); mit Ollama sind die
Modelle `llama3.2:1b`/`llama3.2:3b` lokal, es geht **kein** Byte nach
draußen. Der CI-Job `cortex-tafel-trocken` (bei MRs manuell zu starten)
fährt den Anschluss in der belegten Umgebung: Kern als Checkout, kein
Netz, keine GPU.
