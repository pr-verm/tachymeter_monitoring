from __future__ import annotations
import datetime
import numpy as np
from typing import Literal



class Punkt:
    """Ein Punkt stellt einen Messpunkt dar. Er hat eine Referenzposition, auf welcher der Punkt dargestellt wird."""

    def __init__(self, name, referenz: Koordinate):
        self.name = name
        if not referenz.system == "global":
            raise ValueError("Referenzkoordinate muss im globalen System angegeben sein.")
        else: 
            self.referenz = referenz  
        
    def __str__(self):
        return f"Punkt({self.name})"


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
    

class Position:
    """Eine Position stellt eine Messung eines Messpunktes dar. Sie hat eine lokaleKoordinate. Zu dieser Koordinate wird nach Transformation eine globale Koordinate hinzugefügt.
        Sie ist mit einem Punkt und einer Messung verknüpft, um die Position zuordnen zu können."""

    def __init__(self, koordinate: Koordinate, punkt: Punkt, messung: Messung | None=None):
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

    
    
