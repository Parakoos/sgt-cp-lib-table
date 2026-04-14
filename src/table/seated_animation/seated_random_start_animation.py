from core.utils.settings import get_int, get_float
from core.transition.transition import get_ease

# How many times do we spin around
START_GAME_SPIN_MIN_ROTATIONS = get_int('TABLE_START_GAME_SPIN_MIN_ROTATIONS', 5)
START_GAME_SPIN_MAX_ROTATIONS = get_int('TABLE_START_GAME_SPIN_MAX_ROTATIONS', 7)
# How fast does the spinning go, once ramped up. In Pixels/Seconds
START_GAME_SPIN_SPEED_PPS = get_int('TABLE_START_GAME_SPIN_SPEED_PPS', 30)
# How does the spinning ramp up/down
START_GAME_SPIN_EASE_IN = get_ease('TABLE_START_GAME_SPIN_EASE_IN', 'CubicEaseIn')
START_GAME_SPIN_EASE_IN_DURATION = get_float('TABLE_START_GAME_SPIN_EASE_IN_DURATION', 1.0)
START_GAME_SPIN_EASE_OUT = get_ease('TABLE_START_GAME_SPIN_EASE_OUT', 'CubicEaseOut')
START_GAME_SPIN_EASE_OUT_DURATION = get_float('TABLE_START_GAME_SPIN_EASE_OUT_DURATION', 1.0)
# Controls how colors shift between the potential player colors
START_GAME_COLOR_EASING = get_ease('TABLE_START_GAME_COLOR_EASING', 'CubicEaseOut')
START_GAME_COLOR_DURATION = get_float('TABLE_START_GAME_COLOR_DURATION', 1.0)

from random import choice, randint, random
import time
import adafruit_logging as logging
log = logging.getLogger()

from core.transition.transition import ColorTransitionFunction, RampUpDownTransitionFunction, PropertyTransition, SerialTransitionFunctions
from core.game_state import Player
from table.seated_animation.seated_animation import SgtSeatedAnimation, Line
from table.view_table_outline import ViewTableOutline, BLACK

class SgtSeatedRandomStartAnimation(SgtSeatedAnimation):
	random_player: Player
	shuffled_players: list[Player]
	def __init__(self, parent_view: ViewTableOutline, start_game_mode: str):
		super().__init__(parent_view)
		self.start_game_mode = start_game_mode
		self.shuffled_players = []
		unshuffled_players = self.parent.state.players.copy()
		while len(unshuffled_players) > 0:
			random_index = randint(0, len(unshuffled_players) - 1)
			self.shuffled_players.append(unshuffled_players.pop(random_index))
		self.selected_player = self.shuffled_players[0]
		selected_seat_definition = self.seat_definitions[self.selected_player.seat-1]
		selected_player_midpoint = selected_seat_definition[0]
		rotations_to_spin = randint(START_GAME_SPIN_MIN_ROTATIONS, START_GAME_SPIN_MAX_ROTATIONS)
		start_px = selected_player_midpoint + random() * self.length
		end_px = selected_player_midpoint + rotations_to_spin * self.length
		self.line = Line(midpoint=start_px, length=selected_seat_definition[1], color_ds=BLACK)
		self.spin_transition = RampUpDownTransitionFunction(START_GAME_SPIN_SPEED_PPS, start_px, end_px, START_GAME_SPIN_EASE_IN, START_GAME_SPIN_EASE_IN_DURATION, START_GAME_SPIN_EASE_OUT, START_GAME_SPIN_EASE_OUT_DURATION)
		self.bg_color = BLACK.create_display_color()
		self.color_transition_fg = None
		self.color_transition_bg = None
		self.end_ts = time.monotonic() + self.spin_transition.duration
		self.random_player = None
		self.start_game_command_sent = False

	def animate(self):
		done = self.spin_transition.loop()
		self.line.midpoint = self.spin_transition.value
		if self.start_game_command_sent:
			pass
		elif done:
			self.line.sparkle = True
			self.line.color_d = self.selected_player.color.highlight.create_display_color()
			self.bg_color = self.selected_player.color.dim.create_display_color()

			if self.start_game_mode == 'scramble_player_order' and len(self.shuffled_players) > 1:
				index = 1
				pulse_transitions = list()
				pulse_lines = list()
				while index < len(self.shuffled_players):
					player = self.shuffled_players[index]
					seat = player.seat
					seat_def = self.seat_definitions[seat-1]
					pulse_line = Line(midpoint=seat_def[0], length=0, color_ds=player.color.highlight)
					pulse_lines.append(pulse_line)
					pulse_transitions.append(PropertyTransition(pulse_line, 'length', seat_def[1], START_GAME_SPIN_EASE_IN, START_GAME_SPIN_EASE_IN_DURATION))
					pulse_transitions.append(PropertyTransition(pulse_line, 'length', 0, START_GAME_SPIN_EASE_IN, START_GAME_SPIN_EASE_IN_DURATION))
					index += 1
				pulse_animations = SerialTransitionFunctions(pulse_transitions)
				while True:
					is_done = pulse_animations.loop()
					self.pixels.fill(self.bg_color.current_color)
					self.line.draw(self.pixels)
					for pulse_line in pulse_lines:
						pulse_line.draw(self.pixels)
					self.pixels.show()
					if is_done:
						break
				seats = [player.seat for player in self.shuffled_players]
				self.parent.sgt_connection.enqueue_send_start_game(seats=seats)
			else:
				self.parent.sgt_connection.enqueue_send_start_game(seat=self.selected_player.seat)
			self.start_game_command_sent = True
		else:
			if self.color_transition_fg == None or self.color_transition_bg == None:
				time_left = self.end_ts - time.monotonic()
				if time_left < START_GAME_COLOR_DURATION*2:
					self.color_transition_fg = ColorTransitionFunction(self.line.color_d, self.selected_player.color.highlight, START_GAME_COLOR_EASING(duration=time_left))
					self.color_transition_bg = ColorTransitionFunction(self.bg_color, self.selected_player.color.dim, START_GAME_COLOR_EASING(duration=time_left))
				else:
					options = []
					for player in self.parent.state.players:
						if player != self.random_player:
							options.append(player)
					self.random_player = choice(options)
					self.color_transition_fg = ColorTransitionFunction(self.line.color_d, self.random_player.color.highlight, START_GAME_COLOR_EASING(duration=START_GAME_COLOR_DURATION))
					self.color_transition_bg = ColorTransitionFunction(self.bg_color, self.random_player.color.dim, START_GAME_COLOR_EASING(duration=START_GAME_COLOR_DURATION))

			if self.color_transition_fg.loop():
				self.color_transition_fg = None
			if self.color_transition_bg.loop():
				self.color_transition_bg = None

		self.pixels.fill(self.bg_color.current_color)
		self.line.draw(self.pixels)
		self.pixels.show()

		if (done and len(self.parent.seats_with_pressed_keys) > 1):
			log.debug('Switch back to normal state!')
			self.parent.switch_to_start(self.parent.state, None)
			self.parent.set_state(self.parent.state)

		return True