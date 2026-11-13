from __future__ import annotations
import datetime
import numpy as np
from typing import Literal



class Punkt:
    """Ein Punkt stellt einen Messpunkt dar.
       Er hat eine Darstellungskoordinate (nur für die Anzeige in Übersichtskarten, ohne Aussage über die tatsächliche Lage)
       und eine Historie von Sollkoordinaten. Ist zu einem Zeitpunkt eine Sollkoordinate gültig, ist der Punkt zu diesem
       Zeitpunkt ein Anschlusspunkt."""

    def __init__(self, name: str, darstellung: Koordinate, soll_historie: list[SollKoordinate] | None = None):
        self.name = name
        if darstellung.system != "global":
            raise ValueError("Darstellungskoordinate muss im globalen System angegeben sein.")
        self.darstellung = darstellung

        self.soll_historie: list[SollKoordinate] = []
        for s in soll_historie or []:
            self.neue_sollkoordinate(s.koordinate, s.gueltig_ab, s.quelle)

    def __str__(self):
        return f"Punkt({self.name})"

    __repr__ = __str__

    def neue_sollkoordinate(self, koordinate: Koordinate | None, gueltig_ab: datetime.datetime, quelle: str = "") -> SollKoordinate:
        """Fügt eine neue Sollkoordinate zur Historie hinzu.
           koordinate=None bedeutet: ab diesem Zeitpunkt kein Anschlusspunkt mehr."""
        if koordinate is not None and koordinate.system != "global":
            raise ValueError("Sollkoordinate muss im globalen System angegeben sein.")
        if any(s.gueltig_ab == gueltig_ab for s in self.soll_historie):
            raise ValueError(f"Für {self.name} existiert bereits eine Sollkoordinate gültig ab {gueltig_ab}.")

        soll = SollKoordinate(koordinate, gueltig_ab, quelle)
        self.soll_historie.append(soll)
        self.soll_historie.sort(key=lambda s: s.gueltig_ab)
        return soll

    def sollkoordinate_zu(self, zeitpunkt: datetime.datetime) -> SollKoordinate | None:
        """Gibt den zum Zeitpunkt gültigen Eintrag der Historie zurück, oder None, falls noch keiner gültig ist."""
        gueltige = [s for s in self.soll_historie if s.gueltig_ab <= zeitpunkt]
        return gueltige[-1] if gueltige else None

    def ist_anschlusspunkt(self, zeitpunkt: datetime.datetime) -> bool:
        """True, wenn zum Zeitpunkt eine Sollkoordinate gültig ist (und der Punkt nicht deaktiviert wurde)."""
        s = self.sollkoordinate_zu(zeitpunkt)
        return s is not None and s.koordinate is not None


class Standort:
    """Ein Standort meint die Position des Messgerätes. Er hat einen Punktnamen, eine Koordinate und eine Standortbeschreibung"""

    def __init__(self, name: str, koordinate: Koordinate, beschreibung: str | None = None, ziele: list[Ziel] | None = None):
        self.name = name
        if not koordinate.system == "global":
            raise ValueError("Standortkoordinate muss im globalen System angegeben sein.")
        else:
            self.koordinate = koordinate
        self.beschreibung = beschreibung
        self.ziele = []
        for z in ziele or []:
            self.add_ziel(z)

    def __str__(self):
        return f"Standort({self.name})"


    def aktive_ziele(self):
        return [ziel for ziel in self.ziele if ziel.aktiv]

    def get_ziel(self, punkt: Punkt):
        """Gibt das Ziel für einen bestimmten Punkt zurück, falls vorhanden."""
        for ziel in self.ziele:
            if ziel.punkt == punkt:
                return ziel
        return None

    def add_ziel(self, ziel: Ziel):
        """Fügt ein neues Ziel zum Standort hinzu, falls es für diesen nicht bereits vorhanden ist."""
        if self.get_ziel(ziel.punkt) is None:
            self.ziele.append(ziel)
        else:
            raise ValueError(f"Ziel für Punkt {ziel.punkt.name} ist bereits vorhanden.")


class Ziel:
    """Ein Ziel stellt einen Messpunkt dar, der von einem Standort aus gemessen wird."""
    def __init__(self, punkt: Punkt, hz: float, vz: float, prismenkonstante: float = 0.0000, aktiv: bool = True):
        self.punkt = punkt
        self.hz = hz #rad
        self.vz = vz #rad
        self.prismenkonstante = prismenkonstante #[m] Leica-Konstante 0.0000, andere TS: -0.0344
        self.aktiv = aktiv #ob der Zielpunkt gemessen werden soll oder nicht
                     

class Koordinate:
    """Ein Koordinatenobjekt im Raum, mit X Y und Z Wert sowie deren Unsicherheiten.
       Die Koordinaten sind in einem lokalen oder globalen System angegeben."""
    def __init__(self, x: float, y: float, z: float, kovarianzmatrix: list[list[float]] | None = None,  system: Literal["lokal", "global"] = "lokal"):
        self.x = x
        self.y = y
        self.z = z
        self.kovarianzmatrix = kovarianzmatrix
        if system not in ("lokal", "global"):
            raise ValueError(f"Ungültiges System: {system!r} (erlaubt: 'lokal', 'global')")
        else:
            self.system = system  # "lokal" oder "global"
        

    def __str__(self):
        return f"Koordinate({self.x}, {self.y}, {self.z})"

    def getKoors(self):
        return self.x, self.y, self.z

    def getUnsicherheiten(self):
        if self.kovarianzmatrix is not None:
            return np.sqrt(np.diag(self.kovarianzmatrix))
        return None

class SollKoordinate:
    """Eine Sollkoordinate ist eine Koordinate, die als Referenz für einen Punkt dient. 
    Sie hat einen Zeitpunkt, ab dem sie verwendet wird, und eine Quelle, aus der sie stammt."""
    def __init__(self, koordinate: Koordinate | None, gueltig_ab: datetime, quelle: str = ""):
        self.koordinate = koordinate   # None = ab hier kein Anschlusspunkt mehr
        self.gueltig_ab = gueltig_ab
        self.quelle = quelle           # z. B. "Netzmessung 2026-03"
    

class Position:
    """Eine Position stellt eine Messung eines Messpunktes dar. Sie hat eine lokaleKoordinate. Zu dieser Koordinate wird nach Transformation eine globale Koordinate hinzugefügt.
        Sie ist mit einem Punkt und einer Messung verknüpft, um die Position zuordnen zu können."""

    def __init__(self, koordinate: Koordinate, punkt: Punkt, messung: Messung | None=None, ):
        self.koordinaten: dict[str, Koordinate] = {} #"lokal" oder "global"
        self.set_koordinate(koordinate)

        self.punkt = punkt
        self.messung = messung

    def set_koordinate(self, k: Koordinate):
        self.koordinaten[k.system] = k

    
    


class Messung:
    """Eine Messung stellt eine Sammlung von Positionen dar, die von einem Standpunkt zu einem bestimmten Zeitpunkt gemessen wurden.
       Der Zeitstempel ist ein Orientierungswert, alle Positionen erben diesen Zeitstempel
       Eine Messung kann mehrere Sätze enthalten."""

    def __init__(self, standort: Standort, zeitstempel: datetime.datetime, positionen: list[Position] | None = None):
        self.standort = standort
        self.zeitstempel = zeitstempel
        self.saetze = []  # Sätze in dieser Messung werden erst durch neuer_satz hinzugefügt

        self.positionen = []  # Positionen in dieser Messung werden erst durch add_position hinzugefügt
        for p in positionen or []:
            self.add_position(p)

    def __str__(self):
        return f"Messung({self.standort.name}, {self.zeitstempel})"

    def neuer_satz(self):
        satz = Satz(self)
        self.saetze.append(satz)
        return satz

    def add_position(self, position: Position):
        """Fügt eine neue Position zur Messung hinzu."""
        if self.position_von(position.punkt) is not None:
            raise ValueError(f"Position für Punkt {position.punkt.name} ist bereits vorhanden.")
        else:
            position.messung = self
            self.positionen.append(position)

    def position_von(self, punkt: Punkt):
        """Gibt die Position eines bestimmten Punktes zurück, falls vorhanden."""
        for pos in self.positionen:
            if pos.punkt == punkt:
                return pos
        return None

    def koordinaten(self, system): 
        return {p.punkt: p.koordinaten[system] for p in self.positionen if system in p.koordinaten}


class Satz:
    """Ein Satz stellt eine Sammlung von Messwerten dar. Er gehört fest zu einer Messung.
       Ein Satz kann mehrere Messwerte enthalten."""

    def __init__(self, messung: Messung):
        self.messung = messung
        self.messwerte = []  # Messwerte in diesem Satz werden erst durch neuer_messwert hinzugefügt
        

    def __str__(self):
        return f"Satz({self.messung.standort.name}, {self.messung.zeitstempel})"

    def neuer_messwert(self, ziel: Ziel, hz: float, vz: float, strecke: float, lage: Literal["I", "II"]):
        if self.messwert_von(ziel, lage) is not None:
            raise ValueError(f"Messwert für Ziel {ziel.punkt.name} und Lage {lage} ist bereits vorhanden.")
        else:
            messwert = Messwert(self, ziel, hz, vz, strecke, lage)
            self.messwerte.append(messwert)
            return messwert

    def messwert_von(self, ziel: Ziel, lage: Literal["I", "II"]):
        """Gibt den Messwert eines bestimmten Ziels zurück, falls vorhanden."""
        for mw in self.messwerte:
            if mw.ziel == ziel and mw.lage == lage:
                return mw
        return None
        
    def status(self, ziel: Ziel) -> Literal["komplett", "nur_I", "nur_II", "fehlt"]:
        l1 = self.messwert_von(ziel, "I") is not None
        l2 = self.messwert_von(ziel, "II") is not None
        if l1 and l2: return "komplett"
        if l1:        return "nur_I"
        if l2:        return "nur_II"
        return "fehlt"

    def unvollstaendige_ziele(self) -> list[Ziel]:
        return [z for z in self.messung.standort.aktive_ziele() if self.status(z) != "komplett"]


class Messwert():
    """Ein Messwert stellt eine Messung eines Ziels dar, die zu einem bestimmten Zeitpunkt von einem Standort aus gemessen wurde.
       Ein Messwert hat einen Satz, ein Ziel, einen horizontalen Winkel, einen vertikalen Winkel, eine Strecke und eine Lage (I oder II)."""
    def __init__(self, satz: Satz,  ziel: Ziel, hz: float, vz: float, strecke: float, lage: Literal["I", "II"]):
        self.satz = satz
        self.ziel = ziel
        self.hz = hz #rad
        self.vz = vz #rad
        self.strecke = strecke #Strecke, gemessen, in 3D [m]
        if lage not in ("I", "II"):
            raise ValueError(f"Ungültige Lage: {lage!r} (erlaubt: 'I', 'II')")
        else:
            self.lage = lage

    
    
