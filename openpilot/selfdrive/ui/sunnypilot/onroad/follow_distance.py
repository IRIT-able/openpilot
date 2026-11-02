"""NAP follow distance badge, drawn under the MAX set speed box on Pre-AP Teslas.

Reads NAPFollowDistance directly (~10 Hz) so a dial or settings change shows up
as soon as it is stored; plannerd picks the same value up within 0.25 s.
"""
import pyray as rl

from opendbc.car.tesla.preap.nap_params import NAPParamKeys
from openpilot.common.params import Params
from openpilot.selfdrive.ui.onroad.hud_renderer import UI_CONFIG, COLORS
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

LEVELS = 7
POLL_HZ = 10
HIGHLIGHT_S = 2.0

BOX_HEIGHT = 96
BOX_GAP = 20
BAR_WIDTH = 14
BAR_GAP = 6
BAR_DIM = rl.Color(255, 255, 255, 50)


class FollowDistanceRenderer(Widget):
  def __init__(self):
    super().__init__()
    self.level: int | None = None
    self._params = Params()
    self._poll_frame = 0
    self._highlight_frames = 0
    self._font = gui_app.font(FontWeight.SEMI_BOLD)

  def update(self):
    CP = ui_state.CP
    if CP is None or CP.carFingerprint != "TESLA_MODEL_S_PREAP" or not CP.openpilotLongitudinalControl:
      self.level = None
      return

    self._poll_frame += 1
    if self.level is None or self._poll_frame >= gui_app.target_fps // POLL_HZ:
      self._poll_frame = 0
      level = int(self._params.get(NAPParamKeys.FOLLOW_DISTANCE, return_default=True) or 4)
      level = max(1, min(LEVELS, level))
      if self.level is not None and level != self.level:
        self._highlight_frames = int(HIGHLIGHT_S * gui_app.target_fps)
      self.level = level

    if self._highlight_frames > 0:
      self._highlight_frames -= 1

  def _render(self, rect: rl.Rectangle):
    if self.level is None:
      return

    width = UI_CONFIG.set_speed_width_metric if ui_state.is_metric else UI_CONFIG.set_speed_width_imperial
    x = rect.x + 60 + (UI_CONFIG.set_speed_width_imperial - width) // 2
    y = rect.y + 45 + UI_CONFIG.set_speed_height + BOX_GAP
    box = rl.Rectangle(x, y, width, BOX_HEIGHT)

    highlighted = self._highlight_frames > 0
    if highlighted:
      color = COLORS.WHITE
    elif ui_state.status == UIStatus.ENGAGED:
      color = COLORS.ENGAGED
    else:
      color = COLORS.GREY

    rl.draw_rectangle_rounded(box, 0.35, 10, COLORS.BLACK_TRANSLUCENT)
    rl.draw_rectangle_rounded_lines_ex(box, 0.35, 10, 6, COLORS.WHITE if highlighted else COLORS.BORDER_TRANSLUCENT)

    label = f"{tr('FOLLOW')} {self.level}"
    font_size = 34
    label_size = measure_text_cached(self._font, label, font_size)
    rl.draw_text_ex(self._font, label, rl.Vector2(x + (width - label_size.x) / 2, y + 10), font_size, 0, color)

    # Bars grow left to right; filled up to the current level
    bars_width = LEVELS * BAR_WIDTH + (LEVELS - 1) * BAR_GAP
    bars_x = x + (width - bars_width) / 2
    bars_bottom = y + BOX_HEIGHT - 14
    for i in range(LEVELS):
      bar_height = 12 + i * 4
      bar = rl.Rectangle(bars_x + i * (BAR_WIDTH + BAR_GAP), bars_bottom - bar_height, BAR_WIDTH, bar_height)
      rl.draw_rectangle_rounded(bar, 0.3, 4, color if i < self.level else BAR_DIM)
