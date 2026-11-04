import unittest

from opendbc.car.tesla.preap.follow_dial import FollowDistanceDial

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
        self.assertEqual(dial.update(dtr, 100 * MS), follow)

  def test_default_commits_every_new_position_on_first_frame(self):
    dial = FollowDistanceDial()
    dial.update(0, 1)
    writes = [dial.update(dtr, t * 100 * MS) for t, dtr in enumerate((33, 66, 66, 100, 100, 66), start=1)]
    self.assertEqual(writes, [2, 3, None, 4, None, 3])

  def test_level_is_zero_until_driver_moves_dial(self):
    dial = FollowDistanceDial()
    dial.update(200, 1 * MS)
    self.assertEqual(dial.level, 0)
    dial.update(166, 100 * MS)
    self.assertEqual(dial.level, 6)

  def test_save_only_in_park_after_dial_is_still(self):
    dial = FollowDistanceDial()
    dial.update(0, 1 * MS)
    self.assertIsNone(dial.take_save(True, 10_000 * MS))  # never moved: nothing to save
    dial.update(100, 1000 * MS)
    self.assertIsNone(dial.take_save(False, 9000 * MS))  # driving
    self.assertIsNone(dial.take_save(True, 2900 * MS))  # parked, still < 2 s
    self.assertEqual(dial.take_save(True, 3000 * MS), 4)
    self.assertIsNone(dial.take_save(True, 4000 * MS))  # saved once

  def test_debounce_writes_only_settled_position(self):
    dial = FollowDistanceDial(debounce_ns=200 * MS)
    dial.update(0, 1)
    writes = [dial.update(dtr, t * 100 * MS) for t, dtr in enumerate((33, 66, 100, 166, 200, 200, 200, 200), start=1)]
    self.assertEqual([w for w in writes if w is not None], [7])

  def test_debounce_return_to_committed_cancels_pending_change(self):
    dial = FollowDistanceDial(debounce_ns=200 * MS)
    dial.update(100, 1 * MS)
    dial.update(133, 100 * MS)
    dial.update(100, 200 * MS)
    self.assertIsNone(dial.update(100, 400 * MS))
    self.assertEqual(dial.committed, 4)


if __name__ == "__main__":
  unittest.main()
