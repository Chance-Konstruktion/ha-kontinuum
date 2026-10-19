/* KONTINUUM: natives Panel der Integration "kontinuum".
 * Eine Datei, reine Web Components, kein Build, keine fremden Quellen, keine eigenen Schriften.
 * Home Assistant reicht hass, narrow, route und panel herein; Daten und Dienste laufen
 * über hass.connection / hass.callService, es gibt keine eigene Anmeldung und keine Tokens.
 *
 * Datenweg: das serverseitig gefilterte Abo "kontinuum/abonniere" (zustands_abo.py) über
 * hass.connection.subscribeMessage. Scheitert das Abo, liest das Panel ersatzweise
 * hass.states (derselbe Filter, ehrlich im Aktivitätslog gemeldet).
 */
"use strict";

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const num = (x) => (typeof x === "number" && Number.isFinite(x) ? x : Number(x) || 0);
const fix = (x, n) => num(x).toFixed(n);
const prozent = (x) => `${fix(num(x) * 100, 0)}%`;
const def = (tag) => typeof customElements !== "undefined" && !!customElements.get(tag);
const uhrzeit = () => new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/* ---------- Sensoren finden (unabhängig von der entity_id, wie bisher) ---------- */
const SENSOR_ALIASES = {
  status: ["sensor.kontinuum_status"],
  last_event: ["sensor.kontinuum_last_event", "sensor.letztes_event"],
  prediction: ["sensor.kontinuum_prediction", "sensor.vorhersage"],
  accuracy: ["sensor.kontinuum_accuracy"],
  energy: ["sensor.kontinuum_energy", "sensor.energie"],
  location: ["sensor.kontinuum_location", "sensor.standort"],
  mode: ["sensor.kontinuum_mode", "sensor.kontinuum_modus"],
  cerebellum: ["sensor.kontinuum_cerebellum", "sensor.cerebellum"],
};
const SENSOR_NAME_PATTERNS = {
  status: ["kontinuum status"],
  last_event: ["last event", "letztes event"],
  prediction: ["prediction", "vorhersage"],
  accuracy: ["accuracy"],
  energy: ["energy", "energie"],
  location: ["location", "standort"],
  mode: ["mode", "modus"],
  cerebellum: ["cerebellum"],
};

/* states: Liste von {entity_id, state, attributes} */
function discoverSensors(states) {
  const found = {}, byId = {};
  for (const s of states) byId[s.entity_id] = s;
  for (const [key, aliases] of Object.entries(SENSOR_ALIASES)) {
    for (const alias of aliases) {
      if (byId[alias]) { found[key] = { state: byId[alias].state, attr: byId[alias].attributes || {} }; break; }
    }
    if (found[key]) continue;
    const patterns = SENSOR_NAME_PATTERNS[key] || [];
    for (const s of states) {
      const name = ((s.attributes && s.attributes.friendly_name) || "").toLowerCase();
      if (patterns.some((p) => name.includes(p))) { found[key] = { state: s.state, attr: s.attributes || {} }; break; }
    }
  }
  return found;
}

const gueltig = (s) => !!(s && s.state && s.state !== "unknown" && s.state !== "unavailable");

/* Zustände aus hass.states, die zu KONTINUUM gehören könnten (Ersatzweg ohne Abo) */
function ausHassStates(states) {
  const liste = [];
  for (const [id, s] of Object.entries(states || {})) {
    if (id.startsWith("sensor.") || id.startsWith("binary_sensor.")) liste.push({ entity_id: id, state: s.state, attributes: s.attributes || {} });
  }
  return liste;
}

/* ---------- Farben: nur Variablen des Themes von Home Assistant ---------- */
/* Die Palette (--cyan-color, --purple-color ...) stellt Home Assistant; fehlt eine, bleibt die Primärfarbe */
const pal = (...namen) => namen.reduceRight((rest, n) => `var(--${n}-color, ${rest})`, "var(--primary-color)");
const FARBE = {
  primary: "var(--primary-color)", ok: "var(--success-color)", warn: "var(--warning-color)", nok: "var(--error-color)",
  cyan: pal("cyan"), violett: pal("deep-purple"), grau: pal("blue-grey"), pink: pal("pink"), orange: pal("orange"),
  bernstein: pal("amber"), lila: pal("purple"), teal: pal("teal"), silber: pal("grey"), indigo: pal("indigo"),
  lime: pal("lime"), tieforange: pal("deep-orange"), akzent: pal("accent"),
};
const TON = { ok: "var(--success-color)", warn: "var(--warning-color)", nok: "var(--error-color)", info: "var(--primary-color)", still: "var(--secondary-text-color)" };

/* Module in der Modulliste: [id, Name, Farbe]; die Farbe ist dieselbe wie im Gehirn */
const MODULE = [
  ["thalamus", "Thalamus", FARBE.primary], ["hippocampus", "Hippocampus", FARBE.lila], ["hypothalamus", "Hypothalamus", FARBE.bernstein],
  ["spatial", "Spatial Cortex", FARBE.ok], ["insula", "Insula", FARBE.pink], ["amygdala", "Amygdala", FARBE.nok],
  ["cerebellum", "Cerebellum", FARBE.teal], ["prefrontal", "Prefrontal", FARBE.cyan], ["basalganglien", "Basalganglien", FARBE.orange],
  ["acc", "Ant. Cingulat (ACC)", FARBE.akzent], ["reticular", "Formatio Reticularis", FARBE.silber], ["accumbens", "Nucleus Accumbens", FARBE.tieforange],
  ["locus", "Locus Coeruleus", FARBE.indigo], ["entorhinal", "Entorhinaler Cortex", FARBE.lime], ["sleep", "Sleep Consolidation", FARBE.indigo],
  ["metaplasticity", "Metaplastizität", FARBE.grau], ["neurorhythms", "Neurorhythmen", FARBE.bernstein],
];

/* ---------- Anzeigewerte aus den Sensoren (reine Funktionen) ---------- */
const LEER = { wert: "—", detail: "—" };

function sensorWerte(d) {
  const a = (k) => (d[k] && d[k].attr) || {};
  const w = {};
  const ev = d.last_event;
  if (gueltig(ev)) {
    const evTotal = a("last_event").events_total || 0;
    w.event = { wert: ev.state, detail: `${a("last_event").room || "?"} · ${a("last_event").semantic || ""} · events: ${evTotal}` };
  } else w.event = ev ? { wert: "warte…", detail: "Noch keine Events verarbeitet" } : LEER;

  const pr = d.prediction, conf = a("prediction").confidence;
  w.pred = gueltig(pr) ? { wert: pr.state, detail: conf != null && conf > 0 ? `confidence: ${fix(conf * 100, 0)}%` : "Sammle Daten…" }
    : pr ? { wert: "warte…", detail: "Braucht mehr Events für Vorhersagen" } : LEER;

  const ac = d.accuracy, aa = a("accuracy");
  w.acc = gueltig(ac) ? { wert: ac.state, detail: `hits: ${aa.hits || aa.shadow_hits || 0} / total: ${aa.total || aa.shadow_total || 0}` } : LEER;

  const nrg = d.energy, na = a("energy");
  w.nrg = gueltig(nrg) ? { wert: nrg.state, detail: `solar: ${na.solar || "?"} · absorbed: ${na.events_absorbed || 0}` }
    : nrg ? { wert: "?", detail: "Keine Energiedaten" } : LEER;

  const loc = d.location, sp = a("location");
  if (gueltig(loc)) {
    let detail;
    if (sp && sp.presence_map) {
      const rooms = Object.entries(sp.presence_map).filter(([, v]) => v && v.occupied).map(([k]) => k);
      detail = rooms.length > 0 ? `besetzt: ${rooms.join(", ")}` : sp.predicted_next ? `nächster: ${sp.predicted_next}` : "kein Raum besetzt";
    } else detail = `patterns: ${sp.movement_patterns || 0}`;
    w.loc = { wert: loc.state, detail };
  } else w.loc = loc ? { wert: "unbekannt", detail: "Warte auf Bewegungsdaten…" } : LEER;

  const mo = d.mode, mc = a("mode").confidence;
  w.mode = gueltig(mo) ? { wert: mo.state, detail: mc != null && mc > 0 ? `confidence: ${fix(mc * 100, 0)}%` : "Modus wird ermittelt…" }
    : mo ? { wert: "aktiv", detail: "Standard-Modus" } : LEER;

  const cb = d.cerebellum, ca = a("cerebellum");
  w.cereb = gueltig(cb) ? { wert: cb.state, detail: `fired: ${ca.total_fired || 0} · 1g: ${ca.rules_1gram || 0} · 2g: ${ca.rules_2gram || 0}` }
    : cb ? { wert: "0 Regeln", detail: "Lerne Muster… (braucht ~50 Events)" } : LEER;

  /* aus dem Status-Sensor: Surprise, Circadian, Dopamin */
  const st = d.status && d.status.attr;
  w.surprise = w.circadian = w.dopamine = LEER;
  if (st && st.predictive_processing) {
    const pp = st.predictive_processing, s = pp.current_surprise || 0, avg = pp.average_surprise || 0;
    w.surprise = {
      wert: `${s > 0.6 ? "⚡" : s > 0.3 ? "◉" : "○"} ${fix(s * 100, 0)}%`, ton: s > 0.6 ? "nok" : s > 0.3 ? "warn" : "ok",
      detail: `Ø ${fix(avg * 100, 0)}% · weight: ${fix(pp.learn_weight || 1, 1)}x · surprises: ${fix((pp.surprise_ratio || 0) * 100, 0)}%`,
    };
  }
  if (st && st.neurorhythms) {
    const nr = st.neurorhythms, circ = nr.circadian_multiplier || 1.0, dopa = nr.dopamine_level || 0, burst = !!nr.burst_active;
    w.circadian = {
      wert: `${circ > 1.0 ? "☀" : circ > 0.7 ? "◐" : "☾"} ${fix(circ, 2)}x`, ton: circ > 1.0 ? "warn" : circ > 0.7 ? "info" : "still",
      detail: `Lernrate-Modulation · Homeostasis: ${fix(nr.homeostasis_factor || 1.0, 2)}`,
    };
    w.dopamine = {
      wert: `${burst ? "⚡" : dopa > 0.5 ? "▲" : "●"} ${fix(dopa * 100, 0)}%`, ton: burst ? "nok" : dopa > 0.5 ? "ok" : "info",
      detail: `Bursts: ${nr.total_bursts || 0} · stärkster: ${fix(nr.strongest_burst || 0, 1)}x`,
    };
  }
  return w;
}

/* Kopfzeile: Status, Events, Accuracy, Memory, Absorbed */
function kopfWerte(d) {
  const st = d.status, a = (st && st.attr) || {}, k = {};
  k.status = st ? String(st.state || "").toUpperCase() : "—";
  k.events = a.hippocampus ? a.hippocampus.total_events || 0 : "—";
  k.acc = gueltig(d.accuracy) ? d.accuracy.state : "—";
  k.mem = a.hippocampus ? `${a.hippocampus.memory_kb || 0} KB` : "—";
  k.abs = gueltig(d.energy) ? (d.energy.attr.events_absorbed || 0) : "—";
  return k;
}

/* Modul-Details je Modul-ID (die Texte wie im bisherigen Dashboard) */
function modulDetails(a) {
  const m = {};
  if (!a) return m;
  if (a.thalamus) m.thalamus = `entities: ${a.thalamus.entities_registered || "?"} · rooms: ${a.thalamus.rooms_discovered || "?"}`;
  if (a.hippocampus) m.hippocampus = `events: ${a.hippocampus.total_events || 0} · patterns: ${a.hippocampus.patterns || 0}`;
  if (a.hypothalamus) m.hypothalamus = `absorbed: ${a.hypothalamus.events_absorbed || 0}`;
  if (a.spatial) m.spatial = `room: ${a.spatial.current_room || "?"} · transitions: ${a.spatial.transitions_emitted || 0}`;
  if (a.insula) m.insula = `mode: ${a.insula.current_mode || "?"} · changes: ${a.insula.mode_changes || 0}`;
  if (a.amygdala) m.amygdala = `vetoes: ${a.amygdala.total_vetoes || 0} · risks: ${a.amygdala.learned_risks || 0}`;
  if (a.cerebellum) m.cerebellum = `rules: ${a.cerebellum.rules_count || 0} · fired: ${a.cerebellum.total_fired || 0}`;
  if (a.prefrontal) {
    const pf = a.prefrontal, mode = pf.operation_mode || (pf.shadow_mode ? "shadow" : "active");
    m.prefrontal = `${mode.toUpperCase()} · decisions: ${pf.total_decisions || 0} · overrides: ${pf.overrides_detected || 0}`;
  }
  if (a.basal_ganglia) m.basalganglien = `habits: ${a.basal_ganglia.total_habits || 0} · q-entries: ${a.basal_ganglia.q_entries || 0} · dopamin: ${a.basal_ganglia.dopamine_signal || 0}`;
  if (a.anterior_cingulate) {
    const c = a.anterior_cingulate;
    m.acc = `conflict: ${c.conflict_level || 0} · errors: ${c.total_errors || 0} · threshold: ${c.confidence_threshold || 0.5}`;
  }
  if (a.reticular) m.reticular = `filtered: ${a.reticular.filtered_events || 0} · cooldowns: ${a.reticular.total_cooldowns || 0}`;
  if (a.locus_coeruleus) m.locus = `arousal: ${fix(a.locus_coeruleus.arousal || 0, 2)} · events: ${a.locus_coeruleus.total_events || 0}`;
  if (a.entorhinal) m.entorhinal = `transitions: ${Object.keys(a.entorhinal.transitions || {}).length} · rooms: ${Object.keys(a.entorhinal.room_counts || {}).length}`;
  if (a.metaplasticity) m.metaplasticity = `modules: ${a.metaplasticity.modules_tracked || 0} · last: ${a.metaplasticity.last_update || "nie"}`;
  if (a.neurorhythms) {
    const nr = a.neurorhythms;
    m.neurorhythms = `circadian: ${fix(nr.circadian_multiplier || 1, 2)}x · dopamin: ${fix((nr.dopamine_level || 0) * 100, 0)}% · bursts: ${nr.total_bursts || 0} · load: ${fix(nr.synaptic_load || 0, 0)}`;
  }
  if (a.sleep_consolidation) {
    const sc = a.sleep_consolidation;
    m.sleep = `total: ${sc.total_consolidations || 0} · pruned: ${sc.last_patterns_pruned || 0} · reinforced: ${sc.last_patterns_reinforced || 0} · dreams: ${sc.total_dream_connections || 0} · SHY: ${fix(sc.last_homeostasis_factor || 1.0, 2)}`;
  }
  m.accumbens = "aktiv · moduliert Q-Ranking";     // der Kern meldet dazu keine Zahlen
  return m;
}

/* Cortex-Status als Zeilen aus Teilstücken [text, klasse] (klasse: "" | hi | ok | er | ag); {sep:true} ist eine Trennlinie */
function cortexZeilen(st, seq) {
  if (!st || !st.attr) return null;
  const a = st.attr, z = [];
  const t = (...teile) => z.push(teile);
  if (a.cortex) {
    const c = a.cortex;
    t(["CORTEX", "hi"]);
    t([`  Agents: ${c.agents || 0}  ·  Sequential: `, ""], seq ? ["AN", "ok"] : ["AUS", ""]);
    t([`  Beratungen: ${c.total_consultations || 0}`, ""]);
    t([`  Diskussionen: ${c.total_discussions || 0}`, ""]);
    const lc = c.last_consensus;
    if (lc && lc.consensus_action) {
      t([""]);
      t(["LETZTER KONSENS", "ag"]);
      t(["  Aktion: ", ""], [lc.consensus_action || "keine", "hi"]);
      t([`  Entity: ${lc.consensus_entity || "–"}`, ""]);
      t([`  Grund: ${(lc.consensus_reason || "").substring(0, 200)}`, ""]);
      t(["  Veto: ", ""], lc.vetoed ? ["JA", "er"] : ["Nein", "ok"]);
      t([`  Runden: ${lc.discussion_rounds || 1}`, ""]);
      if (lc.proposals && lc.proposals.length) {
        t([""]);
        t(["VORSCHLÄGE (Runde 1)", "ag"]);
        for (const p of lc.proposals) {
          t(["  ", ""], [p.agent || "?", "hi"], [`: ${p.action || "keine"} → ${p.entity_id || "–"}`, ""], ...(p.veto ? [[" [VETO]", "er"]] : []));
          t([`    Grund: ${(p.reason || "?").substring(0, 150)}`, ""]);
          t([`    Priorität: ${p.priority || 0}`, ""]);
        }
      }
      if (lc.revisions && lc.revisions.length) {
        t([""]);
        t(["REVISIONEN (Runde 2)", "ag"]);
        for (const r of lc.revisions) {
          t(["  ", ""], [r.agent || "?", "hi"], [`: ${r.action || "keine"} → ${r.entity_id || "–"}`, ""]);
          t([`    Grund: ${(r.reason || "?").substring(0, 150)}`, ""]);
        }
      }
    }
  } else t(["Cortex nicht konfiguriert.", ""]);

  if (a.last_brain_review) {
    const br = a.last_brain_review;
    t([""]); z.push({ sep: true });
    t(["BRAIN REVIEW", "ag"]);
    t(["  Health Score: ", ""], [`${br.health_score}/100`, "hi"]);
    t([`  Agents: ${br.agents_consulted || 0}`, ""]);
    if (br.timestamp) t([`  Zeitpunkt: ${br.timestamp}`, ""]);
  }

  t([""]); z.push({ sep: true });
  t(["MODULE", "ag"]);
  if (a.hippocampus) t([`  Hippocampus: ${a.hippocampus.total_events || 0} Events, ${a.hippocampus.patterns || 0} Patterns, ${a.hippocampus.memory_kb || 0} KB`, ""]);
  if (a.cerebellum) t([`  Cerebellum: ${a.cerebellum.rules_count || 0} Regeln, ${a.cerebellum.total_fired || 0} gefeuert`, ""]);
  if (a.prefrontal) t([`  Prefrontal: ${a.prefrontal.total_decisions || 0} Entscheidungen, ${a.prefrontal.overrides_detected || 0} Overrides`, ""]);
  if (a.amygdala) t([`  Amygdala: ${a.amygdala.total_vetoes || 0} Vetos, ${a.amygdala.learned_risks || 0} Risiken`, ""]);
  if (a.spatial) t([`  Spatial: Raum ${a.spatial.current_room || "?"}, ${a.spatial.transitions_emitted || 0} Transitions`, ""]);
  if (a.insula) t([`  Insula: Modus ${a.insula.current_mode || "?"}, ${a.insula.mode_changes || 0} Wechsel`, ""]);

  t([""]);
  t(["NEUROMODULATION", "ag"]);
  if (a.anterior_cingulate) t([`  ACC: Konflikt ${a.anterior_cingulate.conflict_level || 0}, Fehlerrate ${a.anterior_cingulate.error_rate || 0}, Schwelle ${a.anterior_cingulate.confidence_threshold || 0.5}`, ""]);
  if (a.reticular) t([`  Reticular: ${a.reticular.filtered_events || 0} gefiltert`, ""]);
  if (a.locus_coeruleus) t([`  Locus Coeruleus: Arousal ${typeof a.locus_coeruleus.arousal === "number" ? a.locus_coeruleus.arousal.toFixed(2) : "?"}`, ""]);
  if (a.entorhinal) t([`  Entorhinal: ${Object.keys(a.entorhinal.transitions || {}).length} Transitions`, ""]);
  if (a.sleep_consolidation) t([`  Sleep: ${a.sleep_consolidation.total_consolidations || 0} Konsolidierungen, ${a.sleep_consolidation.last_patterns_pruned || 0} pruned, ${a.sleep_consolidation.total_dream_connections || 0} dreams`, ""]);
  if (a.neurorhythms) t([`  Neurorhythmen: circadian=${fix(a.neurorhythms.circadian_multiplier || 1, 2)}x, dopamin=${fix((a.neurorhythms.dopamine_level || 0) * 100, 0)}%, bursts=${a.neurorhythms.total_bursts || 0}`, ""]);
  if (a.predictive_processing) {
    const pp = a.predictive_processing;
    t([`  Predictive: surprise ${pp.current_surprise || 0}, baseline ${pp.baseline_surprise || 0}, weight ${pp.learn_weight || 1}x, ratio ${fix((pp.surprise_ratio || 0) * 100, 0)}%`, ""]);
  }
  if (a.metaplasticity) t([`  Metaplastizität: ${a.metaplasticity.modules_tracked || 0} Module, letztes Update: ${a.metaplasticity.last_update || "nie"}`, ""]);
  return z;
}

const zeilenHtml = (zeilen) => zeilen.map((z) => (z.sep ? `<hr class="sep">`
  : `<div>${z.map(([text, kl]) => (kl ? `<span class="dbg-${kl}">${esc(text)}</span>` : esc(text))).join("") || "&nbsp;"}</div>`)).join("");

const DIENST_TEXT = {
  cortex_consult: "Cortex-Beratung gestartet (Agents diskutieren…)",
  brain_review: "Brain-Analyse gestartet (Agents prüfen Gehirn-Gesundheit…)",
  status: "Status abgerufen",
  export_brain: "Gehirn-Export gespeichert",
  set_mode: "Betriebsmodus geändert",
  cortex_sequential: "Sequential Mode umgeschaltet",
  confirm_action: "Aktion bestätigt – wird ausgeführt",
  reject_action: "Aktion abgelehnt – negatives Feedback",
};

/* Dienste im Debug-Bereich: [id, Titel, Beschreibung, Daten] */
const DIENSTE = [
  ["cortex_consult", "Cortex Consult", "LLM-Agents beraten über den aktuellen Zustand", null],
  ["brain_review", "Brain Review", "Gesundheits-Check aller Gehirn-Module", null],
  ["status", "Status", "Zeigt den aktuellen System-Status", null],
  ["export_brain", "Brain Export", "Speichert den Gehirn-Zustand als JSON", null],
  ["activate", "Activate Light", "Aktiviert Licht-Steuerung (Prefrontal)", { semantic: "light" }],
  ["deactivate", "Deactivate All", "Deaktiviert alle Steuerungen", { semantic: "all" }],
];
const MODI = [
  ["shadow", "Shadow", "Nur beobachten, keine Aktionen ausführen"],
  ["confirm", "Confirm", "Aktionen vorschlagen, Bestätigung nötig"],
  ["active", "Active", "Aktionen automatisch ausführen"],
];

/* ---------- Das Gehirn (eigene Zeichnung, Farben aus dem Theme) ---------- */
const BR_FILTER = (id, sd) => `<filter id="${id}"><feGaussianBlur stdDeviation="${sd}" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
const region = (tag, id, farbe, filt, geo, titel, text, an = true) =>
  `<${tag} id="r-${id}" class="br${an ? " on" : ""}" ${geo} style="fill:${farbe};stroke:${farbe};color:${farbe}" filter="url(#${filt})" data-m="${id}" data-t="${esc(titel)}" data-d="${esc(text)}"></${tag}>`;
const pfad = (id, f, filt, d, t, x, an) => region("path", id, f, filt, `d="${d}"`, t, x, an);
const ell = (id, f, filt, cx, cy, rx, ry, t, x) => region("ellipse", id, f, filt, `cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}"`, t, x);
const beschr = (x, y, text, an = true, klein = false) => `<text class="bl${an ? " on" : ""}" x="${x}" y="${y}"${klein ? ' style="font-size:5px"' : ""}>${esc(text)}</text>`;
const kontur = (d, breite, deckkraft) => `<path d="${d}" fill="none" style="stroke:var(--secondary-text-color)" stroke-opacity="${deckkraft}" stroke-width="${breite}"/>`;

function gehirnSvg() {
  return `<svg class="brain-svg" viewBox="0 0 520 440" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Gehirn mit den Modulen von KONTINUUM">
    <defs>${BR_FILTER("g", 5)}${BR_FILTER("gs", 3)}</defs>
    ${kontur(`M130,180 C115,155 108,128 112,100 C116,72 132,50 158,38 C184,26 218,22 250,24 C282,22 316,26 342,38 C368,50 384,72 388,100 C392,128 385,155 370,180 C358,200 352,218 350,235 C348,258 355,278 368,295 C382,314 400,328 408,342 C416,356 415,368 405,376 C395,384 378,386 358,382 C338,378 315,368 295,358 C275,348 262,342 250,340 C238,342 225,348 205,358 C185,368 162,378 142,382 C122,386 105,384 95,376 C85,368 84,356 92,342 C100,328 118,314 132,295 C145,278 152,258 150,235 C148,218 142,200 130,180Z`, 1.8, 0.35)}
    ${kontur("M320,330 C335,318 358,312 378,316 C398,320 412,332 418,348 C424,364 420,380 408,388 C396,396 378,398 358,394 C338,390 322,378 316,362 C310,346 312,336 320,330Z", 1.2, 0.25)}
    ${kontur("M335,340 C348,332 365,330 380,335", 0.8, 0.15)}${kontur("M328,354 C345,346 368,344 390,350", 0.8, 0.15)}${kontur("M325,368 C342,362 365,360 388,366", 0.8, 0.15)}
    ${kontur("M248,310 C245,325 242,345 240,370 C238,390 240,405 245,415 C250,415 255,405 257,390 C259,370 256,345 253,325 C252,318 250,312 248,310Z", 1, 0.25)}
    ${kontur("M240,32 C235,60 228,95 232,130 C236,165 242,195 245,220", 1, 0.2)}
    ${kontur("M145,195 C175,200 210,210 240,225 C260,235 275,248 285,260", 1, 0.2)}
    ${kontur("M335,70 C330,110 328,150 332,190", 1, 0.2)}
    ${["M155,65 C170,58 188,55 205,60", "M165,90 C182,82 200,80 218,85", "M140,120 C160,112 182,110 200,115", "M275,55 C295,48 315,50 332,58", "M280,85 C298,78 318,78 335,85", "M290,115 C308,108 325,110 340,118", "M155,155 C175,148 195,150 210,158", "M300,155 C318,148 336,150 350,158"].map((d) => kontur(d, 0.7, 0.1)).join("")}
    ${["M250,210 C225,240 210,260 205,280", "M250,210 C240,230 235,248 232,258", "M250,210 C210,180 175,130 155,90", "M250,210 C290,180 325,130 345,90", "M235,100 C240,140 245,170 250,210", "M195,305 C200,300 205,296 210,292", "M258,340 C255,300 252,260 250,220", "M285,225 C290,215 294,207 298,200"].map((d) => `<path d="${d}" class="np on"/>`).join("")}
    <path d="M205,285 C250,310 320,330 365,350" class="np"/>
    ${pfad("prefrontal", FARBE.cyan, "g", "M130,170 C118,148 112,122 115,98 C118,74 130,56 155,44 C175,34 200,30 222,32 C228,50 232,80 232,115 C232,145 228,168 222,185 C200,188 168,185 148,180 C138,176 133,174 130,170Z", "Präfrontaler Kortex", "Entscheidungsengine: OBSERVE → SUGGEST → EXECUTE. Override-Erkennung. Implizites Feedback-Lernen.")}
    ${beschr(172, 108, "Präfrontal")}
    ${pfad("motor", FARBE.violett, "gs", "M222,32 C230,28 240,26 250,24 C256,26 262,28 268,32 C265,55 258,85 255,115 C252,85 242,55 235,38Z", "Motorischer Kortex", "Zukunft: Service-Call-Orchestrierung mit Sequenzen und Delays.", false)}
    ${beschr(248, 52, "Motor", false)}
    ${pfad("spatial", FARBE.ok, "g", "M268,32 C295,34 322,44 342,56 C362,70 375,88 380,110 C384,132 378,155 368,172 C350,168 335,160 322,148 C308,134 295,115 285,95 C275,75 270,52 268,32Z", "Spatial Cortex", "Raumwahrnehmung: Fusioniert Motion+Präsenz+Tracker → Raumwechsel-Events statt Motion-Spam.")}
    ${beschr(328, 100, "Spatial")}
    ${pfad("occipital", FARBE.grau, "gs", "M368,172 C378,188 382,208 378,228 C374,248 365,265 355,278 C342,265 335,248 332,228 C330,208 335,188 345,172 C352,168 360,168 368,172Z", "Visueller Kortex", "Zukunft: Kamera-basierte Erkennung (optional, nicht für Raspi4).", false)}
    ${beschr(355, 222, "Visuell", false)}
    ${kontur("M145,195 C155,210 158,228 155,248 C152,268 145,285 138,298 C130,288 125,272 122,255 C118,235 120,215 128,198 C133,192 139,190 145,195Z", 0.8, 0.2)}
    ${ell("thalamus", FARBE.primary, "g", 250, 210, 35, 24, "Thalamus", "Sensorisches Tor: Filtert alle HA-Events, tokenisiert, routet an Hypothalamus / Spatial / Hippocampus.")}
    ${beschr(250, 213, "Thalamus")}
    <circle cx="250" cy="210" r="2.5" style="fill:${FARBE.primary}" opacity=".6"><animate attributeName="r" values="2;5;2" dur="2.5s" repeatCount="indefinite"/><animate attributeName="opacity" values=".6;.15;.6" dur="2.5s" repeatCount="indefinite"/></circle>
    ${ell("insula", FARBE.pink, "gs", 195, 195, 24, 16, "Insula", "Modus-Erkennung: sleeping / active / relaxing / away – kontextbasiert, nicht zeitbasiert.")}
    ${beschr(195, 198, "Insula")}
    ${ell("basalganglien", FARBE.orange, "gs", 298, 195, 22, 14, "Basalganglien", "Belohnungslernen: Q-Value-Tabelle, Go/NoGo-Pfade, Gewohnheitsbildung, Dopamin-Signal.")}
    ${beschr(298, 198, "Basal")}
    ${ell("hypothalamus", FARBE.bernstein, "gs", 238, 258, 28, 16, "Hypothalamus", "Energie/Klima-Kontext: Absorbiert Batterie/Solar/Temperatur. Max 1 Summary-Token pro 30 Min.")}
    ${beschr(238, 261, "Hypothal.")}
    ${ell("amygdala", FARBE.nok, "gs", 198, 268, 16, 13, "Amygdala", "Risiko-Veto: Bewertet Aktionen, lernt aus Override-Feedback. Verhindert gefährliche Automationen.")}
    ${beschr(198, 271, "Amyg")}
    ${pfad("hippocampus", FARBE.lila, "g", "M178,278 C188,268 205,264 220,268 C235,272 245,284 242,298 C239,312 225,318 210,315 C195,312 182,302 178,292 C175,286 175,282 178,278Z", "Hippocampus", "Gedächtnis: Arbeitsgedächtnis (Buffer 20 Events) + Konsolidiert (Markov N-Gramme). Decay vergisst alte Muster.")}
    ${beschr(212, 294, "Hippocampus")}
    ${pfad("cerebellum", FARBE.teal, "g", "M320,330 C335,318 358,312 378,316 C398,320 412,332 418,348 C424,364 420,380 408,388 C396,396 378,398 358,394 C338,390 322,378 316,362 C310,346 312,336 320,330Z", "Cerebellum", "Routinen-Kompilierung: Alle 6h werden häufigste Muster zu festen Regeln kompiliert.")}
    ${beschr(370, 356, "Cerebellum")}
    ${pfad("reticular", FARBE.silber, "gs", "M244,310 C242,328 240,350 239,375 C238,395 240,408 245,415 C250,415 255,408 256,395 C257,375 255,350 253,328 C252,318 248,312 244,310Z", "Formatio Reticularis", "Burst-Filter: Unterdrückt Ereignis-Stürme per Cooldown. Schützt das Gehirn vor Überlastung.")}
    ${beschr(248, 380, "Reticular")}
    ${ell("locus", FARBE.indigo, "gs", 260, 345, 10, 8, "Locus Coeruleus", "Arousal: Misst Ereignisdichte (EMA). Hohes Arousal = mehr Aufmerksamkeit, System reagiert schneller.")}
    ${beschr(260, 348, "LC", true, true)}
    ${pfad("entorhinal", FARBE.lime, "gs", "M165,295 C175,288 190,286 200,290 C210,294 215,304 210,312 C205,320 192,322 180,318 C168,314 162,304 165,295Z", "Entorhinaler Cortex", "Raumübergänge: Lernt eine Transitions-Map zwischen Räumen. Pruned selten genutzte Pfade automatisch.")}
    ${beschr(188, 306, "Entorh.", true, true)}
    ${ell("accumbens", FARBE.tieforange, "gs", 278, 222, 14, 10, "Nucleus Accumbens", "Belohnungssignal: Verstärkt gute Aktionen (+1), bestraft Overrides (-1). Moduliert Q-Value-Ranking.")}
    ${beschr(278, 225, "NAcc", true, true)}
    ${pfad("acc", FARBE.akzent, "gs", "M230,32 C236,45 240,65 240,85 C240,105 238,120 235,130 C228,125 222,110 220,90 C218,70 222,48 230,32Z", "Anteriorer Cingulärer Cortex", "Konfliktmonitor: Erkennt widersprechende Module, passt Entscheidungsschwellen dynamisch an. Ruft bei Unsicherheit den Cortex.")}
    ${beschr(230, 78, "ACC", true, true)}
  </svg>`;
}

/* ---------- Bausteine des Hauses ---------- */
/* Die Elemente von Home Assistant (hass-tabs-subpage, ha-card, ha-button ...) laden sich erst,
 * wenn eine Seite sie braucht. Wie HACS holen wir sie über die Konfigurationsseite.
 * Fehlt eines, nimmt der Aufbau unten das schlichte HTML-Element: das Panel bleibt bedienbar. */
async function bausteine_laden() {
  if (customElements.get("hass-tabs-subpage-data-table")) return;
  try {
    const aufloeser = document.createElement("partial-panel-resolver");
    const routen = aufloeser._getRoutes
      ? aufloeser._getRoutes([{ component_name: "config", url_path: "a" }])
      : aufloeser.getRoutes([{ component_name: "config", url_path: "a" }]);
    await routen.routes.a.load();
    const konfig = document.createElement("ha-panel-config");
    await konfig.routerOptions.routes.integrations.load();
  } catch (fehler) {
    /* der Rückfall unten wartet trotzdem */
  }
  await Promise.race([
    customElements.whenDefined("hass-tabs-subpage-data-table"),
    new Promise((r) => setTimeout(r, 8000)),
  ]);
}

const TABS = [
  ["uebersicht", "Übersicht", { iconPath: "M22,21H2V3H4V19H6V10H10V19H12V6H16V19H18V14H22V21Z" }],
  ["gehirn", "Gehirn", { iconPath: "M21.33,12.91C21.42,14.46 20.71,15.95 19.44,16.86L20.21,18.35C20.44,18.8 20.47,19.33 20.27,19.8C20.08,20.27 19.69,20.64 19.21,20.8L18.42,21.05C18.25,21.11 18.06,21.14 17.88,21.14C17.37,21.14 16.89,20.91 16.56,20.5L14.44,18C13.55,17.85 12.71,17.47 12,16.9C11.5,17.05 11,17.13 10.5,17.13C9.62,17.13 8.74,16.86 8,16.34C7.47,16.5 6.93,16.57 6.38,16.56C5.59,16.57 4.81,16.41 4.08,16.11C2.65,15.47 1.7,14.07 1.65,12.5C1.57,11.78 1.69,11.05 2,10.39C1.71,9.64 1.68,8.82 1.93,8.06C2.3,7.11 3,6.32 3.87,5.82C4.45,4.13 6.08,3 7.87,3.12C9.47,1.62 11.92,1.46 13.7,2.75C14.12,2.64 14.56,2.58 15,2.58C16.36,2.55 17.65,3.15 18.5,4.22C20.54,4.75 22,6.57 22.08,8.69C22.13,9.8 21.83,10.89 21.22,11.82C21.29,12.18 21.33,12.54 21.33,12.91M16.33,11.5C16.9,11.57 17.35,12 17.35,12.57A1,1 0 0,1 16.35,13.57H15.72C15.4,14.47 14.84,15.26 14.1,15.86C14.35,15.95 14.61,16 14.87,16.07C20,16 19.4,12.87 19.4,12.82C19.34,11.39 18.14,10.27 16.71,10.33A1,1 0 0,1 15.71,9.33A1,1 0 0,1 16.71,8.33C17.94,8.36 19.12,8.82 20.04,9.63C20.09,9.34 20.12,9.04 20.12,8.74C20.06,7.5 19.5,6.42 17.25,6.21C16,3.25 12.85,4.89 12.85,5.81V5.81C12.82,6.04 13.06,6.53 13.1,6.56A1,1 0 0,1 14.1,7.56C14.1,8.11 13.65,8.56 13.1,8.56V8.56C12.57,8.54 12.07,8.34 11.67,8C11.19,8.31 10.64,8.5 10.07,8.56V8.56C9.5,8.61 9.03,8.21 9,7.66C8.92,7.1 9.33,6.61 9.88,6.56C10.04,6.54 10.82,6.42 10.82,5.79V5.79C10.82,5.13 11.07,4.5 11.5,4C10.58,3.75 9.59,4.08 8.59,5.29C6.75,5 6,5.25 5.45,7.2C4.5,7.67 4,8 3.78,9C4.86,8.78 5.97,8.87 7,9.25C7.5,9.44 7.78,10 7.59,10.54C7.4,11.06 6.82,11.32 6.3,11.13C5.57,10.81 4.75,10.79 4,11.07C3.68,11.34 3.68,11.9 3.68,12.34C3.68,13.08 4.05,13.77 4.68,14.17C5.21,14.44 5.8,14.58 6.39,14.57C6.24,14.31 6.11,14.04 6,13.76C5.81,13.22 6.1,12.63 6.64,12.44C7.18,12.25 7.77,12.54 7.96,13.08C8.36,14.22 9.38,15 10.58,15.13C11.95,15.06 13.17,14.25 13.77,13C14,11.62 15.11,11.5 16.33,11.5M18.33,18.97L17.71,17.67L17,17.83L18,19.08L18.33,18.97M13.68,10.36C13.7,9.83 13.3,9.38 12.77,9.33C12.06,9.29 11.37,9.53 10.84,10C10.27,10.58 9.97,11.38 10,12.19A1,1 0 0,0 11,13.19C11.57,13.19 12,12.74 12,12.19C12,11.92 12.07,11.65 12.23,11.43C12.35,11.33 12.5,11.28 12.66,11.28C13.21,11.31 13.68,10.9 13.68,10.36Z" }],
  ["module", "Module", { iconPath: "M7,5H21V7H7V5M7,13V11H21V13H7M4,4.5A1.5,1.5 0 0,1 5.5,6A1.5,1.5 0 0,1 4,7.5A1.5,1.5 0 0,1 2.5,6A1.5,1.5 0 0,1 4,4.5M4,10.5A1.5,1.5 0 0,1 5.5,12A1.5,1.5 0 0,1 4,13.5A1.5,1.5 0 0,1 2.5,12A1.5,1.5 0 0,1 4,10.5M7,19V17H21V19H7M4,16.5A1.5,1.5 0 0,1 5.5,18A1.5,1.5 0 0,1 4,19.5A1.5,1.5 0 0,1 2.5,18A1.5,1.5 0 0,1 4,16.5Z" }],
  ["steuerung", "Steuerung", { iconPath: "M8,5.14V19.14L19,12.14L8,5.14Z" }],
];
const TAB_KEYS = TABS.map((t) => t[0]);
const PFAD = "/kontinuum";

/* ---------- HA-Elemente als Zeichenketten, mit Rückfall auf schlichtes HTML ---------- */
const attr = (n, v) => (v == null || v === "" ? "" : ` ${n}="${esc(v)}"`);
const DA = (o) => Object.entries(o || {}).map(([k, v]) => ` data-${k}="${esc(v)}"`).join("");

/* o: d (data-Attribute), id, klasse, zweit, rot, aus, titel, slot, extra */
function knopf(text, o = {}) {
  const basis = `${attr("id", o.id)}${attr("slot", o.slot)}${attr("title", o.titel)}${o.aus ? " disabled" : ""}${DA(o.d)}${o.extra || ""}`;
  if (def("ha-button")) {
    return `<ha-button${basis}${attr("class", o.klasse)} appearance="${o.zweit ? "outlined" : "filled"}" variant="${o.rot ? "danger" : "brand"}">${esc(text)}</ha-button>`;
  }
  return `<button${basis} class="fb-knopf ${o.zweit ? "zweit" : ""} ${o.rot ? "rot" : ""} ${o.klasse || ""}">${esc(text)}</button>`;
}

/* typ: error | warning | info | success; inhalt ist fertiges HTML (der Aufrufer maskiert) */
function meldung(typ, inhalt, titel) {
  if (def("ha-alert")) return `<ha-alert alert-type="${typ}"${attr("title", titel)}>${inhalt}</ha-alert>`;
  return `<div class="fb-alert ${typ}" role="alert">${titel ? `<b>${esc(titel)}</b> ` : ""}${inhalt}</div>`;
}

/* art: ok | nok | warn | jetzt | "" */
const CHIP_STIL = { ok: "success-color", nok: "error-color", warn: "warning-color", jetzt: "primary-color" };
function chip(text, art = "") {
  const farbe = CHIP_STIL[art];
  const stil = farbe ? `--md-assist-chip-label-text-color:var(--${farbe});--md-assist-chip-outline-color:var(--${farbe});` : "";
  if (def("ha-assist-chip")) return `<ha-assist-chip label="${esc(text)}"${art === "jetzt" ? " filled" : ""}${stil ? ` style="${stil}"` : ""}></ha-assist-chip>`;
  return `<span class="fb-chip"${stil ? ` style="${stil.replace(/--md-assist-chip-label-text-color/, "color")}"` : ""}>${esc(text)}</span>`;
}

/* o: id, klasse, stil */
function karte(kopf, inhalt, o = {}) {
  const k = `karte ${o.klasse || ""}`.trim();
  if (def("ha-card")) return `<ha-card${attr("id", o.id)} class="${k}"${attr("header", kopf)}${attr("style", o.stil)}><div class="card-content">${inhalt}</div></ha-card>`;
  return `<div${attr("id", o.id)} class="${k} fb-karte"${attr("style", o.stil)}>${kopf ? `<h2>${esc(kopf)}</h2>` : ""}${inhalt}</div>`;
}

/* Zeile mit Titel, Beschreibung und einem Bedienelement (ha-settings-row) */
function zeile(titel, text, steuerung, schmal) {
  if (def("ha-settings-row")) {
    return `<ha-settings-row${schmal ? " narrow" : ""}><span slot="heading">${esc(titel)}</span>${text ? `<span slot="description">${esc(text)}</span>` : ""}${steuerung}</ha-settings-row>`;
  }
  return `<div class="fb-zeile"><div><b>${esc(titel)}</b>${text ? `<div class="hinweis">${esc(text)}</div>` : ""}</div><div>${steuerung}</div></div>`;
}

function schalter(an, sw) {
  if (def("ha-switch")) return `<ha-switch${an ? " checked" : ""} data-sw="${sw}"></ha-switch>`;
  return `<input type="checkbox"${an ? " checked" : ""} data-sw="${sw}">`;
}

const WARTE = `<div class="warte"><ha-spinner></ha-spinner></div>`;

/* ---------- Das Panel ---------- */
/* Nur Anordnung: Gitter, Abstände und die Zeichnung des Gehirns. Aussehen kommt von Home Assistant. */
const PANEL_CSS = `
  :host { display: block; }
  * { box-sizing: border-box; }
  .seite { padding: 16px; max-width: 1440px; margin: 0 auto; }
  .raster > * { min-width: 0; }
  .raster { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 16px; }
  .raster.gehirn { grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); }
  @media (max-width: 1100px), (orientation: portrait) { .raster, .raster.gehirn { grid-template-columns: 1fr; } }
  .karte { display: block; margin-bottom: 16px; } .raster > .karte { margin-bottom: 0; }
  .card-content { padding: 16px; }
  .kacheln { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 16px; }
  .kacheln > .karte { margin-bottom: 0; } .kacheln .card-content { padding: 12px 16px; }
  .kachel .wert { font-size: 24px; line-height: 1.2; overflow-wrap: anywhere; }
  .klein { font-size: var(--ha-font-size-s, 12px); color: var(--secondary-text-color); }
  .streifen { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }
  .streifen ha-alert, .streifen .fb-alert { flex: 1 1 100%; }
  ha-alert, ha-settings-row, .fb-alert { display: block; margin: 8px 0; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .punkt { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; }
  .sc { padding: 8px 0; border-bottom: 1px solid var(--divider-color); } .sc:last-child { border-bottom: 0; }
  .sc .wert { font-size: 20px; line-height: 1.3; overflow-wrap: anywhere; }
  .ml { padding: 8px 0; border-bottom: 1px solid var(--divider-color); } .ml:last-child { border-bottom: 0; }
  .ml .name { display: flex; align-items: center; font-weight: var(--ha-font-weight-medium, 500); }
  .module { columns: 340px; column-gap: 24px; } .module .ml { break-inside: avoid; }
  .leer { color: var(--secondary-text-color); font-style: italic; padding: 8px 0; }
  .warte { display: flex; justify-content: center; padding: 32px; }
  .aktionen { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .wartend { border: 1px solid var(--divider-color); border-left: 4px solid var(--warning-color); border-radius: 8px; padding: 12px; margin: 8px 0; display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: start; }
  .wartend .info { min-width: 0; } .wartend .kopf { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-bottom: 4px; }
  .wartend code { overflow-wrap: anywhere; }
  .wartend .knoepfe { display: flex; flex-direction: column; gap: 8px; }
  @media (max-width: 680px) { .wartend { grid-template-columns: 1fr; } .wartend .knoepfe { flex-direction: row; } }
  .dbg { max-height: 460px; overflow-y: auto; font-family: var(--code-font-family, monospace); font-size: 12px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; background: var(--secondary-background-color); border-radius: 8px; padding: 12px; }
  .dbg .ts { color: var(--secondary-text-color); }
  .dbg-ok { color: var(--success-color); } .dbg-er { color: var(--error-color); } .dbg-hi { color: var(--primary-color); } .dbg-ag { color: var(--primary-text-color); font-weight: 600; }
  .dbg hr.sep { border: 0; border-top: 1px solid var(--divider-color); margin: 8px 0; }
  .brain-svg { display: block; width: 100%; max-width: 640px; height: auto; margin: 0 auto; }
  .br { fill-opacity: .12; stroke-width: 1.2; stroke-opacity: .35; transition: all .5s; cursor: pointer; }
  .br:hover { fill-opacity: .3; stroke-opacity: .8; }
  .br.on { fill-opacity: .2; stroke-opacity: .6; animation: glo 2.5s ease-in-out infinite; }
  .br.fire { fill-opacity: .5; stroke-opacity: 1; animation: fir .5s ease-out; }
  @keyframes glo { 0%, 100% { fill-opacity: .12; filter: drop-shadow(0 0 3px currentColor); } 50% { fill-opacity: .3; filter: drop-shadow(0 0 10px currentColor); } }
  @keyframes fir { 0% { fill-opacity: .7; filter: drop-shadow(0 0 18px currentColor); } 100% { fill-opacity: .2; filter: drop-shadow(0 0 3px currentColor); } }
  .bl { font-size: 6.5px; fill: var(--disabled-text-color, var(--secondary-text-color)); pointer-events: none; text-anchor: middle; letter-spacing: .8px; text-transform: uppercase; }
  .bl.on { fill: var(--secondary-text-color); }
  .np { stroke: var(--secondary-text-color); stroke-opacity: .15; stroke-width: .7; fill: none; stroke-dasharray: 3 3; }
  .np.on { stroke-opacity: .35; animation: nf 4s linear infinite; }
  @keyframes nf { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -18; } }
  .tip { position: fixed; z-index: 100; max-width: 260px; pointer-events: none; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 8px; padding: 8px 12px; font-size: 12px; line-height: 1.5; box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.25)); }
  .tip b { display: block; margin-bottom: 2px; } .tip span { color: var(--secondary-text-color); }
  .log .el { display: flex; align-items: baseline; gap: 8px; padding: 4px 0; border-bottom: 1px solid var(--divider-color); font-size: 13px; }
  .log .el:last-child { border-bottom: 0; } .log .t { color: var(--secondary-text-color); font-size: 11px; min-width: 56px; }
  .log .d { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; align-self: center; }
  /* Rückfall, falls ein Baustein des Hauses fehlt: schlichte Elemente in Farben des Themas */
  .fb-kopf { padding: 12px 16px; background: var(--app-header-background-color); color: var(--app-header-text-color); } .fb-kopf h1 { margin: 0; font-size: 20px; font-weight: 500; }
  .fb-tabs { display: flex; flex-wrap: wrap; gap: 4px; padding: 0 16px; border-bottom: 1px solid var(--divider-color); }
  .fb-tabs .fb-knopf { background: none; border: 0; border-radius: 0; color: var(--secondary-text-color); } .fb-tabs .fb-knopf.aktiv { color: var(--primary-color); border-bottom: 3px solid var(--primary-color); }
  .fb-knopf { font: inherit; padding: 8px 16px; border: 1px solid var(--primary-color); border-radius: 18px; cursor: pointer; background: var(--primary-color); color: var(--text-primary-color); }
  .fb-knopf.zweit { background: none; color: var(--primary-color); } .fb-knopf.rot { background: var(--error-color); border-color: var(--error-color); color: #fff; }
  .fb-knopf:disabled { opacity: .45; cursor: not-allowed; }
  .fb-zeile { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; }
  .hinweis { font-size: var(--ha-font-size-s, 12px); color: var(--secondary-text-color); }
  .fb-alert { padding: 8px 12px; border: 1px solid var(--divider-color); border-radius: 6px; }
  .fb-alert.error { border-color: var(--error-color); color: var(--error-color); } .fb-alert.warning { border-color: var(--warning-color); } .fb-alert.success { border-color: var(--success-color); }
  .fb-chip { padding: 2px 10px; border: 1px solid var(--divider-color); border-radius: 12px; }
  .fb-karte { background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); padding: 16px; } .fb-karte h2 { margin: 0 0 10px; font-size: 18px; font-weight: 500; }
  dialog.fb-dialog { max-width: 520px; width: 90%; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 12px; }
  @media (max-width: 600px) { .seite { padding: 8px; } }
`;

const Basis = typeof HTMLElement !== "undefined" ? HTMLElement : class {};

class KontinuumPanel extends Basis {
  constructor() {
    super();
    this.sh = this.attachShadow({ mode: "open" });
    this.tab = "uebersicht";
    this._d = {};                       // gefundene Sensoren (discoverSensors)
    this._cache = {};                   // entity_id -> Zustand (aus dem Abo)
    this._conn = "wait";                // wait | ok | err
    this._aboOk = false; this._aboLaeuft = false; this._unsub = null;
    this._ersterStand = true; this._keineSensoren = false;
    this._prevEvent = ""; this._prevCount = 0; this._lastEvents = 0;
    this._logZ = []; this._dbgZ = [];
    this._debug = false; this._seq = false;
    this._laeuft = new Set();
    this._bereit = false; this._html = null;
  }

  set hass(h) {
    const erst = !this._hass;
    this._hass = h;
    if (this._rahmen) this._rahmen.hass = h;
    if (erst) this.starten();
    else if (this._bereit && !this._aboOk && !this._aboLaeuft) this.ersatzLesen();
  }
  set narrow(n) { this._narrow = n; if (this._rahmen) this._rahmen.narrow = !!n; }
  set panel(p) { this._panel = p; }
  set route(r) {
    this._route = r;
    const t = this._tabAusRoute();
    if (t && t !== this.tab && this._bereit) { this.tab = t; this.zeigeTab(); }
  }

  connectedCallback() { if (this._bereit) { this.abonnieren(); this.takte(); } }
  disconnectedCallback() {
    this.abmelden();
    clearInterval(this._anim); this._anim = null;
    clearTimeout(this._ruhe); this._ruhe = null;
    clearTimeout(this._ersatz); this._ersatz = null;
    clearTimeout(this._tipZu);
  }

  q(s) { return this.sh.querySelector(s); }

  /* --- Adresse und Tabs: /kontinuum/<tab>, wie bei den Seiten des Hauses --- */
  _tabAusRoute() {
    const m = ((this._route && this._route.path) || "").match(/^\/([a-z]+)/);
    return m && TAB_KEYS.includes(m[1]) ? m[1] : null;
  }
  _prefix() { return (this._route && this._route.prefix) || PFAD; }

  geheTab(t) {
    this.tab = t; this.zeigeTab();
    try {
      const ziel = `${this._prefix()}/${t}`;
      if (window.location.pathname !== ziel) {
        window.history.pushState(null, "", ziel);
        window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
      }
    } catch (_) { /* ohne Adresszeile bleibt der Tab trotzdem gewechselt */ }
  }

  /* --- Aufbau --- */
  geruestBauen() {
    const ha = def("hass-tabs-subpage");
    const inhalt = `<div class="seite"><div id="streifen" class="streifen"></div><div id="wartend"></div><div id="inhalt"></div><div class="tip" id="tip" hidden></div></div>`;
    this.sh.innerHTML = `<style>${PANEL_CSS}</style><div id="oben"></div>`;
    const oben = this.q("#oben");
    if (ha) {
      /* tabs und route stehen, bevor das Element zum ersten Mal zeichnet; sonst wirft HA tabs.filter of undefined */
      const r = document.createElement("hass-tabs-subpage");
      r.tabs = [];
      r.route = { prefix: this._prefix(), path: `/${this.tab}` };
      r.mainPage = true; r.hass = this._hass; r.narrow = !!this._narrow;
      r.innerHTML = `<span slot="header">KONTINUUM</span>${inhalt}`;
      this.sh.insertBefore(r, oben);
      this._rahmen = r;
    } else {
      const w = document.createElement("div");
      w.innerHTML = `<div class="fb-kopf"><h1>KONTINUUM</h1></div><nav class="fb-tabs" id="tabs"></nav>${inhalt}`;
      this.sh.insertBefore(w, oben);
      this._rahmen = null;
    }
    this.sh.addEventListener("click", (e) => {
      const t = e.target.closest && e.target.closest("[data-act]");
      if (t && !t.disabled && !t.hasAttribute("disabled")) { if (t.tagName === "A") e.preventDefault(); this.aktion(t.dataset.act, t.dataset); return; }
      const br = e.target.closest && e.target.closest(".br");
      if (br) { this.tipZeigen(br, e); clearTimeout(this._tipZu); this._tipZu = setTimeout(() => this.tipWeg(), 4000); }   // Fingertipp statt Hover
    });
    this.sh.addEventListener("change", (e) => {
      const t = e.target;
      if (t && t.dataset && t.dataset.sw) this.schalten(t.dataset.sw, !!t.checked);
    });
    this.sh.addEventListener("pointerover", (e) => { const br = e.target.closest && e.target.closest(".br"); if (br) this.tipZeigen(br, e); });
    this.sh.addEventListener("pointermove", (e) => { const tip = this.q("#tip"); if (tip && !tip.hidden) this.tipSetzen(e); });
    this.sh.addEventListener("pointerout", (e) => { if (e.target.closest && e.target.closest(".br")) this.tipWeg(); });
  }

  async starten() {
    this.sh.innerHTML = `<style>${PANEL_CSS}</style>${WARTE}`;
    await bausteine_laden();
    this.geruestBauen();
    const rt = this._tabAusRoute(); if (rt) this.tab = rt;
    this._bereit = true;
    this.zeigeTab();
    this.abonnieren();
    this.takte();
  }

  takte() {
    clearInterval(this._anim);
    this._anim = setInterval(() => this.hirnAnimieren(), 5000);
  }

  /* --- Tabs: die Tab-Leiste gehört Home Assistant (hass-tabs-subpage) --- */
  tabsZeichnen() {
    if (this._rahmen) {
      const r = this._rahmen;
      r.route = { prefix: this._prefix(), path: `/${this.tab}` };
      r.tabs = TABS.map(([k, n, ic]) => ({ path: `${this._prefix()}/${k}`, name: n, ...ic }));
      return;
    }
    const nav = this.q("#tabs"); if (!nav) return;
    nav.innerHTML = TABS.map(([k, n]) => `<button class="fb-knopf ${k === this.tab ? "aktiv" : ""}" data-act="tab" data-t="${k}">${esc(n)}</button>`).join("");
  }

  zeigeTab() {
    this.tabsZeichnen();
    this._html = null;
    this.tipWeg();
    if (this.tab === "gehirn") {
      this.q("#inhalt").innerHTML = `<div class="raster gehirn">${karte("Gehirn", `${gehirnSvg()}<div class="klein">Mit der Maus über ein Areal fahren (oder tippen) zeigt seine Aufgabe.</div>`)}`
        + `${karte("Activity Log", `<div id="log" class="log"></div>`)}</div>`;
      this._htmlTab = "gehirn";
      this.logZeichnen();
    } else this._htmlTab = null;
    this.zeichnen();
  }

  /* --- Seiteninhalt je Tab (reine Zeichenketten aus dem Zustand) --- */
  streifenHtml() {
    const c = this._conn;
    const verb = chip(c === "ok" ? "VERBUNDEN" : c === "err" ? "FEHLER" : "VERBINDE...", c === "ok" ? "ok" : c === "err" ? "nok" : "warn");
    let h = verb;
    if (c === "err") h += meldung("error", "Keine Verbindung zu Home Assistant. Die Werte sind veraltet; das Panel verbindet sich von selbst wieder.");
    if (this._keineSensoren) h += meldung("warning", "Keine KONTINUUM-Sensoren gefunden – Integration geladen?");
    return h;
  }

  tabHtml(tab) {
    const d = this._d, st = d.status && d.status.attr;
    if (tab === "uebersicht") {
      const k = kopfWerte(d), w = sensorWerte(d);
      const kachel = (label, wert, ton) => karte("", `<div class="kachel"><div class="klein">${esc(label)}</div><div class="wert"${ton ? ` style="color:${TON[ton]}"` : ""}>${esc(wert)}</div></div>`);
      const sc = ([label, x]) => `<div class="sc"><div class="klein">${esc(label)}</div><div class="wert"${x.ton ? ` style="color:${TON[x.ton]}"` : ""}>${esc(x.wert)}</div><div class="klein">${esc(x.detail)}</div></div>`;
      return `<div class="kacheln">${kachel("Status", k.status)}${kachel("Events", k.events)}${kachel("Accuracy", k.acc)}${kachel("Memory", k.mem)}${kachel("Absorbed", k.abs)}</div>`
        + `<div class="raster">${karte("Sensorik", [["Letztes Event", w.event], ["Vorhersage", w.pred], ["Genauigkeit", w.acc], ["Energie", w.nrg], ["Surprise", w.surprise], ["Circadian", w.circadian], ["Dopamin", w.dopamine]].map(sc).join(""))}`
        + `${karte("Kontext", [["Aufenthaltsort", w.loc], ["Modus", w.mode], ["Routinen", w.cereb]].map(sc).join(""))}</div>`;
    }
    if (tab === "module") {
      const m = modulDetails(st);
      return karte("Module", `<div class="module">${MODULE.map(([id, name, farbe]) => `<div class="ml"><div class="name"><span class="punkt" style="background:${farbe}"></span>${esc(name)}</div><div class="klein">${esc(m[id] || "—")}</div></div>`).join("")}</div>`);
    }
    if (tab === "steuerung") return this.steuerungHtml(d.status);
    return "";
  }

  steuerungHtml(st) {
    const a = (st && st.attr) || {}, pf = a.prefrontal;
    const aktuell = pf ? (pf.operation_mode || (pf.shadow_mode ? "shadow" : "active")) : null;
    const lauf = (s) => this._laeuft.has(s);
    const modi = karte("Betriebsmodus", MODI.map(([m, titel, text]) => zeile(titel, text,
      knopf(m === aktuell ? "Aktiv" : "Wählen", { zweit: m !== aktuell, aus: lauf("set_mode"), d: { act: "modus", m } }), this._narrow)).join("")
      + zeile("Alle bestätigen", "Alle wartenden Aktionen bestätigen", knopf("Alle bestätigen", { zweit: true, d: { act: "alle" } }), this._narrow)
      + (aktuell ? "" : `<div class="hinweis">Der Betriebsmodus ist noch nicht gemeldet (Status-Sensor ohne Prefrontal-Daten).</div>`));
    let h = `<div class="raster">${modi}${karte("Debug / Cortex Control", zeile("Debug / Cortex Control", "Dienste auslösen und die Cortex-Ausgabe lesen", schalter(this._debug, "debug"), this._narrow))}</div>`;
    if (!this._debug) return h;
    const dienste = karte("Service Trigger", DIENSTE.map(([id, titel, text, data]) => zeile(titel, text,
      knopf("Ausführen", { zweit: true, aus: lauf(id), d: { act: "dienst", s: id, p: data ? JSON.stringify(data) : "" } }), this._narrow)).join("")
      + zeile("Sequential", "Agents nacheinander statt parallel befragen (1 GPU)", schalter(this._seq, "seq"), this._narrow));
    const z = cortexZeilen(st, this._seq);
    h += dienste + `<div class="raster">${karte("Cortex Output", `<div class="dbg">${this._dbgZ.length ? this._dbgZ.map((l) => `<div><span class="ts">[${esc(l.t)}]</span> ${l.teile.map(([x, kl]) => (kl ? `<span class="dbg-${kl}">${esc(x)}</span>` : esc(x))).join("")}</div>`).join("") : "Warte auf Cortex-Aktivität…"}</div>`)}`
      + `${karte("Cortex Status", `<div class="dbg">${z ? zeilenHtml(z) : "Keine Cortex-Daten verfügbar."}</div>`)}</div>`;
    return h;
  }

  wartendHtml() {
    const st = this._d.status, pf = st && st.attr && st.attr.prefrontal;
    const liste = pf && Array.isArray(pf.pending_confirms_list) ? pf.pending_confirms_list : [];
    if (!liste.length) return "";
    const eintrag = (item) => {
      const id = item.id || "", ctx = item.context || {}, bits = [];
      if (ctx.mode) bits.push(`Modus: ${ctx.mode}`);
      if (ctx.time_bucket) bits.push(String(ctx.time_bucket));
      if (ctx.rule_order) bits.push(`${ctx.rule_order}-gram Regel`);
      const age = item.age_s || 0, ttl = item.expires_in_s != null ? item.expires_in_s : Math.max(0, 600 - age);
      const meta = [item.room ? `Raum: ${item.room}` : "", item.semantic ? `Funktion: ${item.semantic}` : "", `conf ${Math.round((item.confidence || 0) * 100)}%`,
        `util ${fix(item.utility || 0, 2)}`, `risk ${fix(item.risk || 0, 2)}`, `n=${item.n_obs || 0}`, `Quelle: ${item.source || "?"}`, `${age}s (verfällt in ${ttl}s)`].filter(Boolean);
      return `<div class="wartend" data-id="${esc(id)}"><div class="info">`
        + `<div class="kopf"><code>${esc(item.entity_id || "?")}</code>${chip(String(item.action || "").toUpperCase(), "warn")}</div>`
        + `<div class="klein">${meta.map(esc).join(" · ")}</div>`
        + (bits.length ? `<div class="klein">${bits.map(esc).join(" · ")}</div>` : "")
        + (item.reasoning ? meldung("info", esc(item.reasoning), "Begründung") : "")
        + `</div><div class="knoepfe">${knopf("Ausführen", { d: { act: "bestaetigen", id } })}${knopf("Ablehnen", { zweit: true, rot: true, d: { act: "ablehnen", id } })}</div></div>`;
    };
    return karte(`Wartende Aktionen (${liste.length})`, liste.map(eintrag).join("")
      + `<div class="aktionen">${knopf("Alle bestätigen", { d: { act: "alle" } })}</div>`);
  }

  /* --- Zeichnen: nur anfassen, was sich geändert hat --- */
  zeichnen() {
    if (!this._bereit) return;
    const s = this.q("#streifen"), w = this.q("#wartend"), i = this.q("#inhalt");
    if (!s || !w || !i) return;
    const sh = this.streifenHtml(); if (sh !== this._sHtml) { this._sHtml = sh; s.innerHTML = sh; }
    const wh = this.wartendHtml(); if (wh !== this._wHtml) { this._wHtml = wh; w.innerHTML = wh; }
    if (this.tab === "gehirn") return;
    const h = this.tabHtml(this.tab);
    if (h !== this._html) { this._html = h; i.innerHTML = h; }
  }

  /* --- Gehirn: Feuern, Tooltip, Log --- */
  fire(mod) {
    const el = this.q(`#r-${mod}`);
    if (!el) return;
    el.classList.add("fire");
    setTimeout(() => el.classList.remove("fire"), 500);
  }

  tipZeigen(br, e) {
    const tip = this.q("#tip"); if (!tip) return;
    tip.innerHTML = `<b>${esc(br.dataset.t)}</b><span>${esc(br.dataset.d)}</span>`;
    tip.hidden = false; this.tipSetzen(e);
  }
  tipSetzen(e) {
    const tip = this.q("#tip"); if (!tip) return;
    const rechts = e.clientX > (window.innerWidth || 1000) - 290;
    tip.style.left = rechts ? "" : `${e.clientX + 12}px`; tip.style.right = rechts ? `${(window.innerWidth || 1000) - e.clientX + 12}px` : "";
    tip.style.top = `${e.clientY - 8}px`;
  }
  tipWeg() { const tip = this.q && this.q("#tip"); if (tip) tip.hidden = true; }

  logZ(text, farbe) {
    this._logZ.unshift({ t: uhrzeit(), text, farbe: farbe || FARBE.primary });
    if (this._logZ.length > 25) this._logZ.length = 25;
    this.logZeichnen();
  }
  logZeichnen() {
    const el = this.q("#log"); if (!el) return;
    el.innerHTML = this._logZ.length ? this._logZ.map((e) => `<div class="el"><span class="t">${esc(e.t)}</span><span class="d" style="background:${e.farbe}"></span><span>${esc(e.text)}</span></div>`).join("")
      : `<div class="leer">Noch keine Einträge</div>`;
  }

  dbg(teile) {
    this._dbgZ.unshift({ t: uhrzeit(), teile });
    if (this._dbgZ.length > 100) this._dbgZ.length = 100;
  }

  /* Die Meldung zeigt Home Assistant selbst (Toast am unteren Rand). */
  melde(text, art = "") {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message: text, duration: art === "fehler" ? 10000 : 4000 },
      bubbles: true, composed: true,
    }));
  }

  /* --- Daten: das Abo über hass.connection, hass.states nur als Ersatz --- */
  verbindung(z) {
    this._conn = z;
    if (this._bereit) this.zeichnen();
  }

  async abonnieren() {
    if (this._aboLaeuft || this._aboOk || !this._hass) return;
    const conn = this._hass.connection;
    if (!conn || !conn.subscribeMessage) { this.ersatzStarten("hass.connection fehlt"); return; }
    this._aboLaeuft = true;
    this.verbindung("wait");
    try {
      this._unsub = await conn.subscribeMessage((ev) => this.aboEreignis(ev), { type: "kontinuum/abonniere" });
      this._aboOk = true;
      this.verbindung("ok");
      this.logZ("Verbunden mit Home Assistant (WebSocket-Abo)");
      this._verbEv = [["disconnected", () => this.verbindung("err")], ["ready", () => this.verbindung("ok")]];
      this._verbEv.forEach(([n, f]) => { try { conn.addEventListener(n, f); } catch (_) { /* ältere Verbindung: kein Ereignis */ } });
    } catch (fehler) {
      this.ersatzStarten(fehler && fehler.message ? fehler.message : String(fehler));
    } finally { this._aboLaeuft = false; }
  }

  abmelden() {
    const conn = this._hass && this._hass.connection;
    if (this._verbEv && conn) this._verbEv.forEach(([n, f]) => { try { conn.removeEventListener(n, f); } catch (_) { /* egal */ } });
    this._verbEv = null;
    const u = this._unsub; this._unsub = null; this._aboOk = false;
    if (u) { try { Promise.resolve(u()).catch(() => {}); } catch (_) { /* Verbindung schon weg */ } }
  }

  ersatzStarten(grund) {
    this.logZ(`Abo nicht möglich (${grund}) – das Panel liest hass.states`, FARBE.warn);
    this.ersatzLesen();
  }

  /* Ersatzweg: aus hass.states, höchstens einmal je Sekunde ausgewertet */
  ersatzLesen() {
    if (this._ersatz || !this._hass || !this._hass.states) { if (!this._hass || !this._hass.states) this.verbindung("err"); return; }
    this._ersatz = setTimeout(() => {
      this._ersatz = null;
      if (this._aboOk || !this._hass) return;
      this._conn = "ok";
      this.verarbeiten(ausHassStates(this._hass.states));
    }, this._ersterStand ? 0 : 1000);
  }

  aboEreignis(ev) {
    if (!ev || !ev.art) return;
    if (ev.art === "stand") {
      this._cache = {};
      for (const z of ev.zustaende || []) if (z && z.entity_id) this._cache[z.entity_id] = z;
      clearTimeout(this._ruhe); this._ruhe = null;
      this.verarbeiten(Object.values(this._cache));
    } else if (ev.art === "aenderung") {
      if (ev.neu && ev.neu.entity_id) this._cache[ev.neu.entity_id] = ev.neu;
      else if (ev.entity_id) delete this._cache[ev.entity_id];      // Abschied: Entität entfernt
      if (this._ruhe) return;                                       // Bursts sammeln sich, EINE Zeichnung
      this._ruhe = setTimeout(() => { this._ruhe = null; this.verarbeiten(Object.values(this._cache)); }, 150);
    }
  }

  verarbeiten(zustaende) {
    const d = discoverSensors(zustaende);
    if (this._ersterStand) {
      this._ersterStand = false;
      const n = Object.keys(d).length;
      this._keineSensoren = n === 0;
      this.logZ(n > 0 ? `${n} KONTINUUM Sensoren gefunden` : "Keine KONTINUUM Sensoren gefunden – Integration geladen?", n > 0 ? FARBE.cyan : FARBE.warn);
    } else if (this._keineSensoren && Object.keys(d).length) this._keineSensoren = false;
    this._d = d;
    this.auswerten(d);
    this.zeichnen();
  }

  /* Nebenwirkungen: Areale feuern, Log schreiben (wie bisher nur bei bestehender Verbindung) */
  auswerten(d) {
    const verbunden = this._conn === "ok";
    const ev = d.last_event;
    if (gueltig(ev)) {
      const val = ev.state, room = ev.attr.room || "?", sem = ev.attr.semantic || "", total = ev.attr.events_total || 0;
      const neu = val !== this._prevEvent || (total > 0 && total !== this._prevCount);
      if (neu && verbunden) {
        this.fire("thalamus");
        if (val.includes("house.energy") || val.includes("house.climate")) this.fire("hypothalamus");
        else if (val.includes("person.")) this.fire("spatial");
        else if (val.includes("house.mode")) this.fire("insula");
        else this.fire("hippocampus");
        if (d.prediction && d.prediction.attr && d.prediction.attr.decision) this.fire("prefrontal");
        this.logZ(sem ? `${room} · ${sem} → ${val}` : val,
          val.includes("energy") ? FARBE.bernstein : val.includes("person.") ? FARBE.ok : val.includes("mode.") ? FARBE.pink : FARBE.primary);
      }
      this._prevEvent = val;
      if (total > 0) this._prevCount = total;
    }
    const a = d.status && d.status.attr;
    if (!a) return;
    if (a.basal_ganglia && (a.basal_ganglia.total_updates || 0) > 0) this.fire("basalganglien");
    if (a.anterior_cingulate && (a.anterior_cingulate.conflict_level || 0) > 0.3) this.fire("acc");
    if (a.locus_coeruleus && (a.locus_coeruleus.arousal || 0) > 0.6) this.fire("locus");
    if (a.predictive_processing && (a.predictive_processing.current_surprise || 0) > 0.6) this.fire("acc");
    if (a.neurorhythms && a.neurorhythms.burst_active) this.fire("accumbens");
    if (a.cortex && a.cortex.sequential_mode !== undefined) this._seq = !!a.cortex.sequential_mode;
  }

  /* Periodisches Feuern nach Modulaktivität */
  hirnAnimieren() {
    const a = this._d.status && this._d.status.attr;
    if (!a) return;
    const n = (a.hippocampus && a.hippocampus.total_events) || 0;
    if (n > this._lastEvents) {
      this.fire("reticular");
      setTimeout(() => this.fire("thalamus"), 100);
      setTimeout(() => this.fire("hippocampus"), 200);
      if (a.cerebellum && (a.cerebellum.total_fired || 0) > 0) setTimeout(() => this.fire("cerebellum"), 400);
      if (a.prefrontal && (a.prefrontal.total_decisions || 0) > 0) setTimeout(() => this.fire("prefrontal"), 600);
      if (a.basal_ganglia && (a.basal_ganglia.total_updates || 0) > 0) setTimeout(() => this.fire("basalganglien"), 500);
      setTimeout(() => this.fire("locus"), 150);
      setTimeout(() => this.fire("entorhinal"), 350);
      this._lastEvents = n;
    }
  }

  /* --- Bedienung --- */
  aktion(act, d) {
    ({
      tab: () => this.geheTab(d.t),
      modus: () => this.dienst("set_mode", { mode: d.m }),
      dienst: () => this.dienst(d.s, d.p ? JSON.parse(d.p) : {}),
      bestaetigen: () => d.id && this.dienst("confirm_action", { confirm_id: d.id }),
      ablehnen: () => d.id && this.dienst("reject_action", { confirm_id: d.id }),
      alle: () => this.alleBestaetigen(),
    }[act] || (() => {}))();
  }

  schalten(sw, an) {
    if (sw === "debug") { this._debug = an; if (an) this.dbg([["Debug-Modus aktiviert", "ok"]]); this.zeichnen(); }
    else if (sw === "seq") { this._seq = an; this.dienst("cortex_sequential", { enabled: an }); }
  }

  async dienst(service, data) {
    this._laeuft.add(service); this.zeichnen();
    this.dbg([["Service ", ""], [`kontinuum.${service}`, "hi"], [" wird aufgerufen…", ""]]);
    try {
      await this._hass.callService("kontinuum", service, data || {});
      const label = DIENST_TEXT[service] || `${service} erfolgreich`;
      this.dbg([[label, "ok"]]);
      this.melde(label);
      if (service === "cortex_consult" || service === "brain_review") {
        this.dbg([["Ergebnis wird als History-Datei gespeichert – Warte auf Antwort…", ""]]);
        setTimeout(() => {
          this.dbg([[`${service === "cortex_consult" ? "Beratung" : "Analyse"} abgeschlossen`, "ok"], [" → Ergebnis in Cortex Status sichtbar", ""]]);
          this.zeichnen();
        }, 5000);
      }
    } catch (e) {
      const m = e && e.message ? e.message : String(e);
      this.dbg([[`Fehler: ${m}`, "er"]]);
      this.melde(`kontinuum.${service}: ${m}`, "fehler");
    } finally {
      this._laeuft.delete(service); this.zeichnen();
    }
  }

  /* "Alle bestätigen" führt alle wartenden Aktionen aus: erst nach einem Klick im Bestätigungsfenster */
  alleBestaetigen() {
    const st = this._d.status, pf = st && st.attr && st.attr.prefrontal;
    const n = pf && Array.isArray(pf.pending_confirms_list) ? pf.pending_confirms_list.length : 0;
    const text = n ? `Alle ${n} wartenden Aktionen werden jetzt ausgeführt.` : "Es warten gerade keine Aktionen; bestätigt wird alles, was bis zum Klick eintrifft.";
    const nein = knopf("Abbrechen", { zweit: true, id: "dlg-nein", slot: "footer", extra: " dialogInitialFocus" });
    const ja = knopf("Alle bestätigen", { id: "dlg-ja", slot: "footer" });
    this.q("#oben").innerHTML = def("ha-dialog")
      ? `<ha-dialog id="dlg" header-title="Alle bestätigen?" prevent-scrim-close><p>${esc(text)}</p>${nein}${ja}</ha-dialog>`
      : `<dialog id="dlg" class="fb-dialog"><h2>Alle bestätigen?</h2><p>${esc(text)}</p><div class="aktionen">${nein}${ja}</div></dialog>`;
    const dlg = this.q("#dlg");
    if (dlg.localName === "dialog" && dlg.showModal) { try { dlg.showModal(); } catch (_) { dlg.setAttribute("open", ""); } }
    if (dlg.localName === "ha-dialog") { dlg.headerTitle = "Alle bestätigen?"; dlg.preventScrimClose = true; dlg.open = true; }
    const zu = () => { this.q("#oben").innerHTML = ""; };
    this.q("#dlg-nein").addEventListener("click", zu);
    this.q("#dlg-ja").addEventListener("click", () => { zu(); this.dienst("confirm_action", { confirm_all: true }); });
    dlg.addEventListener("closed", (ev) => { if (ev.target === dlg && this.q("#dlg") === dlg) zu(); });
    dlg.addEventListener("close", (ev) => { if (ev.target === dlg && this.q("#dlg") === dlg) zu(); });
  }
}

if (typeof customElements !== "undefined" && !customElements.get("kontinuum-panel")) customElements.define("kontinuum-panel", KontinuumPanel);

/* Für die Prüfung unter Node (tests/js/panel_pruefung.js); im Browser gibt es kein module */
if (typeof module !== "undefined" && module.exports) {
  module.exports = { KontinuumPanel, discoverSensors, ausHassStates, sensorWerte, kopfWerte, modulDetails, cortexZeilen, zeilenHtml, gehirnSvg, TABS, MODULE, FARBE, esc };
}
