"""Decoders for the Pre-AP MCU GPS and map speed limit frames (tesla_preap.dbc).

Kept free of CANParser/capnp so the GPS daemon can decode raw `can` frames cheaply.
All three frames are sent by the MCU on the party bus at ~1 Hz.
"""
from dataclasses import dataclass

MCU_LOCATION_STATUS = 0x3D8   # 984: MCU_latitude, MCU_longitude, MCU_gpsAccuracy
MCU_LOCATION_STATUS2 = 0x068  # 104: MCU_elevation
UI_GPS_VEHICLE_SPEED = 0x2F8  # 760: UI_gpsHDOP, UI_gpsVehicleHeading, UI_gpsVehicleSpeed, UI_mppSpeedLimit

KPH_TO_MS = 1. / 3.6
MPH_TO_MS = 1.609344 / 3.6

# UI_mppSpeedLimit is 5 bits * 5: 0 = no limit known, 31 (155) = SNA
MPP_SPEED_LIMIT_NONE = 0
MPP_SPEED_LIMIT_SNA = 31


def _bits(dat: bytes, start: int, size: int, signed: bool = False) -> int:
  x = (int.from_bytes(dat[:8].ljust(8, b'\0'), 'little') >> start) & ((1 << size) - 1)
  if signed and x & (1 << (size - 1)):
    x -= 1 << size
  return x


@dataclass
class TeslaLocation:
  latitude: float
  longitude: float
  accuracy: float  # m


@dataclass
class TeslaGpsSpeed:
  hdop: float
  heading_deg: float
  speed: float  # m/s
  speed_limit: float  # m/s, 0 when unknown
  nmea_mia: bool


def decode_location(dat: bytes) -> TeslaLocation:
  return TeslaLocation(
    latitude=_bits(dat, 0, 28, True) * 1e-6,
    longitude=_bits(dat, 28, 29, True) * 1e-6,
    accuracy=_bits(dat, 57, 7) * 0.2,
  )


def decode_elevation(dat: bytes) -> float:
  return _bits(dat, 0, 32, True) * 0.1


def mpp_speed_limit_ms(raw: int, units_kph: bool) -> float:
  if raw in (MPP_SPEED_LIMIT_NONE, MPP_SPEED_LIMIT_SNA):
    return 0.
  return raw * 5 * (KPH_TO_MS if units_kph else MPH_TO_MS)


def decode_gps_speed(dat: bytes) -> TeslaGpsSpeed:
  return TeslaGpsSpeed(
    hdop=_bits(dat, 0, 8) * 0.1,
    heading_deg=_bits(dat, 8, 16) * 0.0078125,
    speed=_bits(dat, 24, 16) * 0.00390625 * KPH_TO_MS,
    speed_limit=mpp_speed_limit_ms(_bits(dat, 48, 5), bool(_bits(dat, 46, 1))),
    nmea_mia=bool(_bits(dat, 53, 1)),
  )


def location_has_fix(loc: TeslaLocation, gps_speed: TeslaGpsSpeed | None) -> bool:
  if gps_speed is None or gps_speed.nmea_mia:
    return False
  if loc.accuracy <= 0. or (loc.latitude == 0. and loc.longitude == 0.):
    return False
  return abs(loc.latitude) <= 90. and abs(loc.longitude) <= 180.
