import unittest

from opendbc.car.tesla.preap.tesla_gps import (
  MPH_TO_MS, KPH_TO_MS, TeslaLocation, decode_elevation, decode_gps_speed, decode_location,
  location_has_fix, mpp_speed_limit_ms,
)


def _frame(*fields: tuple[int, int, int]) -> bytes:
  """Pack (start, size, raw) little-endian signals into an 8-byte frame."""
  v = 0
  for start, size, raw in fields:
    v |= (raw & ((1 << size) - 1)) << start
  return v.to_bytes(8, 'little')


class TestTeslaGps(unittest.TestCase):
  def test_location_from_drive_log(self):
    # MCU_locationStatus captured on a 2014 Model S (route 0000003f, segment 22)
    loc = decode_location(bytes.fromhex("e05f0842aaa8af0d"))
    self.assertAlmostEqual(loc.latitude, 34.103264, places=6)
    self.assertAlmostEqual(loc.longitude, -84.243804, places=6)
    self.assertAlmostEqual(loc.accuracy, 1.2, places=3)

  def test_gps_speed_and_mph_speed_limit(self):
    dat = _frame((0, 8, 5), (8, 16, round(226.9 / 0.0078125)), (24, 16, round(118.8 / 0.00390625)),
                 (46, 1, 0), (48, 5, 13), (53, 1, 0))
    s = decode_gps_speed(dat)
    self.assertAlmostEqual(s.hdop, 0.5)
    self.assertAlmostEqual(s.heading_deg, 226.9, places=2)
    self.assertAlmostEqual(s.speed, 118.8 * KPH_TO_MS, places=2)
    self.assertAlmostEqual(s.speed_limit, 65 * MPH_TO_MS)
    self.assertFalse(s.nmea_mia)

  def test_speed_limit_units_and_invalid(self):
    self.assertAlmostEqual(mpp_speed_limit_ms(10, units_kph=True), 50 * KPH_TO_MS)
    self.assertEqual(mpp_speed_limit_ms(0, units_kph=False), 0.)
    self.assertEqual(mpp_speed_limit_ms(31, units_kph=False), 0.)

  def test_elevation_signed(self):
    self.assertAlmostEqual(decode_elevation(_frame((0, 32, 2902))), 290.2)
    self.assertAlmostEqual(decode_elevation(_frame((0, 32, -15))), -1.5)

  def test_fix_requires_speed_frame_and_accuracy(self):
    loc = TeslaLocation(34.1, -84.2, 1.6)
    speed = decode_gps_speed(_frame((53, 1, 0)))
    self.assertTrue(location_has_fix(loc, speed))
    self.assertFalse(location_has_fix(loc, None))
    self.assertFalse(location_has_fix(loc, decode_gps_speed(_frame((53, 1, 1)))))
    self.assertFalse(location_has_fix(TeslaLocation(34.1, -84.2, 0.), speed))
    self.assertFalse(location_has_fix(TeslaLocation(0., 0., 1.6), speed))


if __name__ == "__main__":
  unittest.main()
