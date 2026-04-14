from core.utils.settings import get_int, get_float
from core.transition.transition import get_ease

# How big should the pulse be as a fraction of the edges.
ERROR_MAX_FRACTION_OF_EDGE_FOR_PULSE = get_float('TABLE_ERROR_MAX_FRACTION_OF_EDGE_FOR_PULSE', 1/3)
# Time in seconds for the pulse to go from 0 to max length, or vice versa.
ERROR_PULSE_DURATION = get_float('TABLE_ERROR_PULSE_DURATION', 1.0)
# How many pulses do we do?
ERROR_PULSE_COUNT = get_int('TABLE_ERROR_PULSE_COUNT', 2)
# The minimum time after the pules to stay black.
ERROR_PAUSE_TIME = get_float('TABLE_ERROR_PAUSE_TIME', 1.0)
# This is re-using the warn easing, but you can import anything you want from easing
ERROR_EASINGS = (get_ease('TABLE_ERROR_EASE_IN', 'CircularEaseIn'), get_ease('TABLE_ERROR_EASE_OUT', 'CircularEaseIn'))

import adafruit_logging as logging
log = logging.getLogger()

from core.transition.transition import CallbackTransitionFunction, SerialTransitionFunctions, NoOpTransition
from table.seated_animation.seated_animation import SgtSeatedAnimation, Line
from table.view_table_outline import ViewTableOutline, BLACK, RED

class SgtErrorAnimation(SgtSeatedAnimation):
	seat_lines: list[Line]
	def __init__(self, parent_view: ViewTableOutline):
		super().__init__(parent_view)
		self.seat_lines = []
		self.seat_line_max_lengths = []
		seat_count = len(self.parent.seat_definitions)
		self.bg_color = BLACK.create_display_color()
		self.overall_transition = SerialTransitionFunctions([])
		for i in range(seat_count):
			s1 = self.parent.seat_definitions[i]
			s2 = self.parent.seat_definitions[(i+1)%seat_count]
			self.seat_lines.append(Line(midpoint=s1[0]+s1[1]/2, length=0, color_ds=RED))
			self.seat_line_max_lengths.append(round(min(s1[1], s2[1])*ERROR_MAX_FRACTION_OF_EDGE_FOR_PULSE))

	def set_lengths(self, progress: float):
		for i in range(len(self.parent.seat_definitions)):
			self.seat_lines[i].length = progress * self.seat_line_max_lengths[i]

	def animate(self):
		if len(self.overall_transition.fns) == 0:
			for _n in range(ERROR_PULSE_COUNT):
				fade_in = CallbackTransitionFunction(ERROR_EASINGS[0](0, 1, ERROR_PULSE_DURATION/2), callback=self.set_lengths)
				fade_out = CallbackTransitionFunction(ERROR_EASINGS[1](1, 0, ERROR_PULSE_DURATION/2), callback=self.set_lengths)
				self.overall_transition.fns.append(fade_in)
				self.overall_transition.fns.append(fade_out)
			pause = NoOpTransition(ERROR_PAUSE_TIME)
			self.overall_transition.fns.append(pause)

		self.overall_transition.loop()
		self.pixels.fill(self.bg_color.current_color)
		for line in self.seat_lines:
			line.draw(self.pixels)
		self.pixels.show()
		return len(self.overall_transition.fns) > 1
