"""Tests für die Kern-Regel aus dem Manifest (Durchsicht 04.10., Punkt 0a).

Der Fund: 0.29.0 nahm jede neue Kern-Version. Als der Kern 0.6.3 die
Signatur von ``should_consolidate`` auf zwei Argumente stellte, brach
jeder Konsolidierungs-Aufruf mit ``TypeError`` — still, hinter einem
breiten ``except``. Die Obergrenze ``<0.7`` macht Kern-Wechsel wieder
zu einer bewussten Handlung (MR + Changelog + CI-Beweis), statt zum
Nebenprodukt eines ``pip install``.

Der CI-Job ``kern-pypi`` liest dieselbe Regel aus dem Manifest und
fährt die Suite gegen die PyPI-Fassung, die sie erlaubt — der Streit
zwischen lokal installiertem Kern und Kern der Installationen ist damit
geschlichtet, bevor er wieder Geld kostet.
"""

import json
from pathlib import Path

MANIFEST = Path("custom_components/kontinuum/manifest.json")


def _kern_regel() -> tuple:
    """Zerlegt die Kern-Anforderung in (Fussboden, Obergrenze) als Texte.

    Aus ``kontinuum-core>=0.6.3,<0.7`` wird ``(">=0.6.3", "<0.7")``.
    Fehlt ein Teil, kommt er als None zurück — die Tests melden das dann.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    req = next(r for r in manifest["requirements"] if r.startswith("kontinuum-core"))
    regel = req[len("kontinuum-core"):].strip()
    teile = [t.strip() for t in regel.split(",")]
    fussboden = next((t for t in teile if t.startswith(">=")), None)
    obergrenze = next((t for t in teile if t.startswith("<")), None)
    return fussboden, obergrenze


def test_kern_regel_hat_fussboden_und_obergrenze():
    """>=0.6.3 UND <0.7 — beides, sonst ist die Regel keine Regel.

    Eine offene Spitze (nur Fussboden) nimmt jede neue Kern-Version
    wieder ungeprüft mit — der Juli-Befund in Reinform.
    """
    fussboden, obergrenze = _kern_regel()
    assert fussboden is not None, "die Kern-Regel braucht einen Fussboden (>=X.Y.Z)"
    assert obergrenze is not None, "die Kern-Regel braucht eine Obergrenze (<N)"
    # Der Fussboden ist eine vollständige Version (X.Y.Z), damit die
    # Regel sagt, WAS mindestens gefordert ist, nicht nur irgendwas.
    assert len(fussboden[2:].split(".")) == 3, (
        f"der Fussboden '{fussboden}' sollte eine vollständige Version X.Y.Z sein"
    )


def test_obergrenze_liegt_genau_eine_nebenlinie_ueber_dem_fussboden():
    """Die Regel erlaubt genau die Nebenlinie des Fussbodens — 0.6.x, nicht mehr.

    Ein größerer Sprung (Fussboden 0.6, Obergrenze 0.9) wäre eine
    Blaupause für den nächsten stillen TypeError: zu viel Kern, zu
    wenig Beweis. Beispiel der Vereinbarung: >=0.6.3,<0.7.
    """
    fussboden, obergrenze = _kern_regel()
    assert fussboden and obergrenze, "siehe test_kern_regel_hat_fussboden_und_obergrenze"
    fuss_teile = fussboden[2:].split(".")
    oberg_teile = obergrenze[1:].split(".")
    assert oberg_teile[0] == fuss_teile[0], (
        f"Hauptversion weicht ab: Fussboden {fuss_teile[0]}, Obergrenze {oberg_teile[0]}"
    )
    assert int(oberg_teile[1]) == int(fuss_teile[1]) + 1, (
        f"Obergrenze <{'.'.join(oberg_teile)} bei Fussboden {'.'.join(fuss_teile)} — "
        "genau eine Nebenlinie Abstand ist die Vereinbarung"
    )
