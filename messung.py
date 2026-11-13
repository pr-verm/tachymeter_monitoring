from __future__ import annotations
import datetime
from typing import Literal



class Punkt:
    """Ein Punkt stellt einen Messpunkt dar. Er hat eine Referenzposition, auf welcher der Punkt dargestellt wird."""

    def __init__(self, name, referenz: Koordinate):
        self.name = name
        self.referenz = referenz  
        
    def __str__(self):
        return f"Punkt({self.name})"


class Standort:
    """Ein Standort meint die Position des Messgerätes. Er hat einen Punktnamen, eine Koordinate und eine Standortbeschreibung"""

    def __init__(self, name: str, koordinate: Koordinate, beschreibung: str | None = None, ziele: list[Ziel] | None = None):
        self.name = name
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
    def __init__(self, punkt: Punkt, hz: float, vz: float, prismenkonstante: float = 0.0, aktiv: bool = True):
        self.punkt = punkt
        self.hz = hz #rad
        self.vz = vz #rad
        self.prismenkonstante = prismenkonstante #[mm] Leica-Konstante 0.0, andere TS: -34.4
        self.aktiv = aktiv #ob der Zielpunkt gemessen werden soll oder nicht
                     

class Koordinate:
    """Ein Koordinatenobjekt im Raum, mit X Y und Z Wert sowie deren Unsicherheiten."""
    def __init__(self, x: float, y: float, z: float, sx: float, sy: float, sz: float,):
        self.x = x
        self.y = y
        self.z = z
        self.sx = sx
        self.sy = sy
        self.sz = sz

    def __str__(self):
        return f"Koordinate({self.x}, {self.y}, {self.z})"

    def getKoors(self):
        return self.x, self.y, self.z

    def getUnsicherheiten(self):
        return self.sx, self.sy, self.sz
    

class Position:
    """Eine Position stellt eine Messung eines Messpunktes dar. Sie hat eine Koordinate.
        Sie ist mit einem Punkt und einer Messung verknüpft, um die Position zuordnen zu können."""

    def __init__(self, koordinate: Koordinate, punkt: Punkt, messung: Messung | None=None):
        self.koordinate = koordinate
        self.punkt = punkt
        self.messung = messung

    def __str__(self):
        return f"Position({self.koordinate.x}, {self.koordinate.y}, {self.koordinate.z})"

    
    


class Messung:
    """Eine Messung stellt eine Sammlung von Positionen dar, die von einem Standpunkt zu einem bestimmten Zeitpunkt gemessen wurden.
       Der Zeitstempel ist ein Orientierungswert, alle Positionen erben diesen Zeitstempel"""

    def __init__(self, standort: Standort, zeitstempel: datetime.datetime, positionen: list[Position] | None = None):
        self.standort = standort
        self.zeitstempel = zeitstempel
        self.positionen = []  # Positionen in dieser Messung werden erst durch add_position hinzugefügt
        for p in positionen or []:
            self.add_position(p)

    def __str__(self):
        return f"Messung({self.standort.name}, {self.zeitstempel})"

    def add_position(self, position: Position):
        """Fügt eine neue Position zur Messung hinzu."""
        position.messung = self
        self.positionen.append(position)

    def position_von(self, punkt: Punkt):
        """Gibt die Position eines bestimmten Punktes zurück, falls vorhanden."""
        for pos in self.positionen:
            if pos.punkt == punkt:
                return pos
        return None


class Messwert():
    def __init__(self, messung: Messung, ziel: Ziel, hz: float, vz: float, strecke: float, lage: Literal["I", "II"]):
            self.messung = messung
            self.ziel = ziel
            self.hz = hz
            self.vz = vz
            self.strecke = strecke #Strecke, gemessen, in 3D
            if lage not in ("I", "II"):
                raise ValueError(f"Ungültige Lage: {lage!r} (erlaubt: 'I', 'II')")
            else:
                self.lage = lage

    
    