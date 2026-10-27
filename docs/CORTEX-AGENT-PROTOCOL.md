# KONTINUUM Cortex — Protokoll für externe KI-Agenten

## Zweck

`kontinuum.cortex_context` liefert einen kleinen, versionierten Kontextvertrag für einen externen Assistenten (zum Beispiel einen Home-Assistant-MCP-Agenten). Er ist bewusst **rein lesend**: kein LLM-Aufruf, keine Gehirnänderung, keine Serviceausführung und kein vollständiger Export von `brain.json`.

## Kontext abfragen

Rufe den Home-Assistant-Service `kontinuum.cortex_context` mit Antwortanforderung auf (bei der WebSocket-API: `return_response: true`). Die Antwort hat das Schema `kontinuum.agent_context.v1`. Lese zuerst `system`, `brain`, `cortex`, `action_options` und `agent_contract`. Unbekannte zukünftige Felder sind zu ignorieren; bei einem unbekannten `schema` darf ein Agent keine Schreibaktion ableiten.

Der Kontext enthält absichtlich nur kleine, ausgewählte Kennzahlen, höchstens fünf Top-Vorhersagen und maximal zehn Aktionsoptionen. Er enthält keine Personen-Tracker-Liste, keine API-Schlüssel, System-Prompts, Rohverläufe oder den vollständigen Gehirnexport. Home-Assistant-Entity-IDs können allerdings benutzerdefinierte Namen enthalten. `resource_profile.llm_calls` ist bei diesem Service immer null.

## Was ein Agent tun darf

- Den aktuellen Betriebsmodus, Lernstand und die vom Cortex gemeldeten Fähigkeiten erklären.
- Konkrete Vorschläge anhand der gelieferten Evidenz machen, Unsicherheit nennen und nötige Diagnosefragen stellen.
- Dem Nutzer erklären, welche der vom Gehirn angebotenen Optionen zur Debatte stehen.
- Auf ausdrücklichen Wunsch `kontinuum.cortex_consult` für eine Cortex-Beratung oder `kontinuum.brain_review` für eine Lernanalyse anstoßen. Beide können Modellressourcen verbrauchen; eine Beratung kann den normalen Aktionspfad erreichen.

## Verbindliche Grenzen

1. Eine Option in `action_options` bedeutet **nicht**, dass die Aktion bereits freigegeben ist. Sie ist nur eine aktuelle, aus den Vorhersagen gebildete Auswahl.
2. Niemals eine Home-Assistant-Geräteaktion direkt ausführen, um einen Cortex-Vorschlag umzusetzen. KONTINUUM muss seine normalen Betriebsmodus-, Freischaltungs-, Risiko- und Bestätigungsprüfungen anwenden.
3. `shadow`, `confirm` und `active` sind unterschiedliche Berechtigungsmodi. Niemals den Modus wechseln oder Gerätetypen freischalten, nur um eine Empfehlung umzusetzen. Dafür ist eine explizite Nutzeranweisung erforderlich.
4. `kontinuum.confirm_action` und `kontinuum.reject_action` verändern den Zustand bzw. das Lernen. Sie sind nur nach eindeutiger Nutzerentscheidung aufzurufen.
5. `kontinuum.export_brain` ist kein Standardweg für Agent-Kontext. Nutze den kleinen Kontextservice, außer der Nutzer verlangt ausdrücklich einen vollständigen Export und versteht dessen Umfang.
6. Wenn keine ausführbare Option vorhanden ist, widersprüchliche Daten vorliegen oder Sicherheit nicht klar ist, lautet das Ergebnis: erklären, nachfragen oder nichts tun.

## Ressourcenregeln

- Zuerst immer den Kontextservice benutzen; er hat null LLM-Aufrufe.
- `cortex_consult` nur bei konkreter Fragestellung und nicht in Schleifen auslösen.
- `brain_review` nur bei Bedarf oder auf Nutzerwunsch ausführen.
- Bei lokalem Ollama auf einer einzelnen CPU/GPU den sequentiellen Modus bevorzugen; Mehrfachaufrufe parallelisieren nicht automatisch das Denken besser.
- Kein Polling im Sekundentakt. Kontext nur bei einer Nutzerfrage, nach einem relevanten Ereignis oder bei gezielter Fehlersuche abrufen.

## Interpretationshinweise

- `brain.predictions` sind Vorhersagen der Engine, keine Gewissheit.
- `brain.risk` und `brain.prediction_accuracy` sind Messwerte und sollten mit ihrem Kontext erklärt werden.
- `capabilities.request_consultation.may_enter_action_pipeline` bedeutet, dass die Konfiguration und der Betriebsmodus den weiteren Weg beeinflussen. Es ist kein Hinweis, die Aktion direkt auszuführen.
- `privacy` und `agent_contract` sind maschinenlesbare Leitplanken, keine Ersatz-Autorisierung für Home-Assistant-Zugriffsrechte.

## Mini-Beispiel für einen Agenten

1. `kontinuum.cortex_context` mit Antwortanforderung abfragen.
2. `schema` prüfen und danach Betriebsmodus, Risiko, Lernstand und Kandidaten erklären.
3. Bei einer reinen Statusfrage keinen LLM-Dienst aufrufen.
4. Bei einem komplexen Analysewunsch erklären, dass eine Cortex-Beratung Modellressourcen nutzt, und sie nur im Rahmen der Nutzeranfrage starten.
5. Vor jeder Änderung sicherstellen, dass der Nutzer genau diese Änderung autorisiert hat; KONTINUUM-Sicherheitsprüfungen niemals umgehen.
