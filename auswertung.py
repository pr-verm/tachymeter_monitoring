import messung
import math
import numpy as np
from messung import Messung, Satz, Position, Punkt, Ziel


""" Auswertung von Messdaten 
    hier werden die Lagen gemittelt, die Sätze gemittelt und lokale Koordinaten berechnet
    Ausgangspunkt sind Messungen der Polaraufnahme und die a-priori Unsicherheit der Messgrößen
    x = Rechtswert, y = Hochwert, z = Höhe, HZ-Winkel von y auf x im Uhrzeigersinn, VZ-Winkel vom Zenit auf die XY-Ebene, Strecke = 3D-Strecke"""
    
    
def satzmittel(messung: Messung) -> Satz:
    saetze = messung.saetze
    if not saetze:
        raise ValueError("Die Satzliste ist leer.")

    ziele_pro_satz = [{mw.ziel for mw in s.messwerte if mw.lage == "Mittel"} for s in saetze]
    gemeinsame = set.intersection(*ziele_pro_satz)
    ausgeschlossen = set.union(*ziele_pro_satz) - gemeinsame
    if ausgeschlossen:
        namen = ", ".join(sorted(z.punkt.name for z in ausgeschlossen))
        print(f"Nicht in allen Sätzen vorhanden, wird nicht gemittelt: {namen}")

    mittelsatz = messung.neuer_mittelsatz()
    
    for ziel in gemeinsame:
        mws = [s.messwert_von(ziel, "Mittel") for s in saetze]

        # Hz um den ersten Wert reduzieren, damit der Sprung 0/2π das Mittel nicht verfälscht
        hz0 = mws[0].hz
        d_hz = [((mw.hz - hz0 + np.pi) % (2 * np.pi)) - np.pi for mw in mws]
        hz = (hz0 + np.mean(d_hz)) % (2 * np.pi)
        vz = np.mean([mw.vz for mw in mws])
        s  = np.mean([mw.strecke for mw in mws])
        
        mittelsatz.neuer_messwert(ziel, float(hz), float(vz), float(s), "Mittel")
        
    return mittelsatz