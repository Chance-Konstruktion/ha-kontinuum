# KONTINUUM – vollständige Review-Sitzung / Claude-Handover

**Sitzungs-ID:** KONTINUUM-AUDIT-2026-10-26  
**Stand:** 26. Oktober 2026  
**Primärer Review-PR:** ha-kontinuum, Branch review/kontinuum-audit-claude-2026-10-26  
**Zweck:** Review-Befunde nachvollziehbar festhalten, konkrete Fixes mit Regressionstests bereitstellen und offene Integrationsfragen an Claude übergeben. Bitte vor einem Merge jeden Befund am aktuellen Branch und gegen die vollständigen Aufrufpfade verifizieren.

## 1. Auftrag und Abgrenzung

Ziel ist ein belastbarer technischer Review des KONTINUUM-Verbunds: Home-Assistant-Integration Pro, HA-unabhängiger Core, die Lite-Integration und ergänzend das Anomaly-Paket. Schwerpunkte sind Entscheidungs-/Lernfluss, Provider- und Agentenverträge, Serviceausführung, Lifecycle, Persistenz, Testqualität sowie eine mögliche MCP-Anbindung für ChatGPT.

Jedes Repository hat seinen eigenen Draft, damit Verträge und Tests dort geprüft werden, wo der Code liegt: [Pro PR #93](https://github.com/Chance-Konstruktion/ha-kontinuum/pull/93), [Core PR #42](https://github.com/Chance-Konstruktion/kontinuum-core/pull/42), [Lite PR #26](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/pull/26) und [AI-anomaly PR #19](https://github.com/Chance-Konstruktion/kontinuum-AI-anomaly/pull/19). Pro behält den Media-Adapter als Kompatibilitätsfallback für ältere Core-Pakete. Der vom Nutzer bestätigte Core-Link ist das GitHub-Repository; die Änderungen sind daher direkt auf dessen Draft-Branch vorbereitet.

Diese Sitzung ist ein tiefgehender statischer Review der zentralen Produktionspfade, aber **keine formale Zeile-für-Zeile-Verifikation jedes einzelnen Files** und kein Beleg für einen erfolgreich lokal ausgeführten Testlauf. Die Teständerungen sind vorbereitet; die CI dieses PRs muss ihre Ausführung bestätigen.

## 2. Repositories und geprüfte Basisstände

- **ha-kontinuum (Pro):** main bei d241e2d3a5c42e174670261507e7bddf2408d5f3. Geprüft wurden insbesondere HA-Einstiegs-/Abbaupfade, Cortex-Orchestrierung, Organ-Menü und Abstimmung, Config Flow/Agentenschlüssel, Diagnostics, Persistenz- und Lifecycle-Tests, Manifest und Workflows.
- **kontinuum-core:** main bei 99e754ff9d91cffcbdbb4f9450af6c7a16376888. Geprüft wurden Engine-Pipeline, Thalamus, Prefrontal Cortex, LLM-Datenvertrag, Assoziationskortex, Persistenzversionierung, Pipeline-Dokumentation und Messprotokoll/Testmatrix.
- **ha-kontinuum-lite:** main bei 016df098d6800be3a5dafbe106169e9a6f54829c. Geprüft wurden LiteEngine-Projektion, Entscheidungskonvertierung, Setup/Teardown, Services, Save/Restore und Core-Vertragstests.
- **kontinuum-AI-anomaly:** main bei 3ce176ff087aa23f44d46036e867bda74b5991e1. Ergänzend geprüft wurden README, dokumentierte Grenzen, API-/Scoring-Dokumentation und Testsuite-Struktur.

**Aktuelle CI (26.10.2026) auf den zuletzt geprüften Code-Heads:**
- Pro: Smoke Test [40404746827](https://github.com/Chance-Konstruktion/ha-kontinuum/actions/runs/40404746827), HACS [40404746714](https://github.com/Chance-Konstruktion/ha-kontinuum/actions/runs/40404746714), hassfest [40404746660](https://github.com/Chance-Konstruktion/ha-kontinuum/actions/runs/40404746660) — erfolgreich auf Code-Head `9768f28` (inklusive HVAC-Modus-Erhalt und dessen Regressionstests).
- Core: Pytest-Matrix Python 3.9–3.12 und Replay-Benchmark [40403178227](https://github.com/Chance-Konstruktion/kontinuum-core/actions/runs/40403178227) — erfolgreich auf Head `a564370` (native HVAC-Modi und Alias-Normalisierung).
- Lite: Pytest [40403589036](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/actions/runs/40403589036), hassfest [40403588569](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/actions/runs/40403588569), HACS [40403588856](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/actions/runs/40403588856) — erfolgreich auf Head `d30b83c` (ID-Round-trip sowie Legacy Media-/Climate-Servicevertrag).
- AI-anomaly: volle Matrix Core 0.6.0/0.6.3 für Python 3.9–3.12, Ruff, Mypy, Build und Twine-Check [40402621954](https://github.com/Chance-Konstruktion/kontinuum-AI-anomaly/actions/runs/40402621954) — erfolgreich auf Head `82ee3caa`; zusätzlich Path-Traversal-Schutz, Zero-Retention-/Persistenz- und Sink-Retry-Tests.

Die Pro-Läufe beziehen sich auf den Code-Head; der Dokumentationscommit mit dieser Aktualisierung löst neue CI-Läufe aus. Für einen Merge muss der neueste Head erneut grün sein. Die vollständige HA-Plugin-Testsuite für Pro wird vom Smoke-Workflow explizit nicht abgedeckt.

## 3. Änderungen in diesem PR

### Commit 1 — Cortex-Menüwahl korrekt in Lernsignale überführen

Dateien: **custom_components/kontinuum/cortex.py**, **tests/test_cortex_bridge.py**

- Das aktuelle Organ-Ergebnis ordnet jeder Agentenstimme nun die tatsächlich gewählte Menüoption zu: Aktion, Entity-ID, Wahl-ID, Gültigkeit und Veto-/Streichliste.
- Die Prefrontal-Utility-Rückmeldung zählt Stimmen über die Menü-ID und nicht über das alte Freitextfeld action, das im Organ-Modus leer war.
- Individuelle Safety-Vetos bleiben als Lernsignal erhalten, auch wenn eine andere, nicht gestrichene Option gewählt werden kann.
- Die Tests prüfen sowohl Konsens-/Feedback-Lernen als auch Veto-Verarbeitung. Ein einzelnes beobachtetes Muster wird nicht fälschlich als bereits fertiger Reflex gewertet.

### Commit 2 — Agentenprompt, Provider-Timeout und Entladen

Dateien: **custom_components/kontinuum/cortex.py**, **custom_components/kontinuum/__init__.py**, **tests/test_aufbau_abbau.py**, **tests/test_cortex_bridge.py**, **tests/test_cortex_provider_contract.py**

- Organ-Modus enthält jetzt tatsächlich konfigurierte, benutzerdefinierte Agentenhinweise. Sie werden als Domänenhinweise vor die verbindliche Menü-/JSON-Ausgaberegel gesetzt, damit die freie Action-Schema-Anweisung nicht das eingeschränkte Menüformat verdrängt.
- Die alten eingebauten DEFAULT_PROMPTS werden nicht noch einmal als widersprüchlicher Freitext in den Organ-Modus hineinkopiert; sie bleiben beim bisherigen Legacy-think-Pfad unverändert.
- Konfigurierbare Request-Timeouts werden an OpenAI-/Grok-/Custom-kompatible, Claude- und Gemini-Aufrufe weitergereicht. Vorher waren diese HTTP-Clients auf 30 Sekunden festgelegt, auch wenn der Agent einen anderen Timeout angab.
- Cortex.close() läuft nun auch beim regulären Unload/Options-Reload, nicht nur beim Home-Assistant-Stop-Event.
- Tests decken benutzerdefinierte Hinweise, Provider-Timeout-Weitergabe und das Session-Cleanup im echten Lifecycle-Test ab.

### Commit 3 — Media-Service-Domain an der HA-Grenze normalisieren

Dateien: **custom_components/kontinuum/__init__.py**, **tests/test_service_domain_mapping.py**

- KONTINUUM-Token verwenden die Semantik media; Home Assistant registriert die Services aber unter media_player. Die Core-Service-Spezifikation kann daher aktuell den ungültigen Domainnamen media liefern.
- Pro normalisiert diesen einen Service-Domainnamen zentral an der HA-Grenze und nutzt die Funktion sowohl bei PFC-Ausführung als auch bei Cortex-Validierung.
- Der Adapter kopiert das Service-Dict statt ein vom Core geliefertes Objekt in-place zu verändern.
- Die gemeinsame Korrektur liegt als [Core-GitHub-Draft #42](https://github.com/Chance-Konstruktion/kontinuum-core/pull/42) vor; [Lite-Draft #26](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/pull/26) erhält zusätzlich die optionale `token_id` aus Core-Snapshots. Beide GitHub-Drafts müssen noch mit der kanonischen GitLab-Core-Quelle abgeglichen und dort separat übertragen werden.

### Commit 4 — Prompt-Zeilenumbrüche

Datei: **custom_components/kontinuum/cortex.py**

- Die zusammengesetzten Promptabschnitte werden mit tatsächlichen Zeilenumbrüchen verbunden, nicht mit sichtbaren Literal-Sequenzen.

### Commit 5 — Veto von fehlender Mehrheit unterscheiden

Dateien: **custom_components/kontinuum/cortex.py**, **tests/test_cortex_bridge.py**

- vetoed ist nur dann wahr, wenn die Vetos alle ausführbaren Menüoptionen ausschließen.
- Ein fehlender absoluter Mehrheitsentscheid wird nicht allein deshalb als Veto markiert, weil im gleichen Beratungszyklus irgendein Kandidat gestrichen wurde.
- Das einzelne Veto bleibt separat sichtbar und lernbar.

## 4. Bestätigte Befunde und aktueller Status

### A. Cortex-Bridge war nicht mehr konsistent zum Organ-Ausgabeformat — im PR behoben

Der aktuelle Beratungsweg wählt nummerierte Menü-IDs; die alte Bridge suchte aber nach Freitext-Action-Übereinstimmungen und einem booleschen Veto im älteren Format. Dadurch konnten die eigentliche Beratung und die vorgesehene Rückmeldung an Prefrontal/Amygdala auseinanderlaufen. Die neue Normalisierung macht das Datenformat an einer Stelle explizit und deckt es mit Regressionstests ab.

**Claude soll prüfen:** Sind Aktion und Entity immer aus demselben Menüeintrag abgeleitet? Sind ungültige Stimmen aus dem Feedback-Nenner ausgeschlossen? Löst ein Veto nur die vorgesehenen Lernfolgen aus? Ist die Bedeutung von vetoed jetzt eng genug?

### B. Media-Player-Service-Domain — Core behoben, Pro/Lite haben Legacy-Fallbacks

Core gruppiert `media_player`-Entities in der Token-Semantik `media`. Der Core-PR bildet diese Semantik nun auf die echte HA-Service-Domain `media_player` ab. Pro und Lite behalten defensive Adapter für ältere installierte Core-Versionen, die noch `domain="media"` zurückgeben.

**Claude soll prüfen:** Ob der Servicevertrag bei allen Aufrufern konsistent ist und die Legacy-Fallbacks nach Veröffentlichung einer Core-Version mit dem neuen Vertrag später wieder entfernt werden können.

### C. HVAC-Modus ging beim Cortex-Service-Reverse-Mapping verloren — im Verbund behoben

Der Thalamus liefert native HA-Zustände wie `heat`, `cool`, `heat_cool`, `auto`, `dry` und `fan_only`. Core mappte vorher nur `heating`/`cooling` und `off`; zudem verwenden mehrere HVAC-Modi denselben HA-Service `climate.set_hvac_mode`. Ein reines Reverse-Mapping vom Service zum Token kann daher den gewählten Modus verlieren oder falsch rekonstruieren.

- Core mappt jetzt native HVAC-Modi auf `climate.set_hvac_mode` und normalisiert die Legacy-Aliase `heating`/`cooling` auf die gültigen HA-Modi `heat`/`cool`.
- Das Organ-Menü kann native Modus-Tokens auch bei älteren Core-Service-Maps behalten.
- Der Konsens trägt das exakte gewählte `consensus_token` durch die Pro-Brücke. Die Ausführung validiert Token, Aktion, Entity-Semantik und Raum gemeinsam; ein mehrdeutiger HVAC-Service ohne Token wird abgelehnt statt geraten.
- Pro bestätigt in der Notification den konkreten gewählten Zustand; die Lern-/Reflex-Brücke bewahrt den Token für HVAC, statt alle Modi unter `climate.set_hvac_mode` zusammenzufassen.
- Lite normalisiert alte Media-/Climate-Serviceverträge sowohl in der direkten Serviceausführung als auch beim Ausführen bereits wartender Bestätigungen.

Regressionstests liegen in Core `test_prefrontal_contract.py`, Pro `test_cortex_organ.py`, `test_cortex_bridge.py`, `test_service_domain_mapping.py` und Lite `test_core_contract.py`.

**Claude soll prüfen:** Dass ein UI- oder Modellkonsens ohne exakten Modus niemals eine HVAC-Aktion auslösen kann und dass die tatsächliche Bestätigungs-/Active-Pipeline denselben Token ausführt, den das Menü ausgewählt hatte.

### D. Benutzerdefinierte Agentenprompts waren im Organ-Modus nicht wirksam — im PR behoben

CortexAgent.waehle() nutzte bislang nur organ_prompt(self.name), nicht self.system_prompt. Ein gespeicherter nutzerdefinierter Prompt beeinflusste daher den aktuellen, menügebundenen Beratungsweg nicht. Die Lösung fügt echte benutzerdefinierte Hinweise ein, bewahrt aber das Menü als einzige Quelle erlaubter Aktionen und das festgelegte Ausgabeschema.

**Claude soll prüfen:** Ist die Trennung zwischen Legacy-think und Organ-Modus klar genug? Sollten Config-Flow-Labels ausdrücklich sagen, dass frei formulierte System-Prompts als fachliche Hinweise dienen und die Ausgabeform nicht ändern können?

### E. Timeout-Konfiguration wurde für Cloud-Provider nicht durchgereicht — im PR behoben

Ollama erhielt den vom Agenten angegebenen Timeout. OpenAI-kompatible Endpunkte, Claude und Gemini verwendeten dagegen fest 30 Sekunden. Der gemeinsame Dispatcher und die HTTP-Wrapper reichen den Wert nun durch.

**Claude soll prüfen:** Ob der Retrypfad für HTTP 429 und Retry-After später erweitert werden soll. Aktuell sind die Retry-Regeln für 5xx und bestimmte Netzwerkfehler definiert; eine Rate-Limit-Antwort sollte nicht blind sofort wiederholt werden, sondern begrenzt und mit Provider-Hinweisen behandelt werden.

### F. Cortex HTTP-Session bei Reload/Unload — im PR behoben

Die Session wurde explizit beim Home-Assistant-Stop geschlossen, nicht aber im regulären Options-Reload-/Unload-Pfad. Das konnte eine alte ClientSession länger leben lassen als den Config Entry. Der echte Setup-/Teardown-Test erhält nun einen Close-Spy.

**Claude soll prüfen:** Ob Cortex.close() bei mehrfachem Aufruf sicher idempotent bleibt und ob weitere Background-Tasks neben der Session an den Entry-Lifecycle gebunden werden müssen.

### G. Inaktive `discussion_rounds`-Einstellung — in diesem PR transparent stillgelegt

Der Config Flow bot bisher 1–3 Diskussionsrunden an, während der aktive Organ-/Menüpfad nur eine Wahl pro Fach-Agent ausführt. Der Coordinator wird nicht gefragt und es findet keine Revisionsrunde statt. Ein UI-Schalter ohne Effekt war irreführend.

- Das editierbare Feld ist aus dem Config Flow entfernt.
- Bereits gespeicherte `discussion_rounds`-Werte bleiben als Legacy-Konfigurationsdaten erhalten; sie werden nicht mehr als wirksame Einstellung behandelt.
- Cortex-State, Sensor und Diagnostics berichten die effektive Ein-Runden-Politik. Tests halten fest, dass alte Snapshots mit `discussion_rounds=3` nicht fälschlich drei effektive Runden melden.

Ein echter Mehr-Runden-/Coordinator-Modus ist **nicht** beiläufig reaktiviert worden. Er braucht ein separates Design, ein explizites Opt-in und Tests gegen Prompt-Injektion, Veto-Priorität, sichere Enthaltung, Mehrdeutigkeit und Gruppendenken.

## 5. Weitere Befunde aus Core, Lite und Anomaly

### kontinuum-core

- **Gute Architektur:** HA-freier Core, versionierter LLM-Kontextvertrag, defensive Normalisierung externer JSON-Antworten, Round-trip-Persistenz und eine explizite Vorhersage-vor-Lernen-Pipeline. EngineSnapshot bietet Diagnostik für gefilterte/unregistrierte Ereignisse statt nur scheinbarer Untätigkeit.
- **Messqualität:** Das Messprotokoll vergleicht Engine mit B0/B1/B2-Baselines und enthält reale CASAS-Spuren. Die dokumentierte Vorhersageverbesserung ist aussagekräftiger als ein isolierter Accuracy-Wert. Es gibt jedoch bewusst dokumentierte Schwächen, insbesondere eine problematische Tulum1-Anwesenheitsperiode. Anwesenheitsschätzungen müssen Unsicherheit und Kalibrierung mitliefern und dürfen nicht als sichere Fakten behandelt werden.
- **Token-Kollisionen:** Ein Token bildet Raum + Semantik + Zustand ab, nicht die einzelne Entity. Mehrere ähnliche Entitäten im Raum werden dadurch zusammengefasst. Das ist ein bewusster Speicherkompromiss, muss aber in Nutzungsdokumentation und Debugging sichtbar bleiben.
- **Persistenz-/Upgrade-Vertrag:** Schema-Version und Modulsammlung funktionieren grundsätzlich als Kompatibilitätsmechanismus; Claude sollte besonders Migration von älteren Brain-Snapshots und Verhalten bei neuerem Schema weiter testen.
- **Im Core-GitHub-Draft umgesetzt:** Service-Domain und Token-Semantik werden im [Core-PR #42](https://github.com/Chance-Konstruktion/kontinuum-core/pull/42) entkoppelt; die Tests umfassen Media-Service-Domain, native HVAC-Modi, Alias-Normalisierung, eindeutige Confirm-IDs und den Snapshot-Tokenvertrag.

### ha-kontinuum-lite

- **Gute Architektur:** Dünne HA-Schicht über KontinuumEngine, atomisches gzip-Speichern mit temporärer Datei und os.replace, Executor für blockierende Dateioperationen, Bestätigungsweg und Lifecycle-Tests.
- **Im Lite-GitHub-Draft umgesetzt:** Lite rekonstruiert Entscheidungen mit optionalem `token_id`, bleibt mit älteren Core-Snapshots kompatibel und fängt `OverflowError`/nicht-endliche Eingaben ab. Serviceaufrufe und bereits wartende Confirm-Entscheidungen behalten auch bei älterem Core gültige Media-/Climate-Modi ([Lite-PR #26](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/pull/26)). Der [Core-PR #42](https://github.com/Chance-Konstruktion/kontinuum-core/pull/42) exportiert `token_id`, macht Confirm-IDs kollisionsresistent und mappt native HVAC-Modi.
- **Shared Media-Bug — Fix auf Core:** Core mappt die Media-Semantik auf `media_player`, worauf auch Lite aufsetzt. Der Pro-Adapter bleibt als Fallback für ältere Core-Pakete.
- **Restore-Randfall:** Der Core verweigert das Laden eines neueren Schema-Standes durch Cold-Start. Claude sollte prüfen, ob Lite den Unterschied zwischen „Datei war vorhanden und bewusst abgelehnt“ und „Brain erfolgreich restauriert“ in Status/Logging deutlich genug macht.

### kontinuum-AI-anomaly

- **Gute Abgrenzung:** Das Paket beschreibt sich als externen Monitor und nicht als Agententrainer. Neuheit wird als starker Anomaliefall dargestellt; schwächere Sequenzanomalien und die Kaltstartphase sind dokumentiert statt verborgen.
- **Skalierungsrisiko:** Unbeschränkte Stream-IDs, wenn variable Werte wie user_8123 in Aktionsnamen kodiert werden, können dauerhafte Zustände erzeugen und Speicher wachsen lassen. Die README warnt davor und empfiehlt variable Details getrennt vom Action-Token zu übergeben.
- **Konkrete Fehler + Fix im Draft:** [AI-anomaly PR #19](https://github.com/Chance-Konstruktion/kontinuum-AI-anomaly/pull/19) behebt die Zero-Cap-Bugs in History und Cross-Stream-Korrelation, erzwingt Retention auch auf der Platte beim Laden, erzeugt fehlende Elternverzeichnisse für Brain/History/Recurrence, setzt sicheres Dateinaming für externe Agent-IDs gegen Path-Traversal durch, meldet Zustellung nur bei erfolgreicher Sink, arm't keinen Cooldown nach vollständigem Fehlschlag, dedupliziert dieselbe Sink-Instanz, verhindert dass Warning-Cooldown einen Critical-Pager unterdrückt, retried fehlgeschlagene Pager trotz erfolgreichem Log-Sink, isoliert Exceptions benutzerdefinierter Sinks, ergänzt threshold/strategy/detail in generischen Webhook-Payloads, validiert Webhook-Ziel und Timeout und ignoriert verspätete Recurrence-Ereignisse außerhalb des Ringfensters. Die aktuelle komplette CI-Matrix ist auf Head `82ee3caa` erfolgreich ([Run 40402621954](https://github.com/Chance-Konstruktion/kontinuum-AI-anomaly/actions/runs/40402621954)).
- **Integration:** Als optionaler Agentenwächter sollte das Paket einen klaren, versionierten Event-Vertrag und kontrollierte Alert-Sinks verwenden. Es bleibt ein externer Beobachter und ändert nicht den Core-Lernpfad.

## 6. MCP / ChatGPT: empfohlene Architektur

Die Architekturentscheidung sollte zwei Wege auseinanderhalten:

1. **ChatGPT nutzt KONTINUUM als Werkzeug (MCP):** Ein separater MCP-Server bzw. eine Bridge ruft die autorisierten HA-/KONTINUUM-Schnittstellen auf. ChatGPT kann Status, Prognosen, Anomalien und den Grund einer Empfehlung abfragen. Ein MCP-Server ist kein Modell-Endpunkt und verwandelt einen ChatGPT-Agenten nicht in eine OpenAI-kompatible Chat-Completions-API.
2. **Cortex nutzt einen externen Agenten als Provider:** Der vorhandene Custom-Provider kann bereits mit OpenAI-kompatiblen Endpunkten sprechen. Ein Agent, der nur MCP spricht, benötigt daher einen Adapter; ein ChatGPT-Abo erzeugt nicht automatisch einen beliebigen Chat-Completions-Endpunkt.

### Empfohlene MVP-Tools

Nur lesende Werkzeuge zuerst:
- **kontinuum.status:** Core-/Integrationsversion, Lernreife, Tracking-/Filterzahlen, Betriebsmodus und Persistenzstatus.
- **kontinuum.predictions:** begrenzte Top-K-Vorhersagen mit Quelle, Konfidenz und Begründung.
- **kontinuum.anomalies:** jüngste Anomalie-Aggregate und Überraschungssignal, keine ungebremsten Roh-Entity-Zustände.
- **kontinuum.presence:** Lagebild-Wahrscheinlichkeit und ihre wichtigsten Belege, klar als Schätzung markiert.
- **kontinuum.cortex.consult:** eine beratende Sitzung auslösen und Ergebnis zurückliefern; keine HA-Aktion direkt aus dem Agentenreply ausführen.
- **kontinuum.history.summary:** begrenzte, datensparsame, aggregierte Historie.

Schreibpfad erst später: **propose_action** soll eine bekannte Option in den vorhandenen KONTINUUM-Bestätigungsfluss stellen. Es sollte keinen generischen call_service(domain, service, arbitrary_data)-MCP-Tool geben. Die endgültige Ausführung muss weiter serverseitig validiert werden und in der konfigurierten Betriebsart bleiben.

### Sicherheit und Betrieb

- Remote-MCP nur über HTTPS plus OAuth oder gleichwertig gesicherte, kurzlebige Identität; pro HA-Installation getrennte Authentifizierung, Berechtigungen und Audit-Spur.
- Home Assistant nicht mit einem breit berechtigten, langfristigen Token ungeschützt ins öffentliche Internet stellen. Wenn HA/MCP lokal oder privat läuft, einen unterstützten Secure MCP Tunnel oder einen kontrollierten, ausgehenden Gateway-Weg prüfen, statt eine private Instanz offen freizugeben.
- Allowlist für Tools, Entities und zulässige Actions; begrenzte Ergebnisgrößen, Timeouts, Rate-Limits, Idempotency Keys und Fehlercodes.
- Haushaltsdaten, Namen, Präsenz und rohe State-Attribute minimieren. Externe Zustände sind Daten, keine vertrauenswürdigen Instruktionen; Prompt-Injection-Risiken müssen Teil des Tests sein.
- Write-Tools in UI/Server getrennt von Read-Tools aktivieren, vor gefährlichen Aktionen Bestätigung verlangen, jede Aktion samt Grund und Ergebnis protokollieren.
- Zuerst reine Leserechte testen; danach Preview/Proposal; erst nach Sicherheitsreview kontrollierte Confirm-Aktionen.

### Aktuelle ChatGPT-Kompatibilität

Die offizielle OpenAI-Dokumentation sagt, dass ChatGPT-Apps über benutzerdefinierte Remote-MCP-Server eingebunden werden können. Volle MCP-Unterstützung einschließlich Schreibaktionen wird derzeit für Business sowie Enterprise/Edu angeboten; Pro kann benutzerdefinierte MCP-Server mit Lese-/Abrufrechten verbinden. Ein lokaler oder privater Server ist nicht direkt als Internet-Endpunkt erreichbar; für unterstützte Produkte wird Secure MCP Tunnel genannt. Vor einer Produktentscheidung sind Konto-/Workspace-Berechtigungen erneut zu prüfen.

Referenzen:
- OpenAI Help Center, Custom MCP Server in ChatGPT: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- OpenAI API Guide, Custom MCP Server: https://developers.openai.com/api/docs/guides/custom-mcp-server
- OpenAI API Guide, MCP servers and Secure MCP Tunnel: https://developers.openai.com/api/docs/guides/tools-connectors-mcp

## 7. Test- und Review-Checkliste für Claude

Bitte nicht nur diesen Markdown-Bericht bestätigen; Code und Tests unabhängig prüfen:

1. Den gesamten Diff dieses Branches lesen und die Aufrufpfade für Pro-Serviceausführung, Cortex-Konsens und Unload verfolgen.
2. CI vollständig laufen lassen: vorhandene Pro-Testpipeline inklusive pytest-homeassistant-custom-component, Smoke-Import, HACS Validate und hassfest.
3. Sicherstellen, dass Provider-Tests kein echtes Netzwerk benötigen und timeout.total auf allen drei Cloud-Transporten überprüfen.
4. Prüfen, dass organ_prompt bei Custom-Prompts den Vertrags-/Menütext am Ende belässt und eingebauter Legacy-JSON-Text keine widersprüchliche neue Antwortform einführt.
5. Prüfen, dass ein Veto auf der individuellen Stimme erhalten bleibt, aber das boolesche vetoed nur aussagt, dass sämtliche ausführbaren Optionen ausgeschlossen wurden.
6. Pro Media-/Climate-Adapter prüfen und mit [Core PR #42](https://github.com/Chance-Konstruktion/kontinuum-core/pull/42) sowie [Lite PR #26](https://github.com/Chance-Konstruktion/ha-kontinuum-lite/pull/26) gegen den realen Call-Path vergleichen. Sicherstellen, dass der exakte HVAC-Token Konsens, Bestätigung, Ausführung und Outcome-Lernen überlebt.
7. Die Verträge über alle vier PRs gemeinsam prüfen: Core-Service-Domain und Confirm-ID, Lite-Decision-Rekonstruktion, Pro-Kompatibilitätsadapter und AI-anomaly Alert-/Retention-Fixes. Prüfen, dass die installierten Core-Versionen in Pro/Lite/Anomaly mit dem veröffentlichten Core-Vertrag kompatibel bleiben.
8. Prüfen, dass `discussion_rounds` im UI nicht mehr als wirksam erscheint und Legacy-Werte bei Migration/Restore die effektive Ein-Runden-Politik nicht überschreiben. Coordinator/Revisionsmodus separat designen.
9. MCP vorerst als gesondertes Architektur-/Sicherheitsprojekt behandeln; kein Netzwerkserver mit Schreibrechten als beiläufiger Zusatz zu diesem Code-PR.

## 8. Akzeptanzkriterien

- Der Pro-PR bleibt ohne Änderung an main; es wird nichts automatisch gemergt.
- Jeder Funktionsfix hat einen Regressionstest.
- Das CI-Ergebnis dieses konkreten PRs ist grün, bevor er für Merge empfohlen wird.
- Alle vier PRs betreffen das bestätigte GitHub-Projekt; jeder PR muss seinen eigenen grünen CI-Lauf sowie das unabhängige Review erhalten.
- Ein MCP-Pilot startet read-only und macht den bestehenden Confirm-/Active-Modus nicht durch eine zweite, schwächere Ausführungsroute wirkungslos.

**Status dieser Sitzung (26.10.2026):**
- Letzter vollständig grüner Pro-Code-Head vor der Config-Bereinigung: `9768f28`; Core `a564370`, Lite `d30b83c` und AI-anomaly `82ee3caa` haben die verlinkten CI-Prüfungen bestanden. Die danach vorgenommenen Pro-Änderungen (consensus-token/HVAC-End-to-End und Stilllegung von `discussion_rounds`) lösen neue Pro-CI-Läufe aus; vor Merge ist der jeweils aktuelle Head zu prüfen.
- Vollständige Pro-Pytest-Suite einschließlich HA-Testplugin: **noch nicht bestätigt**. Die GitHub-Smoke-Workflow-Datei schließt Tests aus, die `pytest_homeassistant_custom_component` importieren; insbesondere der Lifecycle-Test für Session-Cleanup muss in der vollständigen HA-Testumgebung ausgeführt werden.
- Claude wurde auf allen vier PRs um unabhängiges Review gebeten. In der letzten Prüfung war noch keine Claude-Antwort bzw. kein Review-Submission sichtbar.
- Alle vier PRs sind Drafts und ungemergt.
