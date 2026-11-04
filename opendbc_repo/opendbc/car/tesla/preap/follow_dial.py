"""SCCM follow distance dial (STW_ACTN_RQ.DTR_Dist_Rq) -> NAP follow distance.

The dial reports an absolute position on every frame, including at rest, so the
first position seen after startup is only recorded: the dial takes over only once
the driver actually moves it. By default every new position is committed on the
first frame it appears; a non-zero debounce_ns requires it to hold that long.

The live level is published in carState for plannerd and the UI. It is persisted
to NAPFollowDistance only in Park after the dial has been still for SAVE_IDLE_NS:
an onroad param write fsyncs behind loggerd for seconds and stalls every other
param writer (hardwared -> commIssue).
"""

# DBC VAL_ table for DTR_Dist_Rq (255 = SNA)
DTR_DIST_TO_FOLLOW = {0: 1, 33: 2, 66: 3, 100: 4, 133: 5, 166: 6, 200: 7}
DEBOUNCE_NS = 0
SAVE_IDLE_NS = 2_000_000_000


class FollowDistanceDial:
  def __init__(self, debounce_ns: int = DEBOUNCE_NS):
    self.debounce_ns = debounce_ns
    self.committed: int | None = None
    self.level = 0  # live follow distance once the driver moved the dial, else 0
    self._candidate: int | None = None
    self._candidate_since_ns = 0
    self._unsaved = False
    self._changed_ns = 0

  def update(self, dtr_dist: int, ts_nanos: int) -> int | None:
    """Returns the new follow distance (1-7) when the driver moved the dial, else None."""
    follow = DTR_DIST_TO_FOLLOW.get(dtr_dist)
    if ts_nanos == 0 or follow is None:  # message not received yet, SNA, or invalid
      self._candidate = None
      return None

    if self.committed is None:
      self.committed = follow
      return None

    if follow == self.committed:
      self._candidate = None
      return None

    if follow != self._candidate:
      self._candidate = follow
      self._candidate_since_ns = ts_nanos

    if ts_nanos - self._candidate_since_ns >= self.debounce_ns:
      self.committed = follow
      self.level = follow
      self._candidate = None
      self._unsaved = True
      self._changed_ns = ts_nanos
      return follow
    return None

  def take_save(self, parked: bool, now_ns: int) -> int | None:
    """Returns the level to persist once, only in Park after the dial has been still."""
    if self._unsaved and parked and now_ns - self._changed_ns >= SAVE_IDLE_NS:
      self._unsaved = False
      return self.level
    return None
