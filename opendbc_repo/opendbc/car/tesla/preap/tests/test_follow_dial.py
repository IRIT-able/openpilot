import unittest

from opendbc.car.tesla.preap.follow_dial import DEBOUNCE_NS, FollowDistanceDial

MS = 1_000_000


class TestFollowDistanceDial(unittest.TestCase):
  def test_first_position_is_recorded_not_written(self):
    dial = FollowDistanceDial()
    self.assertIsNone(dial.update(0, 100 * MS))
    self.assertIsNone(dial.update(0, 400 * MS))
    self.assertEqual(dial.committed, 1)

  def test_not_received_and_sna_are_ignored(self):
    dial = FollowDistanceDial()
    self.assertIsNone(dial.update(0, 0))  # parser default before the first frame
    self.assertIsNone(dial.committed)
    self.assertIsNone(dial.update(255, 100 * MS))
    self.assertIsNone(dial.update(50, 200 * MS))  # not a DBC position
    self.assertIsNone(dial.committed)
    dial.update(133, 300 * MS)
    self.assertEqual(dial.committed, 5)

  def test_each_position_maps_to_dbc_level(self):
    for dtr, follow in ((0, 1), (33, 2), (66, 3), (100, 4), (133, 5), (166, 6), (200, 7)):
      with self.subTest(dtr=dtr):
        dial = FollowDistanceDial()
        dial.update(0 if dtr else 200, 1 * MS)
        dial.update(dtr, 100 * MS)
        self.assertEqual(dial.update(dtr, 100 * MS + DEBOUNCE_NS), follow)

  def test_roll_through_writes_once(self):
    dial = FollowDistanceDial()
    dial.update(0, 0 + 1)
    writes = [dial.update(dtr, t * 100 * MS) for t, dtr in enumerate((33, 66, 100, 166, 200, 200, 200, 200, 200), start=1)]
    self.assertEqual([w for w in writes if w is not None], [7])

  def test_return_to_committed_cancels_pending_change(self):
    dial = FollowDistanceDial()
    dial.update(100, 1 * MS)
    dial.update(133, 100 * MS)
    dial.update(100, 200 * MS)
    self.assertIsNone(dial.update(100, 100 * MS + DEBOUNCE_NS))
    self.assertEqual(dial.committed, 4)


if __name__ == "__main__":
  unittest.main()
