'use strict';

/**
 * Der Node-Zeuge für das native KONTINUUM-Panel (frontend/kontinuum-panel.js).
 * pytest ruft diese Datei (tests/test_nativ_panel.py) und liest das Zeugnis
 * aus der letzten ZEUGNIS-Zeile.
 *
 * Es gibt kein DOM: HTMLElement und customElements sind Attrappen, das Panel
 * zeichnet nur Zeichenketten. Geprüft wird, was sich ohne Browser prüfen lässt:
 * Sensor-Erkennung, Anzeigewerte, Modullisten, die Zeichenketten der Tabs,
 * Maskierung, Abo-Weg und Dienstaufrufe. Das Aussehen in Home Assistant
 * selbst prüft das nicht.
 */

const fs = require('fs');
const path = require('path');

let pruefungen = 0;
let fehler = 0;
function pruefe(name, bedingung, detail) {
  pruefungen++;
  if (bedingung) console.log('  OK   ' + name);
  else { fehler++; console.log('  ROT  ' + name + (detail ? ' — ' + detail : '')); }
}
const tick = (ms) => new Promise((r) => setTimeout(r, ms));

/* Attrappen für das, was der Browser stellt */
const definiert = new Map();
global.customElements = { get: (n) => definiert.get(n), define: (n, k) => definiert.set(n, k), whenDefined: () => Promise.resolve() };
global.HTMLElement = class {
  attachShadow() { return { innerHTML: '', addEventListener() {}, querySelector() { return null; }, insertBefore() {} }; }
  dispatchEvent(e) { (this.ereignisse = this.ereignisse || []).push(e); return true; }
};

const DATEI = path.join(__dirname, '..', '..', 'custom_components', 'kontinuum', 'frontend', 'kontinuum-panel.js');
const quelle = fs.readFileSync(DATEI, 'utf8');
const P = require(DATEI);

(async () => {
  /* --- Anmeldung --- */
  pruefe('Custom Element kontinuum-panel ist definiert', definiert.get('kontinuum-panel') === P.KontinuumPanel);
  pruefe('vier Tabs mit eigenen Schlüsseln', JSON.stringify(P.TABS.map((t) => t[0])) === JSON.stringify(['uebersicht', 'gehirn', 'module', 'steuerung']));

  /* --- Sensor-Erkennung --- */
  const zustaende = [
    { entity_id: 'sensor.kontinuum_last_event', state: 'person.arrived', attributes: { room: 'Flur', semantic: 'presence', events_total: 7 } },
    { entity_id: 'sensor.vorhersage', state: 'light.on', attributes: { confidence: 0.42 } },
    { entity_id: 'sensor.irgendwas', state: '5', attributes: { friendly_name: 'Mein Cerebellum Zähler' } },
    { entity_id: 'sensor.kontinuum_status', state: 'active', attributes: {} },
  ];
  const d = P.discoverSensors(zustaende);
  pruefe('Erkennung per entity_id (last_event)', d.last_event && d.last_event.state === 'person.arrived');
  pruefe('Erkennung über alten Namen (sensor.vorhersage)', d.prediction && d.prediction.state === 'light.on');
  pruefe('Erkennung über friendly_name (cerebellum)', d.cerebellum && d.cerebellum.state === '5');
  pruefe('Ersatzweg: hass.states wird zur Liste', P.ausHassStates({ 'sensor.a': { state: '1', attributes: {} }, 'light.x': { state: 'on' } }).length === 1);

  /* --- Anzeigewerte --- */
  let w = P.sensorWerte(d);
  pruefe('Letztes Event: Wert und Detail', w.event.wert === 'person.arrived' && w.event.detail === 'Flur · presence · events: 7', JSON.stringify(w.event));
  pruefe('Vorhersage: Konfidenz in Prozent', w.pred.detail === 'confidence: 42%', w.pred.detail);
  pruefe('fehlender Sensor zeigt Strich', w.acc.wert === '—' && w.surprise.wert === '—');
  const mitStatus = { ...d, status: { state: 'active', attr: {
    predictive_processing: { current_surprise: 0.7, average_surprise: 0.2, learn_weight: 1.5, surprise_ratio: 0.1 },
    neurorhythms: { circadian_multiplier: 1.2, dopamine_level: 0.6, total_bursts: 3, strongest_burst: 2.5, burst_active: true, synaptic_load: 12 },
    hippocampus: { total_events: 120, patterns: 4, memory_kb: 33 },
    locus_coeruleus: { arousal: 0.75, total_events: 99 },
    prefrontal: { operation_mode: 'confirm', total_decisions: 5, overrides_detected: 1, pending_confirms_list: [
      { id: 'a1', entity_id: 'light.<b>x</b>', action: 'turn_on', room: 'Küche', confidence: 0.8, utility: 0.5, risk: 0.1, n_obs: 6, source: 'cerebellum', age_s: 20, reasoning: '<script>alert(1)</script>', context: { mode: 'active', rule_order: 2 } },
    ] },
    sleep_consolidation: { total_consolidations: 2, last_patterns_pruned: 1, last_patterns_reinforced: 3, total_dream_connections: 4, last_homeostasis_factor: 0.9 },
  } } };
  w = P.sensorWerte(mitStatus);
  pruefe('Surprise hoch = Fehlerton', w.surprise.ton === 'nok' && w.surprise.wert.includes('70%'), JSON.stringify(w.surprise));
  pruefe('Dopamin-Burst = Fehlerton', w.dopamine.ton === 'nok' && w.dopamine.wert.includes('60%'));
  pruefe('Circadian zeigt Faktor', w.circadian.wert.includes('1.20x'));
  const k = P.kopfWerte(mitStatus);
  pruefe('Kopfzeile: Status, Events, Memory', k.status === 'ACTIVE' && k.events === 120 && k.mem === '33 KB', JSON.stringify(k));
  const md = P.modulDetails(mitStatus.status.attr);
  pruefe('Locus-Text trägt Namen und Ereignisse (Fehler des alten Dashboards behoben)', md.locus === 'arousal: 0.75 · events: 99', md.locus);
  pruefe('Prefrontal zeigt Modus in Großbuchstaben', md.prefrontal.startsWith('CONFIRM'));
  pruefe('Accumbens-Text steht immer', md.accumbens.includes('Q-Ranking'));
  pruefe('Sleep-Text', md.sleep.includes('dreams: 4') && md.sleep.includes('SHY: 0.90'));
  pruefe('Modulliste hat 17 Einträge', P.MODULE.length === 17);

  /* --- Cortex-Status --- */
  pruefe('ohne Status keine Cortex-Zeilen', P.cortexZeilen(null, false) === null);
  const cz = P.cortexZeilen({ attr: { cortex: { agents: 3, sequential_mode: true, total_consultations: 2, total_discussions: 1,
    last_consensus: { consensus_action: 'turn_on', consensus_entity: 'light.a', consensus_reason: 'weil', vetoed: true, proposals: [{ agent: 'A<1>', action: 'x', entity_id: 'e', veto: true, reason: 'r', priority: 2 }] },
    }, last_brain_review: { health_score: 80, agents_consulted: 2 }, hippocampus: { total_events: 1 } } }, true);
  const ch = P.zeilenHtml(cz);
  pruefe('Cortex-Status: Konsens, Veto, Vorschlag, Review', ch.includes('LETZTER KONSENS') && ch.includes('JA') && ch.includes('[VETO]') && ch.includes('80/100'));
  pruefe('Cortex-Status maskiert Agent-Namen', ch.includes('A&lt;1&gt;') && !ch.includes('A<1>'));

  /* --- Gehirn --- */
  const svg = P.gehirnSvg();
  const regionen = ['prefrontal', 'motor', 'spatial', 'occipital', 'thalamus', 'insula', 'basalganglien', 'hypothalamus', 'amygdala', 'hippocampus', 'cerebellum', 'reticular', 'locus', 'entorhinal', 'accumbens', 'acc'];
  pruefe('alle 16 Areale sind gezeichnet', regionen.every((r) => svg.includes(`id="r-${r}"`)));
  pruefe('Gehirn hat keine festen Farbwerte (nur Theme-Variablen)', !/#[0-9a-fA-F]{3,6}\b/.test(svg) && !/rgba?\(/.test(svg));
  pruefe('jedes Areal trägt Titel und Beschreibung für den Tooltip', (svg.match(/data-t="/g) || []).length === 16 && (svg.match(/data-d="/g) || []).length === 16);

  /* --- Das Panel als Objekt --- */
  const p = new P.KontinuumPanel();
  pruefe('Route /gehirn wählt den Tab', (p._route = { prefix: '/kontinuum', path: '/gehirn' }, p._tabAusRoute() === 'gehirn'));
  pruefe('leere Route: kein Tab (Standard bleibt Übersicht)', (p._route = { prefix: '/kontinuum', path: '' }, p._tabAusRoute() === null) && p.tab === 'uebersicht');
  pruefe('unbekannter Tab wird nicht gewählt', (p._route = { path: '/gibtsnicht' }, p._tabAusRoute() === null));
  p._d = mitStatus;
  const ue = p.tabHtml('uebersicht');
  pruefe('Übersicht: Kacheln, Sensorik, Kontext', ue.includes('Sensorik') && ue.includes('Kontext') && ue.includes('Absorbed') && ue.includes('120'));
  pruefe('Übersicht nutzt ha-card nur als Rückfall (Attrappe kennt keins)', ue.includes('fb-karte'));
  const mo = p.tabHtml('module');
  pruefe('Module: 17 Zeilen', (mo.match(/class="ml"/g) || []).length === 17);
  const wa = p.wartendHtml();
  pruefe('Wartende Aktion: Entität maskiert, Begründung maskiert', wa.includes('light.&lt;b&gt;x&lt;/b&gt;') && !wa.includes('<script>') && wa.includes('&lt;script&gt;'));
  pruefe('Wartende Aktion: Ausführen, Ablehnen, Alle bestätigen', wa.includes('data-act="bestaetigen"') && wa.includes('data-act="ablehnen"') && wa.includes('data-act="alle"') && wa.includes('data-id="a1"'));
  p._d = P.discoverSensors(zustaende);
  pruefe('ohne Wartende: keine Karte', p.wartendHtml() === '');
  p._d = mitStatus;
  let st = p.tabHtml('steuerung');
  pruefe('Steuerung: drei Betriebsmodi, aktueller wird markiert', st.includes('data-m="shadow"') && st.includes('data-m="confirm"') && st.includes('data-m="active"') && st.includes('>Aktiv<'));
  pruefe('Debug-Bereich ist zunächst zu', !st.includes('Service Trigger') && st.includes('data-sw="debug"'));
  p._debug = true;
  st = p.tabHtml('steuerung');
  pruefe('Debug offen: alle sechs Dienste, Sequential, Cortex-Ausgabe', ['cortex_consult', 'brain_review', 'status', 'export_brain', 'activate', 'deactivate'].every((s) => st.includes(`data-s="${s}"`)) && st.includes('data-sw="seq"') && st.includes('Cortex Output') && st.includes('Cortex Status'));
  pruefe('Dienste mit Daten tragen sie (activate: light)', st.includes('data-p="{&quot;semantic&quot;:&quot;light&quot;}"'));

  /* --- Dienste --- */
  const ruf = [];
  p._hass = { callService: async (...a) => { ruf.push(a); } };
  await p.dienst('set_mode', { mode: 'active' });
  pruefe('Betriebsmodus geht über hass.callService (kein fetch, kein Token)', JSON.stringify(ruf[0]) === JSON.stringify(['kontinuum', 'set_mode', { mode: 'active' }]));
  pruefe('Toast über hass-notification', (p.ereignisse || []).some((e) => e.type === 'hass-notification' && e.detail.message.includes('Betriebsmodus')));
  p._hass = { callService: async () => { throw new Error('kaputt'); } };
  await p.dienst('status');
  pruefe('Fehlschlag: Log trägt ihn, Knopf wird wieder frei', p._dbgZ[0].teile[0][0].includes('kaputt') && !p._laeuft.has('status'));
  p._hass = { callService: async (...a) => { ruf.push(a); } };
  p.aktion('ablehnen', { id: 'z9' }); await tick(5);
  pruefe('Ablehnen schickt confirm_id', JSON.stringify(ruf[ruf.length - 1]) === JSON.stringify(['kontinuum', 'reject_action', { confirm_id: 'z9' }]));
  p.schalten('seq', true); await tick(5);
  pruefe('Sequential-Schalter ruft cortex_sequential', JSON.stringify(ruf[ruf.length - 1]) === JSON.stringify(['kontinuum', 'cortex_sequential', { enabled: true }]));

  /* --- Abo über hass.connection --- */
  const q = new P.KontinuumPanel();
  const nachr = []; let melder = null, abgemeldet = 0;
  q._hass = { connection: { subscribeMessage: async (cb, msg) => { nachr.push(msg); melder = cb; return () => { abgemeldet++; }; }, addEventListener() {}, removeEventListener() {} }, states: {} };
  const gesehen = []; q.verarbeiten = (liste) => gesehen.push(liste.map((z) => z.entity_id).sort().join(','));
  await q.abonnieren();
  pruefe('abonniert kontinuum/abonniere über die Verbindung von HA', nachr.length === 1 && nachr[0].type === 'kontinuum/abonniere' && q._conn === 'ok');
  melder({ art: 'stand', zustaende: [{ entity_id: 'sensor.kontinuum_a', state: '1', attributes: {} }, { entity_id: 'sensor.kontinuum_b', state: '2', attributes: {} }] });
  pruefe('Startstand zeichnet sofort', gesehen.length === 1 && gesehen[0] === 'sensor.kontinuum_a,sensor.kontinuum_b');
  melder({ art: 'aenderung', entity_id: 'sensor.kontinuum_a', neu: { entity_id: 'sensor.kontinuum_a', state: '9', attributes: {} } });
  melder({ art: 'aenderung', entity_id: 'sensor.kontinuum_b', neu: { entity_id: 'sensor.kontinuum_b', state: '8', attributes: {} } });
  pruefe('Änderungen warten auf die Ruhepause', gesehen.length === 1);
  await tick(250);
  pruefe('danach EINE Zeichnung mit beiden Änderungen', gesehen.length === 2 && q._cache['sensor.kontinuum_a'].state === '9' && q._cache['sensor.kontinuum_b'].state === '8');
  melder({ art: 'aenderung', entity_id: 'sensor.kontinuum_b', neu: null });
  await tick(250);
  pruefe('Abschied einer Entität leert den Cache', !('sensor.kontinuum_b' in q._cache));
  q.abmelden();
  pruefe('Abmelden ruft die Abmeldefunktion', abgemeldet === 1 && !q._aboOk);
  clearTimeout(q._ruhe);

  /* --- Ersatzweg --- */
  const r = new P.KontinuumPanel();
  r._hass = { connection: { subscribeMessage: async () => { throw new Error('unbekannter Befehl'); } },
    states: { 'sensor.kontinuum_status': { state: 'active', attributes: {} } } };
  const rg = []; r.verarbeiten = (l) => rg.push(l.length);
  await r.abonnieren(); await tick(20);
  pruefe('scheitert das Abo, liest das Panel hass.states und sagt es im Log', rg.length === 1 && r._logZ.some((e) => e.text.includes('hass.states')) && r._conn === 'ok');
  clearTimeout(r._ersatz);

  /* --- Keine eigene Anmeldung, keine Fremdquellen --- */
  pruefe('kein Token, kein fetch, kein localStorage im Panel', !/access_token|hassTokens|fetch\(|localStorage|\/api\//.test(quelle));
  pruefe('keine fremden Adressen', !/https?:\/\/(?!www\.w3\.org\/2000\/svg)/.test(quelle));
  const feste = quelle.match(/#[0-9a-fA-F]{3,6}\b/g) || [];
  pruefe('keine festen Farbwerte im Panel-Code außer Weiß auf dem roten Rückfall-Knopf', feste.every((c) => c === '#fff'), feste.join(','));

  console.log('ZEUGNIS ' + JSON.stringify({ pruefungen, fehler }));
  process.exit(fehler ? 1 : 0);
})();
