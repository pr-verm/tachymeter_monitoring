import math
from pyGeoCOM.surveytools import Angle
from pyGeoCOM.GeoComLite import TotalStation, AtmosphericCorrectionData 
from pyGeoCOM.GeoComEnumeration import PositionMode, ATRMode, EDMMeasurementMode, BAPPrismenType 
import time
from messung import Messung, Satz, Position, Punkt, Ziel

""" Dieses Modul steuert das Messgerät, eine Leica-Totalstation über die GeoCOM-Schnittstelle.
    Die Aufnahme wird über die Klasse Standort definiert, in welcher eine Liste von Zielen enthalten ist."""


rho = 200/math.pi

class sortierer():
    """
    Sortiert die Ziele eines Standorts nach HZ 
    auf = True  aufsteigend
    auf = False absteigend
    """

    def output(messung: Messung, auf: bool):
        return sorted(messung.standort.aktive_ziele(), key=lambda z: z.hz, reverse=not auf)
        
        

class execute():
    def __init__(self, messung: Messung, anz_saetze: int, temp: float = 20.0, druck: float = 1000, ts_port: str = '/dev/ttyUSB1', ts_baudrate = 115200, versuche = 1, nachholen: bool = True):
        self.anz_saetze = anz_saetze
        self.messung = messung
        self.ziele = sortierer.output(self.messung, True)
        self.temp = temp
        self.druck = druck
        self.ts_port = ts_port
        self.ts_baudrate = ts_baudrate
        self.versuche = versuche #wie oft versucht wird, ein Ziel zu messen
        self.nachholen = nachholen #ob am Satzende unvollständige Messungen nochmal probiert werden sollen
        
        try:

            """Initialisierung der Totalstation und Verbindung über GeoCOM"""
            self._connect_with_retries()
            
           
            self.set_prism_type(BAPPrismenType.BAP_PRISM_ROUND) #Rundprisma, Leica: 0.0000, wird eingestellt. Die Prismenkonstante wird als Differenz zur Leica-Konstante an den Strecken berücksichtigt
            self.atmo_data = AtmosphericCorrectionData(0.2818, self.druck, self.temp, self.temp)
            print(f"Sende Atmo-Daten: {self.temp}°C bei {self.druck}hPa")
            self.totalstation.set_atm_correction(self.atmo_data)
            
            print("Setze Streckenmessmodus...")
            self.changeEDMmode(0) #0 = Standard mit Reflektor

            for i in range(self.anz_saetze):
                print(f"Starte Satz {i+1} von {self.anz_saetze}...")
                self.messe_satz(i+1)
                print(f"Satz {i+1} abgeschlossen.")
            
            print("Satzmessung beendet, Warteposition...")
            self.moveit(0,200) 
            print("Gute Nacht, Tachymeter!")
            
        finally:
            print("Schließen der Verbindungen...")
            if hasattr(self, 'totalstation'):
                try:
                    self.totalstation.turn_off() 
                except Exception as e:
                    print(f"Warnung beim Abschalten: {e}")
                
                try:
                    self.totalstation.serialPort.close() 
                    print("Serieller Port erfolgreich freigegeben.")
                except Exception as e:
                    print(f"Warnung beim Port-Schließen: {e}")
                    

    def _connect_with_retries(self):
        """Versucht mehrmals, eine stabile Verbindung aufzubauen."""
        max_retries = 3
        
        for versuch in range(max_retries):
            try:
                print(f"Verbindungsversuch {versuch + 1}/{max_retries} auf {self.ts_port}...")
                self.connect()
                
                print("Sende wake_up() Signal...")
                self.totalstation.wake_up()
                
                print("Warte 5 Sekunden auf Instrument...")
                time.sleep(5)
                
               
                print("Prüfe Kommunikationsebene...")
                instr_name = self.totalstation.get_instrument_name()
                print(f"Erfolgreich verbunden mit: {instr_name}")
                
                
                return
                
            except Exception as e:
                print(f"Verbindungsfehler bei Versuch {versuch + 1}: {e}")
                
               
                if hasattr(self, 'totalstation'):
                    try:
                        self.totalstation.serialPort.close()
                    except:
                        pass
                
                if versuch < max_retries - 1:
                    print("Warte 10 Sekunden vor dem nächsten Versuch...")
                    time.sleep(10)
                    
        
        raise ConnectionError(f"Abbruch: Tachymeter reagiert auch nach {max_retries} Versuchen nicht auf Befehle.")
        

    def connect(self):
        self.totalstation = TotalStation(self.ts_port, self.ts_baudrate) 
        

    def moveit(self, ph, pv):
        self.totalstation.set_telescope_position(Angle.from_gon(ph%400), Angle.from_gon(pv%400), 
                                                 PositionMode.AUT_NORMAL, ATRMode.AUT_TARGET)
                                                 

    def changeEDMmode(self, index):
        mode = EDMMeasurementMode.EDM_SINGLE_STANDARD if index == 0 else EDMMeasurementMode.EDM_SINGLE_SRANGE
        self.totalstation.set_edm_mode(mode)
        

    def set_prism_type(self, prism_type: BAPPrismenType):
        command = f"%R1Q,17008:{prism_type.value}"
        response = self.totalstation.request(command)
        return response[0]
        

    def _messe_ziel(self, satz, ziel, lage) -> bool:
        """Misst ein Ziel in einer Lage. Gibt True zurück, wenn ein gültiger Messwert gespeichert wurde."""
        hz = ziel.hz * rho
        vz = ziel.vz * rho
        if lage == "II":
            hz, vz = hz + 200, 400 - vz

        for versuch in range(1, self.versuche + 1):
            try:
                print(f"Lage {lage}: Punkt {ziel.punkt.name} (Versuch {versuch})")
                self.moveit(hz, vz)
                m_obj = self.totalstation.measure(ziel.punkt.name, self.atmo_data, time.time())
                if m_obj is None or not m_obj.slope_distances or m_obj.slope_distances <= 0:
                    print(f"  keine gültige Strecke")
                    continue
                satz.neuer_messwert(
                    ziel=ziel,
                    hz=float(m_obj.direction.value_rad),
                    vz=float(m_obj.zenith.value_rad),
                    strecke=float(m_obj.slope_distances) + ziel.prismenkonstante,
                    lage=lage)
                return True
            except Exception as e:
                print(f"  Fehler: {e}")
        return False

    def messe_satz(self, satz_nr: int):
        """Misst einen Satz"""    
        print(f"Satz {satz_nr} startet...")
        satz = self.messung.neuer_satz()

        for ziel in sortierer.output(self.messung, True):
            self._messe_ziel(satz, ziel, "I")
        for ziel in sortierer.output(self.messung, False):
            self._messe_ziel(satz, ziel, "II")

        if self.nachholen:
            for ziel in satz.unvollstaendige_ziele():
                for lage in ("I", "II"):
                    if satz.messwert_von(ziel, lage) is None:
                        self._messe_ziel(satz, ziel, lage)

        for ziel in satz.unvollstaendige_ziele():
            print(f"WARNUNG Satz {satz_nr}: {ziel.punkt.name} -> {satz.status(ziel)}") 
                        