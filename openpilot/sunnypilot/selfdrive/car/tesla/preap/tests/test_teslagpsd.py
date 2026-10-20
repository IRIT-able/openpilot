import math

import openpilot.cereal.messaging as messaging
from opendbc.car.tesla.preap.tesla_gps import MCU_LOCATION_STATUS, UI_GPS_VEHICLE_SPEED
from openpilot.sunnypilot.selfdrive.car.tesla.preap.teslagpsd import EXTRA_LATENCY, TeslaGpsState

# Frames captured on a 2014 Model S (route 0000003f, segment 22)
LOCATION = bytes.fromhex("e05f0842aaa8af0d")  # 34.103264, -84.243804, 1.2 m


def _speed_frame(heading_deg: float, speed_kph: float, mia: int = 0) -> bytes:
  v = (round(heading_deg / 0.0078125) << 8) | (round(speed_kph / 0.00390625) << 24) | (13 << 48) | (mia << 53)
  return v.to_bytes(8, 'little')


def _fill(state: TeslaGpsState, t_ns: int):
  loc = state.update(MCU_LOCATION_STATUS, LOCATION, t_ns)
  assert loc is not None
  msg = messaging.new_message('gpsLocation', valid=True)
  state.fill(msg.gpsLocation, loc, t_ns, 1.7e12)
  return msg.gpsLocation


def test_no_fix_without_speed_frame():
  gps = _fill(TeslaGpsState(), 1_000_000_000)
  assert not gps.hasFix


def test_fix_and_latency_projection():
  state = TeslaGpsState(default_altitude=290.)
  assert state.update(UI_GPS_VEHICLE_SPEED, _speed_frame(0., 72.), 1_000_000_000) is None
  gps = _fill(state, 1_500_000_000)
  assert gps.hasFix
  assert math.isclose(gps.speed, 20., abs_tol=1e-3)
  # heading north at 20 m/s: projected EXTRA_LATENCY seconds ahead in latitude only
  moved = (gps.latitude - 34.103264) * math.pi / 180 * 6371000.
  assert math.isclose(moved, 20. * EXTRA_LATENCY, abs_tol=0.05)
  assert math.isclose(gps.longitude, -84.243804, abs_tol=1e-6)
  assert gps.altitude == 290.
  assert gps.horizontalAccuracy > 0 and gps.verticalAccuracy > 0 and gps.speedAccuracy > 0
  assert gps.bearingAccuracyDeg < 180.


def test_stationary_and_stale_speed():
  state = TeslaGpsState()
  state.update(UI_GPS_VEHICLE_SPEED, _speed_frame(90., 0.), 0)
  gps = _fill(state, 500_000_000)
  assert gps.hasFix and gps.bearingAccuracyDeg == 180.
  assert math.isclose(gps.latitude, 34.103264, abs_tol=1e-6)
  assert not _fill(state, 5_000_000_000).hasFix  # speed frame older than 3 s


def test_nmea_mia_clears_fix():
  state = TeslaGpsState()
  state.update(UI_GPS_VEHICLE_SPEED, _speed_frame(0., 50., mia=1), 0)
  assert not _fill(state, 100_000_000).hasFix
