"""
╔══════════════════════════════════════════════════════════════════╗
║  KONTINUUM – Hypothalamus                                       ║
║  Homöostase-Monitor: Energie, Klima, Umwelt                    ║
║                                                                  ║
║  Biologisches Vorbild:                                           ║
║  Der Hypothalamus reguliert das innere Gleichgewicht –          ║
║  Temperatur, Hunger, Schlaf-Wach-Rhythmus. Hier überwacht      ║
║  er Energie (Batterie, Solar, Verbrauch) und Klima              ║
║  (Temperatur, Helligkeit, Heizung).                             ║
║                                                                  ║
║  Absorbiert ~95% der Events (Energie/Klima-Rauschen) und       ║
║  gibt nur bei signifikanten Änderungen Tokens weiter.           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import time

_LOGGER = logging.getLogger(__name__)

ENERGY_SEMANTICS = {"battery", "voltage", "power", "energy", "solar", "grid"}
CLIMATE_SEMANTICS = {"temperature", "humidity", "illuminance", "pressure", "co2"}

STATE_TO_LEVEL = {
    "critical": 0, "low": 0, "none": 0, "cold": 0, "dry": 0, "dark": 0,
    "export": 0, "good": 0,
    "niedrig": 1, "wenig": 1, "cool": 1, "dim": 1, "minimal": 1,
    "moderate": 1, "normal": 1,
    "medium": 2, "mittel": 2, "comfort": 2, "bright": 2, "import": 2,
    "full": 3, "high": 3, "viel": 3, "warm": 3, "very_bright": 3,
    "very_hot": 4, "hot": 4, "humid": 3, "poor": 3,
    "lädt": 3, "charging": 3,
}


class HomeoState:
    """Aktueller Homöostase-Zustand."""
    def __init__(self):
        self.battery_state = 2
        self.solar_state = 0
        self.power_consumption = 1
        self.grid_state = 1
        self.indoor_temp = 2
        self.outdoor_temp = 1
        self.humidity = 1
        self.brightness = 1
        self.heating_active = False
        self.heating_demand = 0
    
    def to_context_vector(self) -> list:
        """6-dimensionaler Kontextvektor (0-1 normalisiert)."""
        return [
            self.battery_state / 3.0,
            self.solar_state / 3.0,
            self.power_consumption / 3.0,
            min(self.indoor_temp / 4.0, 1.0),
            self.brightness / 3.0,
            1.0 if self.heating_active else 0.0,
        ]


class Hypothalamus:
    """Homöostase-Monitor von KONTINUUM."""
    
    ENERGY_COOLDOWN = 600     # 10 min statt 30 min
    CLIMATE_COOLDOWN = 1800   # 30 min statt 60 min
    
    def __init__(self):
        self.state = HomeoState()
        self.events_absorbed = 0
        self.last_energy_state = None
        self.last_climate_state = None
        self._last_energy_event_time = 0
        self._last_climate_event_time = 0
    
    def is_hypothalamus_signal(self, semantic: str) -> bool:
        """Prüft ob ein Signal vom Hypothalamus absorbiert werden soll."""
        return semantic in ENERGY_SEMANTICS or semantic in CLIMATE_SEMANTICS
    
    def absorb(self, room: str, semantic: str, state: str,
               entity_id: str = "") -> dict:
        """
        Absorbiert ein Energie/Klima-Event und aktualisiert den Zustand.
        Returns: Transition-Token dict wenn signifikante Änderung, sonst None.
        """
        self.events_absorbed += 1
        level = STATE_TO_LEVEL.get(state, 1)
        
        # Energie-Zustand updaten
        if semantic == "battery":
            self.state.battery_state = level
        elif semantic == "solar":
            self.state.solar_state = level
        elif semantic == "power":
            self.state.power_consumption = level
        elif semantic == "grid":
            self.state.grid_state = level
        elif semantic == "voltage":
            pass  # Nur absorbieren
        elif semantic == "energy":
            pass  # Nur absorbieren
        
        # Klima-Zustand updaten
        elif semantic == "temperature":
            if "outdoor" in (room or "") or "außen" in (entity_id or "").lower():
                self.state.outdoor_temp = level
            else:
                self.state.indoor_temp = level
        elif semantic == "humidity":
            self.state.humidity = level
        elif semantic == "illuminance":
            self.state.brightness = level
        elif semantic == "co2":
            pass  # Nur absorbieren
        
        # Heizung erkennen
        if semantic == "climate":
            self.state.heating_active = state in ("heating", "heat")
        
        # Signifikante Änderung prüfen
        if semantic in ENERGY_SEMANTICS:
            return self._check_energy_transition()
        elif semantic in CLIMATE_SEMANTICS:
            return self._check_climate_transition()
        
        return None
    
    def _check_energy_transition(self) -> dict:
        """Prüft ob sich der Energie-Zustand signifikant geändert hat."""
        battery = self.state.battery_state
        solar = self.state.solar_state
        current = (battery, solar)
        
        if current == self.last_energy_state:
            return None
        
        now = time.time()
        if (now - self._last_energy_event_time) < self.ENERGY_COOLDOWN:
            self.last_energy_state = current
            return None
        
        self.last_energy_state = current
        self._last_energy_event_time = now
        
        if battery <= 0:
            energy_state = "critical"
        elif battery <= 1 and solar <= 1:
            energy_state = "low"
        elif solar >= 2:
            energy_state = "charging"
        else:
            energy_state = "normal"
        
        _LOGGER.info("Hypothalamus: Energie-Transition → house.energy.%s", energy_state)
        return {
            "token": f"house.energy.{energy_state}",
            "room": "house",
            "semantic": "energy_state",
            "state": energy_state,
        }
    
    def _check_climate_transition(self) -> dict:
        """Prüft ob sich das Klima signifikant geändert hat."""
        current = self.state.indoor_temp
        
        if current == self.last_climate_state:
            return None
        
        now = time.time()
        if (now - self._last_climate_event_time) < self.CLIMATE_COOLDOWN:
            self.last_climate_state = current
            return None
        
        self.last_climate_state = current
        self._last_climate_event_time = now
        
        temp_names = {0: "cold", 1: "cool", 2: "comfort", 3: "warm", 4: "hot"}
        climate_state = temp_names.get(current, "comfort")
        
        return {
            "token": f"house.climate.{climate_state}",
            "room": "house",
            "semantic": "climate_state",
            "state": climate_state,
        }
    
    def get_context_vector(self) -> list:
        """Gibt den aktuellen Homöostase-Kontext als Vektor zurück."""
        return self.state.to_context_vector()
    
    def get_energy_summary(self) -> dict:
        """Menschenlesbare Zusammenfassung."""
        battery_names = {0: "kritisch", 1: "niedrig", 2: "normal", 3: "lädt"}
        solar_names = {0: "kein", 1: "wenig", 2: "mittel", 3: "viel"}
        power_names = {0: "kein", 1: "niedrig", 2: "mittel", 3: "hoch"}
        return {
            "battery": battery_names.get(self.state.battery_state, "?"),
            "solar": solar_names.get(self.state.solar_state, "?"),
            "consumption": power_names.get(self.state.power_consumption, "?"),
            "heating_active": self.state.heating_active,
            "indoor_temp": self.state.indoor_temp,
            "outdoor_temp": self.state.outdoor_temp,
        }
    
    def to_dict(self) -> dict:
        return {
            "battery_state": self.state.battery_state,
            "solar_state": self.state.solar_state,
            "power_consumption": self.state.power_consumption,
            "grid_state": self.state.grid_state,
            "indoor_temp": self.state.indoor_temp,
            "outdoor_temp": self.state.outdoor_temp,
            "humidity": self.state.humidity,
            "brightness": self.state.brightness,
            "heating_active": self.state.heating_active,
            "heating_demand": self.state.heating_demand,
            "events_absorbed": self.events_absorbed,
            "last_energy_state": self.last_energy_state,
            "last_climate_state": self.last_climate_state,
            "last_energy_event_time": self._last_energy_event_time,
            "last_climate_event_time": self._last_climate_event_time,
        }
    
    def from_dict(self, data: dict):
        self.state.battery_state = data.get("battery_state", 2)
        self.state.solar_state = data.get("solar_state", 0)
        self.state.power_consumption = data.get("power_consumption", 1)
        self.state.grid_state = data.get("grid_state", 1)
        self.state.indoor_temp = data.get("indoor_temp", 2)
        self.state.outdoor_temp = data.get("outdoor_temp", 1)
        self.state.humidity = data.get("humidity", 1)
        self.state.brightness = data.get("brightness", 1)
        self.state.heating_active = data.get("heating_active", False)
        self.state.heating_demand = data.get("heating_demand", 0)
        self.events_absorbed = data.get("events_absorbed", 0)
        self.last_energy_state = data.get("last_energy_state")
        self.last_climate_state = data.get("last_climate_state")
        self._last_energy_event_time = data.get("last_energy_event_time", 0)
        self._last_climate_event_time = data.get("last_climate_event_time", 0)
    
    @property
    def stats(self) -> dict:
        return {
            "events_absorbed": self.events_absorbed,
            "energy": self.get_energy_summary(),
            "context_vector": self.state.to_context_vector(),
        }
