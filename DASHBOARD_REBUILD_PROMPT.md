# KONTINUUM Dashboard – Rebuild-Anleitung für DeepSeek

## Datei: `www/kontinuum.html`

Du bearbeitest das Dashboard einer Home Assistant Custom Integration namens KONTINUUM.
Die Datei ist eine einzelne HTML-Datei mit eingebettetem CSS und JavaScript.

---

## 3 Änderungen durchführen:

### 1. AUTH-SYSTEM KOMPLETT NEU (JavaScript)

**Problem:** Zeile 372 enthält einen hardcodierten Long-Lived Access Token:
```js
const HA_TOKEN = 'eyJhbGciOi...';
```

**Lösung:** Ersetze die gesamte Authentifizierung durch dieses System:

```js
// ── AUTH ──
// Priorität 1: HA-Iframe (same-origin, kein Token nötig)
// Priorität 2: localStorage Token (für Standalone-Zugriff)
// Priorität 3: Token-Eingabe-UI anzeigen

const HA_BASE = window.location.origin;
let HA_TOKEN = '';

function getAuthHeaders() {
  if (isInsideHA()) {
    // Im HA-Iframe: same-origin credentials, kein Bearer Token
    return {};
  }
  return HA_TOKEN ? { 'Authorization': 'Bearer ' + HA_TOKEN } : {};
}

function getFetchOptions() {
  const opts = { headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' } };
  if (isInsideHA()) {
    opts.credentials = 'same-origin';
  }
  return opts;
}

function isInsideHA() {
  try {
    // Wenn wir im HA-Iframe sind, hat parent denselben Origin
    return window.parent !== window && window.parent.location.origin === window.location.origin;
  } catch(e) {
    // Cross-origin = nicht im HA-Iframe
    return false;
  }
}

function initAuth() {
  // Versuch 1: Im HA-Iframe → kein Token nötig
  if (isInsideHA()) {
    startPolling();
    return;
  }

  // Versuch 2: Token aus localStorage
  const saved = localStorage.getItem('kontinuum_ha_token');
  if (saved) {
    HA_TOKEN = saved;
    startPolling();
    return;
  }

  // Versuch 3: Token-Eingabe anzeigen
  showTokenInput();
}

function showTokenInput() {
  document.getElementById('token-overlay').style.display = 'flex';
}

function submitToken() {
  const input = document.getElementById('token-input');
  const token = input.value.trim();
  if (!token) return;
  HA_TOKEN = token;
  localStorage.setItem('kontinuum_ha_token', token);
  document.getElementById('token-overlay').style.display = 'none';
  startPolling();
}

function clearToken() {
  localStorage.removeItem('kontinuum_ha_token');
  HA_TOKEN = '';
  connected = false;
  setConn('err');
  showTokenInput();
}

function startPolling() {
  setConn('wait');
  fetchSensors();
  setInterval(fetchSensors, POLL_INTERVAL);
}
```

**fetchSensors() ändern** – ersetze den `fetch`-Aufruf:
```js
// ALT:
const resp = await fetch(HA_BASE + '/api/states', {
  headers: { 'Authorization': 'Bearer ' + HA_TOKEN, 'Content-Type': 'application/json' }
});

// NEU:
const resp = await fetch(HA_BASE + '/api/states', getFetchOptions());
```

**Fehlerbehandlung in fetchSensors()** – bei 401/403 Token löschen:
```js
if (!resp.ok) {
  if (resp.status === 401 || resp.status === 403) {
    clearToken();
    log('Token ungültig – bitte neu eingeben', 'var(--red)');
  }
  if (!connected) setConn('err');
  return;
}
```

**Am Ende der Datei** – ersetze den alten Start-Block:
```js
// ALT:
setConn('wait');
fetchSensors();
setInterval(fetchSensors, POLL_INTERVAL);

// NEU:
initAuth();
```

**Token-Eingabe-UI** – füge dieses HTML direkt nach `<body>` ein (vor `<div class="tip">`):
```html
<div id="token-overlay" style="display:none;position:fixed;inset:0;z-index:999;
  background:rgba(6,8,15,0.95);display:none;align-items:center;justify-content:center">
  <div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;
    padding:32px;max-width:420px;width:90%;text-align:center">
    <h2 style="font-family:'Orbitron',sans-serif;font-size:1rem;letter-spacing:3px;
      background:linear-gradient(135deg,var(--blue),var(--cyan));
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px">
      KONTINUUM</h2>
    <p style="color:var(--t2);font-size:.7rem;margin-bottom:20px;line-height:1.6">
      Standalone-Modus: Erstelle einen Long-Lived Access Token in<br>
      Home Assistant → Profil → Sicherheit → Token erstellen</p>
    <input id="token-input" type="password" placeholder="Token einfügen..."
      style="width:100%;padding:10px 14px;background:rgba(5,5,16,.6);border:1px solid var(--border);
      border-radius:8px;color:var(--t1);font-family:'JetBrains Mono',monospace;font-size:.7rem;
      margin-bottom:12px;outline:none" onkeydown="if(event.key==='Enter')submitToken()">
    <button onclick="submitToken()" style="width:100%;padding:10px;background:var(--blue);
      color:white;border:none;border-radius:8px;font-family:'JetBrains Mono',monospace;
      font-size:.7rem;cursor:pointer;letter-spacing:1px">VERBINDEN</button>
  </div>
</div>
```

**Lösche** die Konstante `const HA_TOKEN = 'eyJhbGciOi...';` komplett (Zeile 372).

---

### 2. BASALGANGLIEN IM SVG AKTIVIEREN (HTML)

Finde die SVG-Region für die Basalganglien (ca. Zeile 268-273):
```html
<!-- BASALGANGLIEN – lateral to thalamus (placeholder) -->
<ellipse id="r-basalganglien" class="br" cx="298" cy="195" rx="22" ry="14"
         fill="#f97316" stroke="#f97316" filter="url(#gs)"
         data-m="basalganglien" data-t="Basalganglien"
         data-d="PLATZHALTER – Phase 4: Gewohnheits-Prior. Erfolgsquote pro Aktion."/>
<text class="bl" x="298" y="198">Basal</text>
```

Ändere zu (class `br` → `br on`, Text `bl` → `bl on`, neue Beschreibung):
```html
<!-- BASALGANGLIEN – lateral to thalamus -->
<ellipse id="r-basalganglien" class="br on" cx="298" cy="195" rx="22" ry="14"
         fill="#f97316" stroke="#f97316" filter="url(#gs)"
         data-m="basalganglien" data-t="Basalganglien"
         data-d="Belohnungslernen: Q-Values, Go/NoGo-Pathway, Gewohnheitsbildung. Dopamin-Signal steuert Lernrate."/>
<text class="bl on" x="298" y="198">Basal</text>
```

---

### 3. BASALGANGLIEN IN MODUL-LISTE AKTIVIEREN (HTML + JavaScript)

**HTML** – Finde in der rechten Spalte (Module-Panel, ca. Zeile 340):
```html
<div class="ml off"><div class="ml-n"><span class="dot" style="background:#f97316"></span> Basalganglien</div><div class="ml-d">Phase 4</div></div>
```

Ändere zu (entferne `off`, füge `id` hinzu):
```html
<div class="ml" id="m-basalganglien"><div class="ml-n"><span class="dot" style="background:#f97316"></span> Basalganglien</div><div class="ml-d" id="md-basalganglien">—</div></div>
```

**JavaScript** – Im `SENSORS`-Array (ca. Zeile 374), füge hinzu:
```js
'sensor.kontinuum_basal_ganglia'
```

**JavaScript** – In der `updateDashboard(d)`-Funktion, nach dem Cerebellum-Block und vor dem Status-Block, füge hinzu:
```js
// ── Basal Ganglia ──
const bg = d['sensor.kontinuum_basal_ganglia'];
if (bg) {
  document.getElementById('md-basalganglien').textContent =
    'habits: ' + (bg.attr.total_habits || 0) +
    ' · q: ' + (bg.attr.q_entries || 0) +
    ' · dopamin: ' + (bg.attr.dopamine_signal || 0);
}
```

**JavaScript** – Im `fire()`-Logik-Block in `updateDashboard`, wo Events die Regionen zum Leuchten bringen, füge einen Fall für Basalganglien hinzu. Nach der `fire('hippocampus')` Zeile:
```js
fire('basalganglien'); // Basalganglien feuern bei jedem neuen Event mit
```

---

## Zusammenfassung der Änderungen

| Was | Vorher | Nachher |
|-----|--------|---------|
| Auth | Hardcoded Token | same-origin (Iframe) + localStorage + Token-UI |
| Basal Ganglia SVG | `class="br"` (inaktiv, grau) | `class="br on"` (aktiv, leuchtend) |
| Basal Ganglia Modul-Liste | `class="ml off"` ("Phase 4") | Aktiv mit Live-Daten |
| Basal Ganglia Sensor | Nicht abgefragt | `sensor.kontinuum_basal_ganglia` wird gepollt |
| Token-Sicherheit | Token im Quellcode | Kein Token im Code, localStorage oder same-origin |

## WICHTIG
- Ändere NUR die beschriebenen Stellen
- Behalte ALLES andere exakt bei (CSS, SVG, Layout, andere Sensor-Logik)
- Die Datei muss weiterhin eine einzelne, selbstständige HTML-Datei sein
- Gib die KOMPLETTE Datei aus, nicht nur Diffs
