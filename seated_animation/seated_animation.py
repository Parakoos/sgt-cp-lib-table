from core.utils.settings import get_int, get_float
from core.transition.transition import get_ease

# Easing functions to and from a warning highlight, mostly during time reminders.
TIME_REMINDER_EASINGS = (get_ease('TABLE_TIME_REMINDER_EASE_IN', 'CubicEaseInOut'), get_ease('TABLE_TIME_REMINDER_EASE_OUT', 'CubicEaseInOut'))
# The duration of a warning
TIME_REMINDER_PULSE_DURATION = get_float('TABLE_TIME_REMINDER_PULSE_DURATION', 0.5)
# Maximum times a warning is shown in series
TIME_REMINDER_MAX_PULSES = get_int('TABLE_TIME_REMINDER_MAX_PULSES', 5)

# Easing functions for a sparkle
SPARKLE_EASINGS = (get_ease('TABLE_SPARKLE_EASE_IN', 'CubicEaseInOut'), get_ease('TABLE_SPARKLE_EASE_OUT', 'CubicEaseInOut'))
# How much of a side should be covered by sparkles? Between 0 and 1
SPARKLE_COVER = get_float('TABLE_SPARKLE_COVER', 1.0)
# The range of duration of a given sparkle.
SPARKLE_DURATION_MIN = get_float('TABLE_SPARKLE_DURATION_MIN', 0.1)
SPARKLE_DURATION_MAX = get_float('TABLE_SPARKLE_DURATION_MAX', 0.5)

import adafruit_logging as logging
log = logging.getLogger()
from random import uniform, choice
import adafruit_fancyled.adafruit_fancyled as fancy
from math import modf

from core.game_state import GameState
from core.color import DisplayedColor, StaticColor
from core.transition.transition import TransitionFunction, SerialTransitionFunctions
from table.view_table_outline import ViewTableOutline

class Line():
	sparkles: list[tuple[int, SerialTransitionFunctions]]
	color_d: DisplayedColor
	def __init__(self, midpoint: float, length: float, color_ds: DisplayedColor|StaticColor) -> None:
		self.midpoint = midpoint
		self.length = length
		if isinstance(color_ds, DisplayedColor):
			self.color_d = color_ds
		elif isinstance(color_ds, StaticColor):
			self.color_d = color_ds.create_display_color()
		else:
			raise TypeError(f"Expected Color, got {type(self.color_d)}")
		self.sparkle = False
		self.sparkles = list()
	def draw(self, pixels: list[int], length_percentage: float = 1.0):
		full_length_lower_bound = round(self.midpoint - (self.length/2))
		full_length_upper_bound = round(self.midpoint + (self.length/2))
		diff = full_length_upper_bound - full_length_lower_bound
		for n in range(full_length_lower_bound, full_length_upper_bound):
			pixels[n % len(pixels)] = 0x0
		lower_bound = round(self.midpoint - (self.length/2) * length_percentage)
		upper_bound = round(self.midpoint + (self.length/2) * length_percentage)
		for n in range(lower_bound, upper_bound):
			pixels[n % len(pixels)] = self.color_d.current_color
		if self.sparkle:
			if len(self.sparkles) < round(self.length * SPARKLE_COVER):
				unused_indices = [i for i in range(diff)]
				for spark in self.sparkles:
					try:
						unused_indices.remove(spark[0])
					except:
						log.info(f"ERROR! {spark[0]} not in {unused_indices}")
				if len(unused_indices) > 0:
					spark_index = choice(unused_indices)
					duration = uniform(SPARKLE_DURATION_MIN, SPARKLE_DURATION_MAX)
					sparkle_transition = SerialTransitionFunctions([
						TransitionFunction(SPARKLE_EASINGS[0](start=0, end=1, duration=duration/2)),
						TransitionFunction(SPARKLE_EASINGS[1](start=1, end=0, duration=duration/2)),
					])
					self.sparkles.append((spark_index, sparkle_transition))
		for spark in self.sparkles:
			tranny = spark[1].fns[0]
			done = spark[1].loop()
			if done:
				self.sparkles.remove(spark)
			else:
				i = full_length_lower_bound + spark[0]
				if lower_bound <= i < upper_bound:
					progress = tranny.value
					brightness = self.color_d.brightness * (1-progress) + progress
					pixels[i % len(pixels)] = fancy.gamma_adjust(self.color_d.fancy_color, brightness=brightness).pack()

	def __repr__(self):
		facts = []
		if (self.midpoint != None):
			facts.append(f'midpoint={self.midpoint}')
		if (self.length != None):
			facts.append(f'length={self.length}')
		if (self.color_d != None):
			facts.append(f'color={self.color_d}')
		return f"<Line: {', '.join(facts)}>"

class LineTransition():
	def __init__(self, line: Line, transitions: list[TransitionFunction]) -> None:
		self.line = line
		self.transitions = transitions
	def __repr__(self):
		facts = []
		if (self.line):
			facts.append(f'line={self.line}')
		if (self.transitions):
			facts.append(f'transitions={self.transitions}')
		return f"<LineTransition: {', '.join(facts)}>"

class SgtSeatedAnimation():
	def __init__(self, parent_view: ViewTableOutline):
		self.parent = parent_view
		self.pixels=parent_view.pixels
		self.seat_definitions = parent_view.seat_definitions
		self.length = len(self.pixels)

	def calc_dot(self, point: float, width: float, brightness: float, fade_into_brightness: float = 0.0):
		f, i_lower = modf(point-width/2)
		i_lower = int(i_lower)
		b_low = f * fade_into_brightness + (1-f) * brightness
		f, i_upper = modf(point+width/2)
		i_upper = int(i_upper)
		b_high = (1-f) * fade_into_brightness + f * brightness
		return (i_lower % self.length, b_low, i_upper % self.length, b_high, range(i_lower + 1, i_upper))

	def on_state_update(self, state: GameState, old_state: GameState):
		pass

	def on_time_reminder(self, time_reminder_count: int):
		pass
