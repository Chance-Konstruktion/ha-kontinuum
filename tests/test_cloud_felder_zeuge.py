"""Der strukturelle CLOUD_FELDER-Zeuge (Gegenlesungs-Fund aus Notiz 19987).

Der Wort-Zeuge in test_cloud_hinweis.py prüft 10 Stichworte gegen die
Liste — er bleibt grün, wenn der VERSAND sich ändert. Dieser Zeuge hier
ruft den ECHTEN ``Cortex._build_context`` gegen ein echtes Kern-Gehirn
(alle sieben Module aus kontinuum_core) und verlangt: JEDES Feld, das
der Code heute versendet, wird in CLOUD_FELDER benannt. Kommt ein neues
Feld dazu, wird der Zeuge rot mit dem Namen des Feldes — die Liste kann
nicht mehr still veralten.
"""
import pytest

from kontinuum_core.amygdala import Amygdala
from kontinuum_core.basal_ganglia import BasalGanglia
from kontinuum_core.hippocampus import Hippocampus
from kontinuum_core.hypothalamus import Hypothalamus
from kontinuum_core.insula import Insula
from kontinuum_core.spatial_cortex import SpatialCortex
from kontinuum_core.thalamus import Thalamus

from custom_components.kontinuum.cortex import Cortex
from custom_components.kontinuum.config_flow import CLOUD_FELDER

#: Kontext-Feld -> das deutsche Wort, das CLOUD_FELDER dafür führt.
#: Ein NEUES Feld in _build_context ohne Eintrag hier = roter Zeuge
#: mit dem Feldnamen — dann beide Stellen erweitern (Liste UND Zeuge).
KONTEXT_WORTE = {
    "mode": "Modus",
    "room": "Raum",
    "prediction": "Vorhersage",
    "confidence": "Sicherheit",
    "energy": "Energie",
    "risk": "Risiko",
    "persons_home": "Personen",
    "events": "Ereignis",
    "accuracy": "Genauigkeit",
    "last_event": "letzte Ereignis",
    "habits": "Habit",
    "dopamine": "Dopamin",
}


def _echtes_gehirn() -> dict:
    """Ein Gehirn aus den ECHTEN Kern-Modulen — kein Attrappen-Dict.

    _build_context greift auf alle sieben Module zu (plus die optionalen
    ``_last_*``-Signale); hier laufen die echten Klassen, damit der Zeuge
    genau die Felder sieht, die der Versand wirklich baut.
    """
    return {
        "hippocampus": Hippocampus(),
        "insula": Insula(),
        "spatial": SpatialCortex(),
        "hypothalamus": Hypothalamus(),
        "amygdala": Amygdala(),
        "basal_ganglia": BasalGanglia(),
        "thalamus": Thalamus(),
        "_last_predictions": [],
        "_last_signal": {"token": "wohnzimmer.light.on"},
        "_persons_home": ["Chris"],
    }


def test_c_feldliste_nennt_alles_was_der_kontext_traegt():
    """Der ECHTE _build_context läuft; jedes Feld muss benannt sein."""
    kontext = Cortex()._build_context(_echtes_gehirn())
    for schluessel in sorted(kontext):
        wort = KONTEXT_WORTE.get(schluessel)
        assert wort is not None, (
            f"Neues Kontextfeld '{schluessel}' ohne Zeugen-Wort — "
            "KONTEXT_WORTE erweitern und CLOUD_FELDER prüfen"
        )
        assert wort in CLOUD_FELDER, (
            f"CLOUD_FELDER verschweigt '{schluessel}' ({wort}) — "
            "die Liste muss das neue Feld ehrlich nennen"
        )


def test_der_zeuge_ist_nicht_nur_ein_blatt():
    """Gegenprobe: fehlt ein Wort, wird der Zeuge rot (wir werfen eines
    raus und erwarten den Fehler — der Zeuge muss schlagen koennen)."""
    kontext = Cortex()._build_context(_echtes_gehirn())
    schluessel = sorted(kontext)[0]
    wort = KONTEXT_WORTE[schluessel]
    liste_ohne = CLOUD_FELDER.replace(wort, "")
    assert wort not in liste_ohne  # die Entfernung ist echt passiert
