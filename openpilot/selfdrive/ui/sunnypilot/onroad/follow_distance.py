"""NAP follow distance badge, drawn under the MAX set speed box on Pre-AP Teslas.

Shows the follow distance the planner is actually using (longitudinalPlan.tFollow),
so a dial change is confirmed once plannerd has picked it up.
"""
import pyray as rl

from openpilot.selfdrive.ui.onroad.hud_renderer import UI_CONFIG, COLORS
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget

# Must match NAP_T_FOLLOW in longitudinal_mpc_lib/long_mpc.py (not imported: it pulls in acados)
NAP_T_FOLLOW = (0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.9)
LEVELS = len(NAP_T_FOLLOW)
HIGHLIGHT_S = 2.0

BOX_HEIGHT = 96
BOX_GAP = 20
BAR_WIDTH = 14
BAR_GAP = 6
BAR_DIM = rl.Color(255, 255, 255, 50)


def follow_level_from_t_follow(t_follow: float) -> int | None:
  for i, t in enumerate(NAP_T_FOLLOW):
    if abs(t_follow - t) < 0.02:  # personality defaults (1.25/1.45/1.75 s) must not match
      return i + 1
  return None


class FollowDistanceRenderer(Widget):
  def __init__(self):
    super().__init__()
    self.level: int | None = None
    self._highlight_frames = 0
    self._font = gui_app.font(FontWeight.SEMI_BOLD)

  def update(self):
    CP = ui_state.CP
    if CP is None or CP.carFingerprint != "TESLA_MODEL_S_PREAP" or not CP.openpilotLongitudinalControl:
      self.level = None
      return

    sm = ui_state.sm
    if sm.updated["longitudinalPlan"]:
      level = follow_level_from_t_follow(sm["longitudinalPlan"].tFollow)
      if level is not None and self.level is not None and level != self.level:
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
