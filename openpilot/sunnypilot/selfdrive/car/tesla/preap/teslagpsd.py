#!/usr/bin/env python3
"""Publish gpsLocation from the Pre-AP Tesla MCU GPS on CAN, replacing qcomgpsd.

Runs only when NAP GPS Source is set to Tesla (see process_config.teslagps).
The MCU sends MCU_locationStatus (lat/lon/accuracy), MCU_locationStatus2 (elevation)
and UI_gpsVehicleSpeed (heading/speed) at ~1 Hz on the party bus.
"""
import json
import math
import time

from opendbc.car.tesla.preap.tesla_gps import (
  MCU_LOCATION_STATUS, MCU_LOCATION_STATUS2, UI_GPS_VEHICLE_SPEED,
  TeslaGpsSpeed, TeslaLocation, decode_elevation, decode_gps_speed, decode_location, location_has_fix,
)
from opendbc.car.tesla.values import CANBUS
from openpilot.cereal import log
import openpilot.cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

GPS_ADDRS = (MCU_LOCATION_STATUS, MCU_LOCATION_STATUS2, UI_GPS_VEHICLE_SPEED)
STALE_NS = 3_000_000_000
# MCU does not report these; chosen to pass locationd sanity checks with sensible weight
SPEED_ACCURACY = 0.5  # m/s
BEARING_ACCURACY = 3.0  # deg, when moving
MIN_BEARING_SPEED = 2.0  # m/s, heading is unknown below this
# MCU position arrives ~0.7 s later than the Quectel fix whose latency locationd already
# compensates (measured on a 2014 Model S); project forward so both sources line up
EXTRA_LATENCY = 0.7  # s
EARTH_RADIUS = 6371000.  # m


def last_known_altitude(params: Params) -> float:
  # MCU_locationStatus2 (elevation) is not on the party bus of Pre-AP cars
  try:
    raw = params.get("LastGPSPositionLLK") or {}
    pos = raw if isinstance(raw, dict) else json.loads(raw)
    return float(pos.get("altitude", 0.))
  except (TypeError, ValueError, AttributeError):
    return 0.


class TeslaGpsState:
  def __init__(self, default_altitude: float = 0.):
    self.gps_speed: TeslaGpsSpeed | None = None
    self.gps_speed_ns = 0
    self.default_altitude = default_altitude
    self.elevation = 0.
    self.elevation_ns = 0

  def update(self, address: int, dat: bytes, t_ns: int) -> TeslaLocation | None:
    """Feed one frame; returns a location when a new MCU_locationStatus arrives."""
    if address == UI_GPS_VEHICLE_SPEED:
      self.gps_speed, self.gps_speed_ns = decode_gps_speed(dat), t_ns
    elif address == MCU_LOCATION_STATUS2:
      self.elevation, self.elevation_ns = decode_elevation(dat), t_ns
    elif address == MCU_LOCATION_STATUS:
      return decode_location(dat)
    return None

  def fill(self, gps, loc: TeslaLocation, t_ns: int, unix_time_ms: float) -> None:
    gps_speed = self.gps_speed if (t_ns - self.gps_speed_ns) < STALE_NS else None
    speed = gps_speed.speed if gps_speed is not None else 0.
    heading = gps_speed.heading_deg if gps_speed is not None else 0.
    moving = speed >= MIN_BEARING_SPEED

    lat, lon = loc.latitude, loc.longitude
    if moving:
      d = speed * EXTRA_LATENCY
      lat += math.degrees(d * math.cos(math.radians(heading)) / EARTH_RADIUS)
      lon += math.degrees(d * math.sin(math.radians(heading)) / (EARTH_RADIUS * math.cos(math.radians(loc.latitude))))

    gps.latitude = lat
    gps.longitude = lon
    has_elevation = self.elevation_ns > 0 and (t_ns - self.elevation_ns) < STALE_NS
    gps.altitude = self.elevation if has_elevation else self.default_altitude
    gps.speed = speed
    gps.bearingDeg = heading
    gps.vNED = [speed * math.cos(math.radians(heading)), speed * math.sin(math.radians(heading)), 0.]
    gps.horizontalAccuracy = loc.accuracy
    gps.verticalAccuracy = max(2. * loc.accuracy, 1.)
    gps.speedAccuracy = SPEED_ACCURACY
    gps.bearingAccuracyDeg = BEARING_ACCURACY if moving else 180.
    gps.unixTimestampMillis = unix_time_ms
    gps.source = log.GpsLocationData.SensorSource.car
    gps.hasFix = location_has_fix(loc, gps_speed)


def _pub_master() -> messaging.PubMaster:
  # qcomgpsd can still own gpsLocation for a moment while manager switches sources
  while True:
    try:
      return messaging.PubMaster(['gpsLocation'])
    except messaging.MultiplePublishersError:
      cloudlog.warning("teslagpsd: gpsLocation still published, waiting for qcomgpsd to exit")
      time.sleep(0.5)


def main() -> None:
  can_sock = messaging.sub_sock('can', timeout=100)
  pm = _pub_master()
  state = TeslaGpsState(last_known_altitude(Params()))

  while True:
    for msg in messaging.drain_sock(can_sock, wait_for_one=True):
      for c in msg.can:
        if c.src != CANBUS.party or c.address not in GPS_ADDRS:
          continue
        loc = state.update(c.address, bytes(c.dat), msg.logMonoTime)
        if loc is None:
          continue
        gps_msg = messaging.new_message('gpsLocation', valid=True)
        state.fill(gps_msg.gpsLocation, loc, msg.logMonoTime, time.time() * 1e3)
        pm.send('gpsLocation', gps_msg)


if __name__ == "__main__":
  main()
