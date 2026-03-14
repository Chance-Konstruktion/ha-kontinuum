"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Spatial Cortex                                     ║
║  Raumwahrnehmung: Wo bin ich? Wohin gehe ich?                  ║
║                                                                  ║
║  v0.12.0 – Bewegungsmuster:                                    ║
║  Lernt Raum-Sequenzen (A → B) und kann den nächsten Raum      ║
║  vorhersagen. Plus Drei-Schicht-Anti-Bounce.                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)

SPATIAL_SEMANTICS = {"motion", "presence", "door", "tracker"}

SIGNAL_WEIGHTS = {
    "tracker": 0.9,
    "presence": 0.7,
    "motion": 0.5,     # 0.5 statt 0.3 – Motion ist Hauptsignal
    "door": 0.2,
}

DECAY_RATES = {
    "tracker": 900,    # 15 min
    "presence": 600,   # 10 min
    "motion": 300,     # 5 min statt 3 min
    "door": 180,       # 3 min
}


class RoomState:
    """Zustand eines Raumes."""
    def __init__(self, name: str):
        self.name = name
        self.probability = 0.0
        self.signals = {}      # signal_key → (weight, timestamp)
        self.motion_count = 0
        self.last_motion_time = 0


class SpatialCortex:
    """Raumwahrnehmung von KONTINUUM."""
    
    TRANSITION_COOLDOWN = 60     # 60s statt 120s
    HYSTERESIS_FACTOR = 1.2      # 1.2 statt 1.5
    CONFIRMATION_TIME = 30       # 30s statt 60s
    ACTIVE_COOLDOWN = 1800
    ACTIVE_MIN_MOTIONS = 5
    OCCUPIED_THRESHOLD = 0.25    # 0.25 statt 0.4
    
    def __init__(self):
        self.rooms = {}
        self.current_room = "unknown"
        self.last_transition_time = 0
        self.proposed_room = None
        self.proposed_since = 0
        self.total_transitions = 0
        self.bounces_prevented = 0
        self._last_active_token_time = 0
        # Bewegungsgedächtnis (v0.12.0): "room_a→room_b" → count
        self.movement_memory = {}
    
    def is_spatial_signal(self, semantic: str) -> bool:
        """Prüft ob ein Signal räumlich ist."""
        return semantic in SPATIAL_SEMANTICS
    
    def absorb(self, room: str, semantic: str, state: str,
               entity_id: str = "") -> list:
        """
        Absorbiert ein räumliches Signal.
        Returns: Liste von Transition-Tokens (meist leer oder 1-2).
        """
        if not room or room == "unknown":
            return []
        
        now = time.time()
        
        if room not in self.rooms:
            self.rooms[room] = RoomState(room)
        
        rs = self.rooms[room]
        
        # Signal registrieren
        if state in ("on", "home", "open", "detected"):
            weight = SIGNAL_WEIGHTS.get(semantic, 0.2)
            sig_key = f"{entity_id}_{semantic}"
            rs.signals[sig_key] = (weight, now)
            
            if semantic == "motion":
                rs.motion_count += 1
                rs.last_motion_time = now
        elif state in ("off", "away", "closed", "clear", "not_home"):
            sig_key = f"{entity_id}_{semantic}"
            rs.signals.pop(sig_key, None)
            
            if semantic == "tracker" and room == self.current_room:
                rs.probability *= 0.5
        
        # Alle Räume updaten (decay)
        self._update_probabilities(now)
        
        # Transition erkennen
        tokens = []
        transition = self._detect_transition(now)
        if transition:
            tokens.extend(transition)
        
        # Active-Token prüfen
        active = self._check_active_token(room, now)
        if active:
            tokens.append(active)
        
        return tokens
    
    def _update_probabilities(self, now: float):
        """Aktualisiert Wahrscheinlichkeiten aller Räume."""
        for room_name, rs in self.rooms.items():
            prob = 0.0
            expired = []
            
            for sig_key, (weight, sig_time) in rs.signals.items():
                semantic = sig_key.split("_")[-1] if "_" in sig_key else "motion"
                max_age = DECAY_RATES.get(semantic, 180)
                age = now - sig_time
                
                if age > max_age:
                    expired.append(sig_key)
                    continue
                
                freshness = 1.0 - (age / max_age)
                prob += weight * freshness
            
            for key in expired:
                del rs.signals[key]
            
            rs.probability = min(1.0, prob)
    
    def _detect_transition(self, now: float) -> list:
        """
        Erkennt Raumwechsel mit drei Schutzschichten.
        Returns: Liste von Transition-Tokens.
        """
        if not self.rooms:
            return []
        
        best_room = max(self.rooms.values(), key=lambda r: r.probability)
        
        if best_room.probability < self.OCCUPIED_THRESHOLD:
            return []
        
        if best_room.name == self.current_room:
            self.proposed_room = None
            return []
        
        current_prob = self.rooms[self.current_room].probability if self.current_room in self.rooms else 0.0
        
        # Schicht 1: Hysterese
        if best_room.probability < current_prob * self.HYSTERESIS_FACTOR:
            self.bounces_prevented += 1
            return []
        
        # Schicht 2: Confirmation
        if self.proposed_room != best_room.name:
            self.proposed_room = best_room.name
            self.proposed_since = now
            return []
        
        if (now - self.proposed_since) < self.CONFIRMATION_TIME:
            return []
        
        # Schicht 3: Cooldown
        if (now - self.last_transition_time) < self.TRANSITION_COOLDOWN:
            self.bounces_prevented += 1
            return []
        
        # Transition!
        old_room = self.current_room
        new_room = best_room.name
        self.current_room = new_room
        self.last_transition_time = now
        self.total_transitions += 1
        self.proposed_room = None

        # Bewegungsmuster lernen (v0.12.0)
        if old_room != "unknown":
            move_key = f"{old_room}→{new_room}"
            self.movement_memory[move_key] = self.movement_memory.get(move_key, 0) + 1
        
        tokens = []
        if old_room != "unknown":
            tokens.append({
                "token": f"person.left.{old_room}",
                "room": old_room,
                "semantic": "spatial",
                "state": "left",
            })
        tokens.append({
            "token": f"person.entered.{new_room}",
            "room": new_room,
            "semantic": "spatial",
            "state": "entered",
        })
        
        _LOGGER.info("Spatial: %s → %s (prob=%.2f)", old_room, new_room, best_room.probability)
        return tokens
    
    def _check_active_token(self, room: str, now: float) -> dict:
        """Erzeugt person.active.{room} Token bei genug Motion."""
        if room != self.current_room:
            return None
        
        rs = self.rooms.get(room)
        if not rs:
            return None
        
        if rs.motion_count < self.ACTIVE_MIN_MOTIONS:
            return None
        
        if (now - self._last_active_token_time) < self.ACTIVE_COOLDOWN:
            return None
        
        self._last_active_token_time = now
        rs.motion_count = 0
        
        return {
            "token": f"person.active.{room}",
            "room": room,
            "semantic": "spatial",
            "state": "active",
        }
    
    def get_current_location(self) -> str:
        """Gibt den aktuellen Raum zurück."""
        return self.current_room

    def predict_next_room(self) -> list:
        """
        Vorhersage: Welcher Raum kommt als nächstes? (v0.12.0)
        Returns: [(room, probability), ...] sortiert nach Wahrscheinlichkeit.
        """
        if self.current_room == "unknown":
            return []

        prefix = f"{self.current_room}→"
        candidates = []
        for key, count in self.movement_memory.items():
            if key.startswith(prefix) and count >= 2:
                target = key.split("→", 1)[1]
                candidates.append((target, count))

        total = sum(c for _, c in candidates)
        if total == 0:
            return []

        return [(room, round(count / total, 3))
                for room, count in sorted(candidates, key=lambda x: -x[1])][:3]

    def to_dict(self) -> dict:
        rooms_data = {}
        for name, rs in self.rooms.items():
            rooms_data[name] = {
                "probability": rs.probability,
                "motion_count": rs.motion_count,
                "last_motion_time": rs.last_motion_time,
            }
        return {
            "current_room": self.current_room,
            "rooms": rooms_data,
            "last_transition_time": self.last_transition_time,
            "total_transitions": self.total_transitions,
            "bounces_prevented": self.bounces_prevented,
            "movement_memory": self.movement_memory,
        }

    def from_dict(self, data: dict):
        self.current_room = data.get("current_room", "unknown")
        self.last_transition_time = data.get("last_transition_time", 0)
        self.total_transitions = data.get("total_transitions", 0)
        self.bounces_prevented = data.get("bounces_prevented", 0)
        self.movement_memory = data.get("movement_memory", {})
        for name, rd in data.get("rooms", {}).items():
            rs = RoomState(name)
            rs.probability = rd.get("probability", 0)
            rs.motion_count = rd.get("motion_count", 0)
            rs.last_motion_time = rd.get("last_motion_time", 0)
            self.rooms[name] = rs

    @property
    def stats(self) -> dict:
        presence = {}
        for name, rs in self.rooms.items():
            if rs.probability > 0.01:
                presence[name] = round(rs.probability, 3)
        next_room = self.predict_next_room()
        return {
            "current_room": self.current_room,
            "total_transitions": self.total_transitions,
            "bounces_prevented": self.bounces_prevented,
            "presence_map": presence,
            "predicted_next": next_room[0] if next_room else None,
            "movement_patterns": len(self.movement_memory),
        }
