from core.utils.settings import get_float
from core.transition.transition import get_ease, BoomerangEase

# The easing to do for the seat animation 'pulse'
REORDER_EASE = get_ease('TABLE_REORDER_EASE', 'SineEaseOut')
# The duration of each seat animation 'pulse'
REORDER_DURATION_PER_SEAT = get_float('TABLE_REORDER_DURATION_PER_SEAT', 0.5)
# The time to pause between each seat reordering animation
REORDER_DURATION_PAUSE = get_float('TABLE_REORDER_DURATION_PAUSE', 1.0)
# The length of the lines when user is pressing their keys to reorder the table, as a fraction of the full length
REORDER_LINE_LENGTH_FRACTION = get_float('TABLE_REORDER_LINE_LENGTH_FRACTION', 0.33)

from time import monotonic
import adafruit_logging as logging
log = logging.getLogger()

import core.reorder as reorder
from table.seated_animation.seated_animation import SgtSeatedAnimation, Line
from table.view_table_outline import ViewTableOutline, BLACK

class SgtSeatedReorder(SgtSeatedAnimation):
	seat_lines: list[Line]
	ts_animation_start: float
	def __init__(self, parent_view: ViewTableOutline):
		super().__init__(parent_view)
		self.seat_lines = []
		for seat_0, s in enumerate(self.seat_definitions):
			seat = seat_0+1
			player = self.parent.state.get_player_by_seat(seat)
			if player == None:
				line = Line(midpoint=s[0], length=0, color_ds=BLACK)
			else:
				line = Line(midpoint=s[0], length=0, color_ds=player.color.dim)
			self.seat_lines.append(line)
		self.ts_animation_start = monotonic()

	def animate(self):
		self.pixels.fill(0x0)
		if reorder.singleton is not None:
			for seat_0, s in enumerate(self.seat_definitions):
				seat = seat_0+1
				if seat in reorder.singleton.new_seat_order:
					self.seat_lines[seat_0].length = s[1] * REORDER_LINE_LENGTH_FRACTION
				else:
					self.seat_lines[seat_0].length = 0
			animation_progress = monotonic() - self.ts_animation_start
			animating_order_index, seat_animation_progress_in_seconds= divmod(animation_progress, REORDER_DURATION_PER_SEAT)
			if animating_order_index < len(reorder.singleton.new_seat_order):
				animating_seat = reorder.singleton.new_seat_order[int(animating_order_index)]
				animating_seat_index = animating_seat - 1
				full_line_length = self.seat_definitions[animating_seat_index][1]
				line = self.seat_lines[animating_seat_index]
				line.length = BoomerangEase(line.length, full_line_length, REORDER_EASE, REORDER_DURATION_PER_SEAT).func(seat_animation_progress_in_seconds)
				# seat_animation_progress = REORDER_EASE.func(seat_animation_progress_in_seconds / REORDER_DURATION_PER_SEAT)
				# line.length = line.length * (1-seat_animation_progress) + seat_animation_progress * full_line_length
				# line.length = new_line_length
			elif animation_progress > len(reorder.singleton.new_seat_order) * REORDER_DURATION_PER_SEAT + REORDER_DURATION_PAUSE:
				self.ts_animation_start = monotonic()

		for seat_line in self.seat_lines:
			seat_line.draw(self.pixels)
		self.pixels.show()
		return False
