"""SCCM follow distance dial (STW_ACTN_RQ.DTR_Dist_Rq) -> NAP follow distance.

The dial reports an absolute position on every frame, including at rest, so the
first position seen after startup is only recorded: the NAP setting is changed
only when the driver actually moves the dial. A new position must hold for
DEBOUNCE_NS before it is committed, so rolling through several detents
quickly gives one write instead of one per intermediate value.
"""

# DBC VAL_ table for DTR_Dist_Rq (255 = SNA)
DTR_DIST_TO_FOLLOW = {0: 1, 33: 2, 66: 3, 100: 4, 133: 5, 166: 6, 200: 7}
DEBOUNCE_NS = 50_000_000  # at 10 Hz: same position on 2 consecutive frames


class FollowDistanceDial:
  def __init__(self, debounce_ns: int = DEBOUNCE_NS):
    self.debounce_ns = debounce_ns
    self.committed: int | None = None
    self._candidate: int | None = None
    self._candidate_since_ns = 0

  def update(self, dtr_dist: int, ts_nanos: int) -> int | None:
    """Returns a follow distance (1-7) to store, or None if nothing changed."""
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
      return None

    if ts_nanos - self._candidate_since_ns >= self.debounce_ns:
      self.committed = follow
      self._candidate = None
      return follow
    return None
