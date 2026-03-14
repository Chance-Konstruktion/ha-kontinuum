"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Thalamus                                           ║
║  Sensorisches Tor: Filtert, normalisiert, tokenisiert           ║
║                                                                  ║
║  Biologisches Vorbild:                                           ║
║  Der Thalamus ist die Relaisstation des Gehirns. Er filtert     ║
║  sensorische Eingaben, entfernt Rauschen und leitet relevante   ║
║  Signale an die richtigen Verarbeitungszentren weiter.          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import math
import re
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

# ── Raum-Zuordnung ──────────────────────────────────────────────

HA_AREA_MAP = {
    "schlafzimmer": "bedroom", "bedroom": "bedroom",
    "wohnzimmer": "livingroom", "living": "livingroom", "wohnbereich": "livingroom",
    "küche": "kitchen", "kitchen": "kitchen",
    "bad": "bathroom", "bath": "bathroom", "badezimmer": "bathroom",
    "flur": "hallway", "hall": "hallway", "corridor": "hallway", "diele": "hallway",
    "büro": "office", "office": "office", "arbeitszimmer": "office",
    "kinderzimmer": "kidsroom", "kids": "kidsroom",
    "garten": "outdoor", "garden": "outdoor", "terrasse": "outdoor",
    "balkon": "outdoor", "balcony": "outdoor", "outdoor": "outdoor",
    "einfahrt": "outdoor", "carport": "outdoor", "hof": "outdoor",
    "garage": "garage",
    "keller": "basement", "basement": "basement",
    "hauswirtschaft": "utility", "utility": "utility",
    "waschküche": "utility", "laundry": "utility",
    "technikraum": "utility", "heizungsraum": "utility",
    "dachboden": "attic", "attic": "attic",
    "eingang": "entrance", "entrance": "entrance", "windfang": "entrance",
    "gästezimmer": "guestroom", "guest": "guestroom",
    "esszimmer": "diningroom", "dining": "diningroom",
}

NAME_ROOM_HINTS = {
    # Deutsch
    "schlaf": "bedroom", "bett": "bedroom", "bedroom": "bedroom",
    "wohn": "livingroom", "living": "livingroom", "lounge": "livingroom",
    "küche": "kitchen", "kitchen": "kitchen", "kochen": "kitchen",
    "bad": "bathroom", "bath": "bathroom", "dusche": "bathroom", "wc": "bathroom",
    "büro": "office", "office": "office", "desk": "office", "arbeit": "office",
    "flur": "hallway", "hall": "hallway", "gang": "hallway", "diele": "hallway",
    "eingang": "entrance", "entrance": "entrance", "haustür": "entrance",
    "garten": "outdoor", "garden": "outdoor", "outdoor": "outdoor",
    "terrasse": "outdoor", "balkon": "outdoor", "terrace": "outdoor",
    "einfahrt": "outdoor", "carport": "outdoor",
    "garage": "garage",
    "keller": "basement", "basement": "basement",
    "wasch": "utility", "utility": "utility", "hauswirtschaft": "utility",
    "heizung": "utility", "technik": "utility", "server": "utility",
    "kind": "kidsroom", "kids": "kidsroom", "nursery": "kidsroom",
    "gäste": "guestroom", "guest": "guestroom",
    "dach": "attic", "attic": "attic", "speicher": "attic",
    "esszimmer": "diningroom", "dining": "diningroom",
    "fernseh": "livingroom", "tv": "livingroom", "wiz_wohn": "livingroom",
    # IP-Kamera Patterns
    "ipcam": "outdoor",
}

# ── Semantik-Zuordnung ──────────────────────────────────────────

DOMAIN_SEMANTIC = {
    "light": "light",
    "switch": "switch",
    "fan": "fan",
    "cover": "cover",
    "climate": "climate",
    "media_player": "media",
    "vacuum": "vacuum",
    "lock": "lock",
    "alarm_control_panel": "alarm",
    "automation": "automation",
    "water_heater": "water_heater",
}

SENSOR_KEYWORDS = {
    "temperature": "temperature", "temp": "temperature",
    "humidity": "humidity", "feucht": "humidity",
    "power": "power", "watt": "power", "leistung": "power",
    "energy": "energy", "energie": "energy", "kwh": "energy",
    "battery": "battery", "batterie": "battery", "akku": "battery",
    "voltage": "voltage", "spannung": "voltage",
    "illuminance": "illuminance", "lux": "illuminance", "hell": "illuminance",
    "pressure": "pressure", "druck": "pressure",
    "solar": "solar", "pv": "solar", "photovoltaic": "solar",
    "grid": "grid", "netz": "grid",
    "co2": "co2", "carbon": "co2",
}


class Thalamus:
    """
    Sensorisches Tor von KONTINUUM.
    
    Aufgaben:
    1. Entity → Raum zuordnen (aus HA Areas, Names, IDs)
    2. Entity → Semantischer Typ (light, motion, temperature, ...)
    3. State-Change → Token erzeugen (z.B. "bedroom.light.on")
    4. Duplikate filtern (gleicher Token hintereinander)
    5. Token-Vokabular verwalten (bidirektionale Map)
    """
    
    # Domains die wir komplett ignorieren
    IGNORED_DOMAINS = {
        "persistent_notification", "scene", "script", "zone",
        "input_boolean", "input_number", "input_select", "input_text",
        "input_datetime", "counter", "timer", "group", "logbook",
        "recorder", "homeassistant", "frontend", "system_log",
        "updater", "update", "tts", "stt", "conversation",
    }
    
    IGNORED_PATTERNS = [
        re.compile(r"^sensor\.kontinuum_"),
        re.compile(r"_linkquality$"),
        re.compile(r"_signal_strength$"),
        re.compile(r"_last_seen$"),
    ]
    
    def __init__(self):
        # Entity → Raum/Semantik
        self.entity_room = {}       # "sensor.temp_bedroom" → "bedroom"
        self.entity_semantic = {}   # "sensor.temp_bedroom" → "temperature"
        
        # Token-Vokabular
        self.token_to_id = {}       # "bedroom.light.on" → 42
        self.id_to_token = {}       # 42 → "bedroom.light.on"
        self._next_id = 1
        
        # Dedup
        self.entity_last_token = {} # entity_id → last token string
        
        # Stats
        self.stats = {
            "entities_registered": 0,
            "rooms_discovered": 0,
            "tokens_filtered": 0,
            "events_processed": 0,
        }
        self._known_rooms = set()
    
    def register_entity(self, entity_id: str, ha_area: str = "",
                        device_class: str = "", domain: str = "",
                        friendly_name: str = "", unit: str = ""):
        """Registriert eine Entity mit Raum und Semantik."""
        if not entity_id:
            return
        
        if not domain:
            domain = entity_id.split(".")[0] if "." in entity_id else ""
        
        if domain in self.IGNORED_DOMAINS:
            return
        
        for pat in self.IGNORED_PATTERNS:
            if pat.search(entity_id):
                return
        
        # Raum ermitteln
        room = self._resolve_room(entity_id, ha_area, friendly_name)
        
        # Semantik ermitteln
        semantic = self._resolve_semantic(entity_id, domain, device_class,
                                          friendly_name, unit)
        
        if not semantic:
            return

        # Ebene 3: Entity-Whitelist – nur Entities mit bekanntem Raum
        # Proxmox-VMs, GPU-LEDs, Batterie-Management etc. haben keinen Raum
        # und produzieren nur Ballast
        if room == "unknown":
            self.stats["entities_filtered"] = self.stats.get("entities_filtered", 0) + 1
            return

        self.entity_room[entity_id] = room
        self.entity_semantic[entity_id] = semantic

        if room not in self._known_rooms:
            self._known_rooms.add(room)
            self.stats["rooms_discovered"] = len(self._known_rooms)

        self.stats["entities_registered"] = len(self.entity_semantic)
    
    def _resolve_room(self, entity_id: str, ha_area: str, friendly_name: str) -> str:
        """Ermittelt den Raum einer Entity."""
        # 1. HA Area (beste Quelle)
        if ha_area:
            area_lower = ha_area.lower().strip()
            for pattern, room in HA_AREA_MAP.items():
                if pattern == area_lower or pattern in area_lower:
                    return room
        
        # 2. Friendly Name
        if friendly_name:
            name_lower = friendly_name.lower()
            for hint, room in NAME_ROOM_HINTS.items():
                if hint in name_lower:
                    return room
        
        # 3. Entity ID
        eid_lower = entity_id.lower()
        for hint, room in NAME_ROOM_HINTS.items():
            if hint in eid_lower:
                return room
        
        return "unknown"
    
    def _resolve_semantic(self, entity_id: str, domain: str,
                          device_class: str, friendly_name: str,
                          unit: str) -> str:
        """Ermittelt den semantischen Typ einer Entity."""
        # 1. Direkte Domain-Zuordnung
        if domain in DOMAIN_SEMANTIC:
            return DOMAIN_SEMANTIC[domain]
        
        # 2. Binary Sensor
        if domain == "binary_sensor":
            dc = (device_class or "").lower()
            if dc in ("motion", "occupancy"):
                return "motion"
            if dc in ("door", "window", "garage_door", "opening"):
                return "door"
            if dc in ("presence", "connectivity"):
                return "presence"
            
            # Name-basiert
            name = (friendly_name or entity_id).lower()
            if any(k in name for k in ("motion", "bewegung", "pir")):
                return "motion"
            if any(k in name for k in ("door", "tür", "fenster", "window")):
                return "door"
            if any(k in name for k in ("presence", "anwesen", "besetzt")):
                return "presence"
            return "binary"
        
        # 3. Sensor
        if domain == "sensor":
            return self._classify_sensor(entity_id, device_class,
                                          friendly_name, unit)
        
        # 4. Device Tracker / Person
        if domain in ("device_tracker", "person"):
            return "tracker"
        
        # 5. Button / Number
        if domain in ("button", "number"):
            return None  # Ignorieren
        
        return None
    
    def _classify_sensor(self, entity_id: str, device_class: str,
                         friendly_name: str, unit: str) -> str:
        """Klassifiziert einen Sensor nach Typ."""
        dc = (device_class or "").lower()
        name = (friendly_name or entity_id).lower()
        unit_lower = (unit or "").lower()
        
        # Device Class zuerst
        unit_map = {
            "temperature": "temperature",
            "humidity": "humidity",
            "battery": "battery",
            "power": "power",
            "energy": "energy",
            "voltage": "voltage",
            "illuminance": "illuminance",
            "pressure": "pressure",
            "co2": "co2",
        }
        if dc in unit_map:
            return unit_map[dc]
        
        # Unit-basiert
        if unit_lower in ("°c", "°f"):
            return "temperature"
        if unit_lower in ("%",) and "battery" in name:
            return "battery"
        if unit_lower in ("w", "kw"):
            return "power"
        if unit_lower in ("kwh", "wh"):
            return "energy"
        if unit_lower in ("v",):
            return "voltage"
        if unit_lower in ("lx", "lux"):
            return "illuminance"
        
        # Name-basiert
        for keyword, semantic in SENSOR_KEYWORDS.items():
            if keyword in name or keyword in entity_id.lower():
                return semantic
        
        return None
    
    def process(self, entity_id: str, new_state: str, old_state: str,
                timestamp=None) -> dict:
        """
        Verarbeitet einen State-Change und erzeugt ein Token-Signal.
        Returns None wenn gefiltert, sonst dict mit Signal-Info.
        """
        if entity_id not in self.entity_semantic:
            return None
        
        semantic = self.entity_semantic[entity_id]
        room = self.entity_room.get(entity_id, "unknown")

        # Ebene 1: Unknown-Raum = kein Token
        # Entities ohne bekannten Raum erzeugen nur Rauschen
        if room == "unknown":
            self.stats["tokens_filtered"] += 1
            return None

        # State normalisieren
        state = self._normalize_state(semantic, new_state)
        if not state:
            return None
        
        # Token bilden
        token = f"{room}.{semantic}.{state}"
        
        # Dedup: gleicher Token hintereinander für gleiche Entity
        if self.entity_last_token.get(entity_id) == token:
            self.stats["tokens_filtered"] += 1
            return None
        self.entity_last_token[entity_id] = token
        
        # Token-ID vergeben
        if token not in self.token_to_id:
            self.token_to_id[token] = self._next_id
            self.id_to_token[self._next_id] = token
            self._next_id += 1
        
        token_id = self.token_to_id[token]
        
        self.stats["events_processed"] += 1
        
        if not timestamp:
            timestamp = datetime.now(timezone.utc)
        
        return {
            "token_id": token_id,
            "token": token,
            "entity_id": entity_id,
            "room": room,
            "semantic": semantic,
            "state": state,
            "timestamp": timestamp,
        }
    
    def _normalize_state(self, semantic: str, state: str) -> str:
        """Normalisiert State-Werte für konsistente Tokens."""
        if not state or state in ("unknown", "unavailable"):
            return None
        
        state_lower = state.lower().strip()
        
        # On/Off Domains
        if semantic in ("light", "switch", "fan", "automation",
                        "motion", "door", "presence", "binary"):
            if state_lower in ("on", "true", "open", "detected", "home"):
                return "on"
            if state_lower in ("off", "false", "closed", "clear", "not_home"):
                return "off"
            return state_lower
        
        # Media
        if semantic == "media":
            if state_lower in ("playing", "on"):
                return "playing"
            if state_lower in ("paused",):
                return "paused"
            if state_lower in ("idle", "standby"):
                return "standby"
            if state_lower in ("off", "unavailable"):
                return "off"
            return state_lower
        
        # Climate
        if semantic == "climate":
            return state_lower
        
        # Cover
        if semantic == "cover":
            if state_lower in ("open", "opening"):
                return "open"
            if state_lower in ("closed", "closing"):
                return "closed"
            return state_lower
        
        # Tracker
        if semantic == "tracker":
            if state_lower in ("home", "zu hause"):
                return "home"
            if state_lower in ("not_home", "away", "abwesend"):
                return "away"
            return state_lower
        
        # Numerische Sensoren → Bucket
        if semantic in ("temperature", "humidity", "power", "energy",
                        "battery", "voltage", "illuminance", "pressure",
                        "solar", "grid", "co2"):
            return self._bucket_value(semantic, state)
        
        return state_lower if len(state_lower) < 30 else None
    
    def _bucket_value(self, semantic: str, state: str) -> str:
        """Bucketed numerische Werte in Kategorien."""
        try:
            val = float(state)
        except (ValueError, TypeError):
            return state.lower() if state else None
        
        if semantic == "temperature":
            if val < 10:
                return "cold"
            elif val < 18:
                return "cool"
            elif val < 24:
                return "comfort"
            elif val < 30:
                return "warm"
            else:
                return "very_hot"
        
        elif semantic == "humidity":
            if val < 30:
                return "dry"
            elif val < 60:
                return "normal"
            else:
                return "humid"
        
        elif semantic == "power":
            if val < 100:
                return "low"
            elif val < 1000:
                return "medium"
            else:
                return "high"
        
        elif semantic == "energy":
            return "consumed"
        
        elif semantic == "battery":
            if val < 10:
                return "critical"
            elif val < 30:
                return "low"
            elif val < 80:
                return "medium"
            else:
                return "full"
        
        elif semantic == "voltage":
            if val < 210:
                return "low"
            elif val < 240:
                return "normal"
            else:
                return "high"
        
        elif semantic == "illuminance":
            if val < 10:
                return "dark"
            elif val < 200:
                return "dim"
            elif val < 1000:
                return "bright"
            else:
                return "very_bright"
        
        elif semantic == "solar":
            if val < 10:
                return "none"
            elif val < 500:
                return "low"
            elif val < 2000:
                return "medium"
            else:
                return "high"
        
        elif semantic == "grid":
            if val < 0:
                return "export"
            elif val < 100:
                return "minimal"
            else:
                return "import"
        
        elif semantic == "co2":
            if val < 600:
                return "good"
            elif val < 1000:
                return "moderate"
            else:
                return "poor"
        
        return "medium"
    
    def decode_token(self, token_id: int) -> str:
        """Token-ID → Token-String."""
        return self.id_to_token.get(token_id, f"?{token_id}")
    
    def encode_time_context(self, timestamp) -> list:
        """
        Zeitstempel → 9-dimensionaler Kontext-Vektor.
        
        [0-1] Stunde sin/cos (zyklisch)
        [2-3] Wochentag sin/cos (zyklisch)
        [4-5] Monat sin/cos (zyklisch)
        [6]   is_weekend (0/1)
        [7-8] reserved (0)
        """
        if hasattr(timestamp, 'hour'):
            dt = timestamp
        else:
            try:
                dt = datetime.fromisoformat(str(timestamp))
            except (ValueError, TypeError):
                dt = datetime.now(timezone.utc)
        
        hour = dt.hour + dt.minute / 60.0
        dow = dt.weekday()
        month = dt.month
        
        return [
            math.sin(2 * math.pi * hour / 24),
            math.cos(2 * math.pi * hour / 24),
            math.sin(2 * math.pi * dow / 7),
            math.cos(2 * math.pi * dow / 7),
            math.sin(2 * math.pi * month / 12),
            math.cos(2 * math.pi * month / 12),
            1.0 if dow >= 5 else 0.0,
            0.0,
            0.0,
        ]
    
    # ── Persistence ──────────────────────────────────────────────
    
    def to_dict(self) -> dict:
        return {
            "entity_room": self.entity_room,
            "entity_semantic": self.entity_semantic,
            "token_to_id": self.token_to_id,
            "id_to_token": {str(k): v for k, v in self.id_to_token.items()},
            "next_id": self._next_id,
            "entity_last_token": self.entity_last_token,
            "known_rooms": list(self._known_rooms),
        }
    
    def from_dict(self, data: dict):
        self.entity_room = data.get("entity_room", {})
        self.entity_semantic = data.get("entity_semantic", {})
        self.token_to_id = data.get("token_to_id", {})
        self.id_to_token = {int(k): v for k, v in data.get("id_to_token", {}).items()}
        self._next_id = data.get("next_id", 1)
        self.entity_last_token = data.get("entity_last_token", {})
        self._known_rooms = set(data.get("known_rooms", []))
        self.stats["entities_registered"] = len(self.entity_semantic)
        self.stats["rooms_discovered"] = len(self._known_rooms)
