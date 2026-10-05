'use strict';

/**
 * Der Node-Zeuge für die KONTINUUM-Datenschicht (Durchsicht 04.10.,
 * Punkt 7). pytest ruft diese Datei (tests/test_websocket_abo.py)
 * und liest das Zeugnis aus der letzten ZEUGNIS-Zeile.
 *
 * Die Datenschicht selbst (custom_components/kontinuum/assets/
 * kontinuum-daten.js) wird UNVERÄNDERT geladen — alle Nebenwirkungen
 * (Socket, fetch, Log, Anzeige) sind hier Attrappen. Was hier grün
 * ist, ist im Browser dasselbe: nur die Fabriken sind echt.
 */

const pfad = require('path').join(
  __dirname, '..', '..', 'custom_components', 'kontinuum', 'assets', 'kontinuum-daten.js'
);
const KontinuumDatenSchicht = require(pfad).KontinuumDatenSchicht;

let pruefungen = 0;
let fehler = 0;

function pruefe(name, bedingung, detail) {
  pruefungen++;
  if (bedingung) {
    console.log('  OK   ' + name);
  } else {
    fehler++;
    console.log('  ROT  ' + name + (detail ? ' — ' + detail : ''));
  }
}

const tick = (ms) => new Promise((r) => setTimeout(r, ms));

/** Der Attrappen-Socket: der Test ist der Server. */
class Attrappe {
  constructor(url) {
    this.url = url;
    this.gesendet = [];
    this.zu = false;
    Attrappe.alle.push(this);
  }
  send(roh) { this.gesendet.push(JSON.parse(roh)); }
  close() {
    if (!this.zu) {
      this.zu = true;
      if (this.onclose) { this.onclose(); }
    }
  }
  // Server-Seite
  begruessen() { this.onmessage({ data: JSON.stringify({ type: 'auth_required' }) }); }
  annahme() { this.onmessage({ data: JSON.stringify({ type: 'auth_ok' }) }); }
  zurueckweisen() { this.onmessage({ data: JSON.stringify({ type: 'auth_invalid' }) }); }
  aboBestaetigen(id) {
    this.onmessage({ data: JSON.stringify({ id: id, type: 'result', success: true }) });
  }
  ereignis(id, ev) {
    // Nach stop() ist onmessage bewusst kapp — der Draht ist zu,
    // das Ereignis verhallt ungehört (genau das zeugt der Test).
    if (!this.onmessage) { return; }
    this.onmessage({ data: JSON.stringify({ id: id, type: 'event', event: ev }) });
  }
}
Attrappe.alle = [];

function schichtMit(optionen) {
  const protokoll = {
    conn: [], logs: [], gemalt: [], socke: [], abrufe: [],
    fehlerFetch: null,
  };
  const schicht = new KontinuumDatenSchicht(Object.assign({
    haBase: 'http://haus.local',
    holeToken: () => 'token-1',
    frischerToken: null,
    beiZustaenden: (zs) => { protokoll.gemalt.push(zs); },
    log: (t) => { protokoll.logs.push(t); },
    setConn: (s) => { protokoll.conn.push(s); },
    socketFabrik: (url) => { const s = new Attrappe(url); protokoll.socke.push(s); return s; },
    fetchFabrik: (url, headers) => {
      if (protokoll.fehlerFetch) { return Promise.reject(protokoll.fehlerFetch); }
      protokoll.abrufe.push({ url: url, headers: headers });
      return Promise.resolve({
        ok: true, status: 200,
        json: async () => [{ entity_id: 'sensor.kontinuum_status', state: 'rest-modus', attributes: {} }],
      });
    },
    ruheMs: 4,
    wartezeiten: [3, 6, 9],
    maxFehlversuche: 3,
    restTakt: 7,
    pingTakt: 100000,
    tokenTakt: 4,
    tokenVersuche: 3,
  }, optionen || {}));
  return { schicht: schicht, p: protokoll };
}

async function kompletterHandschuh(s) {
  // Begrüssung → Token → Abo → Bestätigung; gibt den Socket zurück.
  const sock = s.p.socke[s.p.socke.length - 1];
  sock.begruessen();
  sock.annahme();
  sock.aboBestaetigen(sock.gesendet[sock.gesendet.length - 1].id);
  return sock;
}

(async () => {

  // ── 1. Handshake ──
  {
    const s = schichtMit({});
    s.schicht.start();
    const sock = s.p.socke[0];
    pruefe('die Adresse ist ws://…/api/websocket',
      sock.url === 'ws://haus.local/api/websocket', sock.url);
    sock.begruessen();
    pruefe('auth_required beantwortet die Schicht mit dem Token',
      sock.gesendet.length === 1 && sock.gesendet[0].type === 'auth'
      && sock.gesendet[0].access_token === 'token-1');
    sock.annahme();
    pruefe('nach auth_ok abonniert die Schicht kontinuum/abonniere',
      sock.gesendet.length === 2 && sock.gesendet[1].type === 'kontinuum/abonniere'
      && typeof sock.gesendet[1].id === 'number');
    const aboId = sock.gesendet[1].id;
    sock.aboBestaetigen(aboId);
    pruefe('Bestätigung verbindet und meldet VERBUNDEN',
      s.schicht.verbunden === true && s.p.conn[s.p.conn.length - 1] === 'ok');
    pruefe('im WebSocket-Modus wird kein REST gerufen',
      s.p.abrufe.length === 0);
    s.schicht.stop();
  }

  // ── 2. Erster Stand zeichnet sofort ──
  {
    const s = schichtMit({});
    s.schicht.start();
    const sock = await kompletterHandschuh(s);
    sock.ereignis(sock.gesendet[1].id, {
      art: 'stand',
      zustaende: [
        { entity_id: 'sensor.kontinuum_status', state: 'aktiv', attributes: {} },
        { entity_id: 'sensor.kontinuum_prediction', state: 'warten', attributes: {} },
      ],
    });
    pruefe('der erste Stand zeichnet sofort mit beiden Entitäten',
      s.p.gemalt.length === 1 && s.p.gemalt[0].length === 2);
    s.schicht.stop();
  }

  // ── 3. Änderung reist in die Ruhe, dann EINE Zeichnung ──
  {
    const s = schichtMit({});
    s.schicht.start();
    const sock = await kompletterHandschuh(s);
    sock.ereignis(sock.gesendet[1].id, {
      art: 'stand',
      zustaende: [
        { entity_id: 'sensor.kontinuum_status', state: 'aktiv', attributes: {} },
        { entity_id: 'sensor.kontinuum_energy', state: '5', attributes: {} },
      ],
    });
    await tick(10);
    const vorher = s.p.gemalt.length;
    sock.ereignis(sock.gesendet[1].id, {
      art: 'aenderung', entity_id: 'sensor.kontinuum_status',
      neu: { entity_id: 'sensor.kontinuum_status', state: 'lernt', attributes: {} }, alt: null,
    });
    sock.ereignis(sock.gesendet[1].id, {
      art: 'aenderung', entity_id: 'sensor.kontinuum_energy',
      neu: { entity_id: 'sensor.kontinuum_energy', state: '6', attributes: {} }, alt: null,
    });
    sock.ereignis(sock.gesendet[1].id, {
      art: 'aenderung', entity_id: 'sensor.kontinuum_energy',
      neu: { entity_id: 'sensor.kontinuum_energy', state: '7', attributes: {} }, alt: null,
    });
    pruefe('während der Ruhepause zeichnet noch nichts',
      s.p.gemalt.length === vorher);
    await tick(30);
    pruefe('drei Ereignisse im Burst = EINE Zeichnung',
      s.p.gemalt.length === vorher + 1,
      'gemalt=' + s.p.gemalt.length + ' vorher=' + vorher);
    const letzte = s.p.gemalt[s.p.gemalt.length - 1];
    const energie = letzte.find((z) => z.entity_id === 'sensor.kontinuum_energy');
    pruefe('der Cache trägt den NEUEN Zustand (7)',
      energie && energie.state === '7');
    s.schicht.stop();
  }

  // ── 4. Entfernte Entität verlässt den Cache ──
  {
    const s = schichtMit({});
    s.schicht.start();
    const sock = await kompletterHandschuh(s);
    sock.ereignis(sock.gesendet[1].id, {
      art: 'stand',
      zustaende: [
        { entity_id: 'sensor.kontinuum_status', state: 'aktiv', attributes: {} },
        { entity_id: 'sensor.vorhersage', state: 'kueche', attributes: {} },
      ],
    });
    await tick(10);
    sock.ereignis(sock.gesendet[1].id, {
      art: 'aenderung', entity_id: 'sensor.vorhersage', neu: null,
      alt: { entity_id: 'sensor.vorhersage', state: 'kueche', attributes: {} },
    });
    await tick(30);
    pruefe('das Abschiedsereignis leert den Cache ehrlich',
      !s.schicht.zustaende().some((z) => z.entity_id === 'sensor.vorhersage'));
    s.schicht.stop();
  }

  // ── 5. Die Reconnect-Treppe ──
  {
    const s = schichtMit({});
    pruefe('die Treppe beginnt auf der ersten Stufe',
      s.schicht.naechsteWartezeit() === 3);
    s.schicht._versuche = 1;
    pruefe('ein Riss: die erste Stufe', s.schicht.naechsteWartezeit() === 3);
    s.schicht._versuche = 2;
    pruefe('zwei Risse: die zweite Stufe', s.schicht.naechsteWartezeit() === 6);
    s.schicht._versuche = 5;
    pruefe('jenseits aller Stufen bleibt der Deckel',
      s.schicht.naechsteWartezeit() === 9);
    s.schicht._versuche = 0;
    pruefe('zurückgesetzt beginnt die Treppe vorn', s.schicht.naechsteWartezeit() === 3);
  }

  // ── 6. Abgerissene Handshakes steigen die Treppe ──
  {
    const s = schichtMit({ wartezeiten: [3, 6, 9, 12], maxFehlversuche: 99 });
    s.schicht.start();
    // Dreimal reisst der Handschlag (Server schliesst vor auth_ok)
    for (let i = 0; i < 3; i++) {
      const sock = s.p.socke[s.p.socke.length - 1];
      sock.begruessen();
      sock.close();
      await tick(12);
    }
    pruefe('drei Risse = drei neue Versuche', s.p.socke.length === 4,
      'socke=' + s.p.socke.length);
    s.schicht.stop();
  }

  // ── 7. Der REST-Notausgang ──
  {
    const s = schichtMit({ maxFehlversuche: 3 });
    s.schicht.start();
    for (let i = 0; i < 3; i++) {
      const sock = s.p.socke[s.p.socke.length - 1];
      sock.begruessen();
      sock.close();
      await tick(12);
    }
    await tick(20);
    pruefe('nach dem dritten Riss greift der Notausgang',
      s.schicht.statistik().restModus === true);
    pruefe('der Notausgang ruft /api/states mit dem Token',
      s.p.abrufe.length >= 1
      && s.p.abrufe[0].url === 'http://haus.local/api/states'
      && s.p.abrufe[0].headers['Authorization'] === 'Bearer token-1');
    pruefe('der Notausgang zeichnet die REST-Zustände',
      s.p.gemalt.some((zs) => zs.some((z) => z.entity_id === 'sensor.kontinuum_status'
        && z.state === 'rest-modus')));
    await tick(40);
    pruefe('der Notausgang pollt im Takt (mehrere Abrufe)',
      s.p.abrufe.length >= 2, 'abrufe=' + s.p.abrufe.length);
    pruefe('der Notausgang meldet sich ehrlich im Log',
      s.p.logs.some((t) => t.indexOf('Notausgang') !== -1));
    s.schicht.stop();
  }

  // ── 8. auth_invalid mit frischem Token: sofort neu, ohne Zähler ──
  {
    let token = 'alt';
    const s = schichtMit({
      holeToken: () => token,
      frischerToken: () => { token = 'neu'; return true; },
    });
    s.schicht.start();
    const sock1 = s.p.socke[0];
    sock1.begruessen();
    sock1.zurueckweisen();
    await tick(2);
    pruefe('auth_invalid verbindet sofort neu', s.p.socke.length === 2,
      'socke=' + s.p.socke.length);
    const sock2 = s.p.socke[1];
    sock2.begruessen();
    pruefe('der zweite Versuch trägt das NEUE Token',
      sock2.gesendet.length === 1 && sock2.gesendet[0].access_token === 'neu');
    sock2.annahme();
    sock2.aboBestaetigen(sock2.gesendet[1].id);
    pruefe('kein Fehlversuch wurde gezählt (frisches Token ist kein Fehler)',
      s.schicht.statistik().handshakesGescheitert === 0);
    s.schicht.stop();
  }

  // ── 9. stop() räumt ab ──
  {
    const s = schichtMit({});
    s.schicht.start();
    const sock = await kompletterHandschuh(s);
    s.schicht.stop();
    await tick(10);
    pruefe('stop() schliesst den Socket', sock.zu === true);
    pruefe('stop() nimmt die Verbindung zurück',
      s.schicht.verbunden === false);
    const gemaltVorher = s.p.gemalt.length;
    sock.ereignis(sock.gesendet[1].id, {
      art: 'aenderung', entity_id: 'sensor.kontinuum_status',
      neu: { entity_id: 'sensor.kontinuum_status', state: 'nach-stop', attributes: {} }, alt: null,
    });
    await tick(30);
    pruefe('nach stop() zeichnet nichts mehr',
      s.p.gemalt.length === gemaltVorher);
  }

  console.log('ZEUGNIS ' + JSON.stringify({ pruefungen: pruefungen, fehler: fehler }));
  process.exit(fehler > 0 ? 1 : 0);

})().catch((e) => {
  console.error('HARNESS-STURZ: ' + (e && e.stack || e));
  console.log('ZEUGNIS ' + JSON.stringify({ pruefungen: pruefungen, fehler: fehler + 1 }));
  process.exit(1);
});
