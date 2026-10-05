/**
 * KONTINUUM-Datenschicht — das WebSocket-Abo (Durchsicht 04.10., Punkt 7).
 *
 * Der Befund: das Dashboard holte alle 3 s ALLE Zustände über /api/states,
 * je offenem Tab. Diese Schicht dreht den Fluss:
 *
 *   1. Token besorgen (Eltern-Frame, localStorage, External Auth —
 *      wie bisher, das Wohnen der Tokens bleibt dem Dashboard).
 *   2. EINE WebSocket-Verbindung nach /api/websocket, Handshake
 *      (auth_required → auth → auth_ok), dann EIN Abo:
 *      `kontinuum/abonniere` — serverseitig gefiltert auf die
 *      Kontinuum-Entitäten (die Integration entscheidet, wer dazugehört,
 *      nicht das Dashboard).
 *   3. Das Startereignis (art: "stand") füllt den Cache — die
 *      REST-Ausgangsrunde entfällt ganz.
 *   4. Jede Änderung (art: "aenderung") aktualisiert den Cache;
 *      Änderungen sammeln sich in einer Ruhepause (Standard 150 ms),
 *      dann EINE Benachrichtigung an die Zeichnung — nicht je Ereignis.
 *   5. Fällt die Verbindung, wächst die Wartezeit (1, 2, 4, 8, 15 s —
 *      Deckel 15 s) und der nächste Versuch kommt von selbst; nach
 *      erfolgreicher Wiederverbindung fällt die Treppe auf den Anfang.
 *      Kommt der Handshake wiederholt gar nicht zustande (z. B. ein
 *      Proxy, der WebSocket verschluckt), greift der REST-Notausgang:
 *      der alte Takt — ehrlich gemeldet, nicht versteckt.
 *
 * Die Schicht weiss nichts vom DOM: alle Nebenwirkungen (Log, Verbindungs-
 * anzeige, Zeichnung) und alle Fabriken (Socket, fetch) werden von aussen
 * injiziert — deshalb läuft dieselbe Datei unverändert im Browser UND
 * unter Node in der Prüfung (tests/js/daten_schicht_pruefung.js).
 */
(function (wurzel, definition) {
  'use strict';
  var modul = definition();
  if (typeof module !== 'undefined' && module.exports) {
    // Node: die Prüfung greift direkt UND über .KontinuumDatenSchicht zu
    module.exports = modul;
    modul.KontinuumDatenSchicht = modul;
  } else {
    wurzel.KontinuumDatenSchicht = modul; // Browser: global, kein Modul-Laden nötig
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {

  var ABO_TYP = 'kontinuum/abonniere';

  function KontinuumDatenSchicht(optionen) {
    optionen = optionen || {};
    if (!optionen.beiZustaenden) {
      throw new Error('KontinuumDatenSchicht braucht beiZustaenden (states[]) => void');
    }

    // ── Injizierte Nebenwirkungen ──
    this._haBase = optionen.haBase || '';
    this._holeToken = optionen.holeToken || function () { return null; };
    this._frischerToken = optionen.frischerToken || null;  // () => bool: NEU gelesen
    this._beiZustaenden = optionen.beiZustaenden;
    this._log = optionen.log || function () {};
    this._setConn = optionen.setConn || function () {};

    // ── Fabriken (im Browser echt, in der Prüfung Attrappen) ──
    var selbst = this;
    this._socketFabrik = optionen.socketFabrik || function (url) {
      return new wurzel.WebSocket(url);
    };
    this._fetchFabrik = optionen.fetchFabrik || function (url, headers) {
      return wurzel.fetch(url, { headers: headers });
    };

    // ── Takte ──
    this._ruheMs = optionen.ruheMs !== undefined ? optionen.ruheMs : 150;
    this._wartezeiten = optionen.wartezeiten || [1000, 2000, 4000, 8000, 15000];
    this._maxFehlversuche = optionen.maxFehlversuche !== undefined ? optionen.maxFehlversuche : 5;
    this._restTakt = optionen.restTakt !== undefined ? optionen.restTakt : 3000;
    this._pingTakt = optionen.pingTakt !== undefined ? optionen.pingTakt : 25000;
    this._tokenTakt = optionen.tokenTakt !== undefined ? optionen.tokenTakt : 1000;
    this._tokenVersuche = optionen.tokenVersuche !== undefined ? optionen.tokenVersuche : 10;

    // ── innerer Zustand ──
    this._cache = {};              // entity_id → Zustandsobjekt (REST-Gestalt)
    this._verbunden = false;       // ein lebendiges Abo (für Zeuge `verbunden`)
    this._jeAbonniert = false;     // einmal geklappt → WS bleibt erste Wahl
    this._versuche = 0;            // gescheiterte Handshakes in Folge
    this._schluss = false;         // stop() gerufen
    this._naechsteId = 1;
    this._sock = null;
    this._aboId = null;
    this._token = null;
    this._ruheTimer = null;
    this._verbindeTimer = null;
    this._pingTimer = null;
    this._restTimer = null;
    this._restAktiv = false;
    this._tokenTimer = null;
    this._tokenFehlversuche = 0;
    this._stats = {
      ereignisse: 0,       // alle Abo-Ereignisse vom Draht
      benachrichtigt: 0,   // Aufrufe der Zeichnung
      verbindungen: 0,     // erfolgreiche Abonnements
      handshakesGescheitert: 0,
      restAbrufe: 0,
    };
  }

  KontinuumDatenSchicht.prototype.start = function () {
    this._schluss = false;
    this._tokenWarten(0);
  };

  KontinuumDatenSchicht.prototype.stop = function () {
    this._schluss = true;
    this._timerAbräumen();
    if (this._sock) {
      try { this._sock.onclose = null; } catch (e) { /* schon weg */ }
      try { this._sock.onmessage = null; } catch (e) { /* schon weg */ }
      try { this._sock.onerror = null; } catch (e) { /* schon weg */ }
      try { this._sock.close(); } catch (e) { /* schon weg */ }
      this._sock = null;
    }
    this._verbunden = false;
    this._setConn('wait');
  };

  /** Der Zustands-Cache als Array (REST-Gestalt) — Zeuge für die Prüfung. */
  KontinuumDatenSchicht.prototype.zustaende = function () {
    var cache = this._cache;
    return Object.keys(cache).map(function (k) { return cache[k]; });
  };

  Object.defineProperty(KontinuumDatenSchicht.prototype, 'verbunden', {
    get: function () { return this._verbunden; },
  });

  /** Zahlen für Diagnose und Prüfung. */
  KontinuumDatenSchicht.prototype.statistik = function () {
    var s = {};
    for (var k in this._stats) { s[k] = this._stats[k]; }
    s.cacheGroesse = Object.keys(this._cache).length;
    s.restModus = this._restAktiv;
    return s;
  };

  /** Die nächste Wartezeit der Reconnect-Treppe (reiner Zeuge). */
  KontinuumDatenSchicht.prototype.naechsteWartezeit = function () {
    if (this._versuche <= 0) { return this._wartezeiten[0]; }
    var i = Math.min(this._versuche - 1, this._wartezeiten.length - 1);
    return this._wartezeiten[i];
  };

  // ── Token-Warte (Mobile App braucht manchmal einen Moment) ──

  KontinuumDatenSchicht.prototype._tokenWarten = function (versuch) {
    if (this._schluss) { return; }
    var token = this._holeToken();
    if (token) {
      this._tokenFehlversuche = 0;
      this._token = token;
      this._verbinde();
      return;
    }
    if (versuch === 0) { this._setConn('wait'); }
    if ((versuch + 1) % 5 === 0) {
      this._log('Auth-Token nicht gefunden – HA-Seite neu laden oder App neu starten');
    }
    if (versuch + 1 >= this._tokenVersuche) {
      this._setConn('err');
      return; // aufgegeben — ein Seitenladen startet frisch
    }
    var selbst = this;
    this._tokenTimer = setTimeout(function () { selbst._tokenWarten(versuch + 1); }, this._tokenTakt);
  };

  // ── Verbindung und Handshake ──

  KontinuumDatenSchicht.prototype._verbinde = function () {
    if (this._schluss || this._restAktiv) { return; }
    var url = this._haBase.replace(/^http/, 'ws') + '/api/websocket';
    this._setConn('wait');
    var sock;
    try {
      sock = this._socketFabrik(url);
    } catch (fehler) {
      this._handshakeGescheitert(fehler);
      return;
    }
    this._sock = sock;
    var selbst = this;
    sock.onopen = function () { /* der Server begrüsst zuerst */ };
    sock.onmessage = function (m) { selbst._nachricht(m.data); };
    sock.onerror = function () { /* onclose folgt immer */ };
    sock.onclose = function () { selbst._geschlossen(); };
  };

  KontinuumDatenSchicht.prototype._senden = function (obj) {
    if (this._sock) { this._sock.send(JSON.stringify(obj)); }
  };

  KontinuumDatenSchicht.prototype._nachricht = function (roh) {
    var msg;
    try { msg = JSON.parse(roh); } catch (e) { return; }
    if (msg.type === 'auth_required') {
      this._senden({ type: 'auth', access_token: this._token });
    } else if (msg.type === 'auth_ok') {
      this._aboId = this._naechsteId++;
      this._senden({ id: this._aboId, type: ABO_TYP });
    } else if (msg.type === 'auth_invalid') {
      // Token abgelaufen — frisch lesen und sofort NEU verbinden,
      // ohne Fehlzähler (das alte Socket schliesst der Server).
      var neu = this._frischerToken && this._frischerToken();
      if (neu) {
        if (this._sock) {
          try { this._sock.onclose = null; this._sock.close(); } catch (e) { /* schon weg */ }
          this._sock = null;
        }
        this._token = this._holeToken();
        this._verbinde();
      } else {
        this._handshakeGescheitert(new Error('auth_invalid'));
      }
    } else if (msg.type === 'result') {
      if (msg.id === this._aboId) {
        if (msg.success) { this._abonniert(); }
        else { this._handshakeGescheitert(new Error('Abonnement abgelehnt')); }
      } // pong-Ergebnisse und andere IDs: nur Herzschlag
    } else if (msg.type === 'pong') {
      // Herzschlag-Bestätigung
    } else if (msg.type === 'event') {
      if (msg.id === this._aboId) { this._ereignis(msg.event); }
    }
  };

  KontinuumDatenSchicht.prototype._abonniert = function () {
    this._verbunden = true;
    this._jeAbonniert = true;
    this._versuche = 0; // die Treppe fällt auf den Anfang
    this._stats.verbindungen++;
    this._setConn('ok');
    this._log('Verbunden mit Home Assistant (WebSocket-Abo)');
    var selbst = this;
    this._pingTimer = setInterval(function () {
      selbst._senden({ id: selbst._naechsteId++, type: 'ping' });
    }, this._pingTakt);
  };

  KontinuumDatenSchicht.prototype._ereignis = function (ev) {
    if (!ev || !ev.art) { return; }
    this._stats.ereignisse++;
    if (ev.art === 'stand') {
      this._cache = {};
      var liste = ev.zustaende || [];
      for (var i = 0; i < liste.length; i++) {
        if (liste[i] && liste[i].entity_id) { this._cache[liste[i].entity_id] = liste[i]; }
      }
      this._benachrichtige(true); // der erste Stand zeichnet sofort
    } else if (ev.art === 'aenderung') {
      if (ev.neu && ev.neu.entity_id) {
        this._cache[ev.neu.entity_id] = ev.neu;
      } else if (ev.entity_id) {
        delete this._cache[ev.entity_id]; // Abschied: Entität entfernt
      }
      this._benachrichtige(false);
    }
  };

  // ── Ruhepause: Bursts sammeln sich, EINE Zeichnung ──

  KontinuumDatenSchicht.prototype._benachrichtige = function (sofort) {
    var selbst = this;
    if (sofort) {
      if (this._ruheTimer !== null) {
        clearTimeout(this._ruheTimer);
        this._ruheTimer = null;
      }
      this._rufe();
      return;
    }
    if (this._ruheTimer !== null) { return; } // eine Zeichnung ist schon geplant
    this._ruheTimer = setTimeout(function () {
      selbst._ruheTimer = null;
      selbst._rufe();
    }, this._ruheMs);
  };

  KontinuumDatenSchicht.prototype._rufe = function () {
    this._stats.benachrichtigt++;
    try {
      this._beiZustaenden(this.zustaende());
    } catch (fehler) {
      this._log('Zeichnungs-Fehler: ' + (fehler && fehler.message));
    }
  };

  // ── Sturz und Wiederaufstieg ──

  KontinuumDatenSchicht.prototype._handshakeGescheitert = function (fehler) {
    this._stats.handshakesGescheitert++;
    this._versuche++;
    if (this._pingTimer !== null) { clearInterval(this._pingTimer); this._pingTimer = null; }
    try { if (this._sock) { this._sock.onclose = null; this._sock.close(); } } catch (e) { /* schon weg */ }
    this._sock = null;
    if (this._schluss) { return; }

    if (!this._jeAbonniert && this._versuche >= this._maxFehlversuche) {
      this._restModus(); // Notausgang: der alte Takt, ehrlich gemeldet
      return;
    }
    var warte = this.naechsteWartezeit();
    var selbst = this;
    this._verbindeTimer = setTimeout(function () { selbst._verbinde(); }, warte);
  };

  KontinuumDatenSchicht.prototype._geschlossen = function () {
    // onclose: der Sturz einer (fast) bestehenden Verbindung.
    if (this._pingTimer !== null) { clearInterval(this._pingTimer); this._pingTimer = null; }
    var warAbonniert = this._verbunden;
    this._verbunden = false;
    if (this._schluss || this._restAktiv) { return; }
    if (!warAbonniert && !this._jeAbonniert) {
      // Der Handshake riss ab (Server weg, Proxy verschluckt) — als
      // Fehlversuch werten und die Treppe steigen.
      this._handshakeGescheitert(new Error('Verbindung im Handshake gerissen'));
      return;
    }
    this._setConn('err');
    var warte = this.naechsteWartezeit();
    var selbst = this;
    this._verbindeTimer = setTimeout(function () { selbst._verbinde(); }, warte);
  };

  // ── REST-Notausgang (der alte Weg, nur wenn WebSocket strukturell tot) ──

  KontinuumDatenSchicht.prototype._restModus = function () {
    this._restAktiv = true;
    this._verbunden = false;
    this._log('WebSocket nicht erreichbar – REST-Takt als Notausgang (alle 3 s)');
    this._setConn('wait');
    this._restHolen();
    var selbst = this;
    this._restTimer = setInterval(function () { selbst._restHolen(); }, this._restTakt);
  };

  KontinuumDatenSchicht.prototype._restHolen = function () {
    if (this._schluss) { return; }
    var selbst = this;
    var token = this._holeToken();
    if (!token) {
      if (this._frischerToken && this._frischerToken()) {
        token = this._holeToken();
      }
      if (!token) { this._setConn('err'); return; }
    }
    var versprechen = this._fetchFabrik(this._haBase + '/api/states', {
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json',
    });
    Promise.resolve(versprechen).then(function (resp) {
      if (resp.status === 401) {
        // Token abgelaufen — frisch lesen und einmal wiederholen
        if (selbst._frischerToken && selbst._frischerToken()) {
          selbst._restHolen();
        } else {
          selbst._setConn('err');
        }
        return;
      }
      if (!resp.ok) { selbst._setConn('err'); return; }
      return resp.json().then(function (states) {
        selbst._stats.restAbrufe++;
        selbst._verbunden = true;
        selbst._setConn('ok');
        selbst._cache = {};
        for (var i = 0; i < states.length; i++) {
          if (states[i] && states[i].entity_id) { selbst._cache[states[i].entity_id] = states[i]; }
        }
        selbst._benachrichtige(true);
      });
    }).catch(function (fehler) {
      selbst._verbunden = false;
      selbst._setConn('err');
    });
  };

  KontinuumDatenSchicht.prototype._timerAbräumen = function () {
    var t = [this._ruheTimer, this._verbindeTimer, this._tokenTimer];
    for (var i = 0; i < t.length; i++) { if (t[i] !== null) { clearTimeout(t[i]); } }
    if (this._pingTimer !== null) { clearInterval(this._pingTimer); }
    if (this._restTimer !== null) { clearInterval(this._restTimer); }
    this._ruheTimer = this._verbindeTimer = this._tokenTimer = null;
    this._pingTimer = this._restTimer = null;
  };

  return KontinuumDatenSchicht;
});
