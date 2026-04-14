from core.utils.settings import get_float
from core.transition.transition import get_ease

# The easing to do for the seat animation 'pulse'
REORDER_EASE = get_ease('TABLE_REORDER_EASE', 'SineEaseOut')
# The duration of each seat animation 'pulse'
REORDER_DURATION_PER_SEAT = get_float('TABLE_REORDER_DURATION_PER_SEAT', 0.5)
# The time to pause between each seat ordering animation
REORDER_DURATION_PAUSE = get_float('TABLE_REORDER_DURATION_PAUSE', 1.0)
# The length of the lines when not pulsing
REORDER_LINE_LENGTH_FRACTION = get_float('TABLE_REORDER_LINE_LENGTH_FRACTION', 0.33)

START_GAME_MODE_SCRAMBLE_PLAYER_ORDER = "scramble_player_order"
START_GAME_MODE_RANDOMIZE_FIRST_PLAYER = "randomize_first_player"
START_GAME_MODE_USE_CURRENT_ORDER = "use_current_order"

from math import ceil
import time
import adafruit_logging as logging
log = logging.getLogger()

from core.game_state import GameState, STATE_START, STATE_SIM_TURN, STATE_ADMIN, Player
from core.transition.transition import PropertyTransition, SerialTransitionFunctions, ColorTransitionFunction, ParallellTransitionFunctions, BoomerangEase
from table.seated_animation.seated_animation import SgtSeatedAnimation, Line, LineTransition, TIME_REMINDER_EASINGS, TIME_REMINDER_MAX_PULSES, TIME_REMINDER_PULSE_DURATION
from table.view_table_outline import ViewTableOutline, BLACK, FADE_EASE, FADE_DURATION

class SgtSeatedMultiplayerAnimation(SgtSeatedAnimation):
	def __init__(self, parent_view: ViewTableOutline):
		super().__init__(parent_view)
		self.seat_lines = list(LineTransition(Line(midpoint=s[0], length=0, color_ds=BLACK), transitions=[]) for s in self.seat_definitions)
		self.blinks_left = 0
		self.blink_transition = None
		self.current_times = None
		self.state = None
		self.first_player_init_ts = None
		self.start_game_mode = None
		self.order_player_index = None
		self.order_animation_ts = None

	def animate(self):
		is_busy = False
		self.pixels.fill(0x0)

		# There is no blinking during GAME SETUP
		if self.start_game_mode == None:
			if self.blink_transition == None and self.blinks_left > 0:
				self.blinks_left = self.blinks_left - 1
				self.blink_transition = SerialTransitionFunctions([
					PropertyTransition(self.pixels, 'brightness', 0, TIME_REMINDER_EASINGS[0], TIME_REMINDER_PULSE_DURATION/2),
					PropertyTransition(self.pixels, 'brightness', 1, TIME_REMINDER_EASINGS[1], TIME_REMINDER_PULSE_DURATION/2),
				])
			if self.blink_transition != None and self.blink_transition.loop():
				self.blink_transition = None
			is_busy = is_busy or self.blinks_left > 0 or self.blink_transition != None

		if self.order_player_index != None:
			# We must be in the order animation mode.
			animation_progress = time.monotonic() - self.order_animation_ts
			duration_of_current_animation = REORDER_DURATION_PER_SEAT if self.order_player_index >= 0 else REORDER_DURATION_PAUSE
			divider, remainder_in_seconds= divmod(animation_progress, duration_of_current_animation)
			if divider > 0:
				# Update the currently animated player index
				self.order_player_index += int(divider)
				# Reset the animation start time to the remainder of this animation cycle
				self.order_animation_ts = time.monotonic() - remainder_in_seconds

			# We need to ensure that the animated player index is always within the right
			# range of the number of players. The state can change at any time, so we always
			# need to do this correction. We go to -1 if we want a break between the last and
			# first player, otherwise we round back to 0, the first player immediately.
			if self.order_player_index >= len(self.state.players):
				self.order_player_index = -1 if self.start_game_mode == START_GAME_MODE_USE_CURRENT_ORDER else 0

			if self.order_player_index >= 0:
				indicated_player_lengt_percentage = BoomerangEase(REORDER_LINE_LENGTH_FRACTION, 1, REORDER_EASE, REORDER_DURATION_PER_SEAT).func(remainder_in_seconds)

		for seat_0, seat_line in enumerate(self.seat_lines):
			if len(seat_line.transitions) > 0:
				if(seat_line.transitions[0].loop()):
					seat_line.transitions = seat_line.transitions[1:]
			is_busy = is_busy or len(seat_line.transitions) > 0
			seat_line.line.sparkle = self.parent.state.state == STATE_START and (seat_0+1) in self.parent.seats_with_pressed_keys
			if self.order_player_index == None:
				# We must be in fully random or not-starting mode. So, full lengths for all
				length_percentage = 1.0
			elif self.order_player_index >= 0 and self.state.players[self.order_player_index].seat == seat_0 + 1:
				# This is the indicated player. So used the variable length calculated above
				length_percentage = indicated_player_lengt_percentage
			else:
				# We are in the pause between the last and first player or one of the
				# un-indicated players. So, reduced length.
				length_percentage = REORDER_LINE_LENGTH_FRACTION
			seat_line.line.draw(self.pixels, length_percentage=length_percentage)
		self.pixels.show()
		if self.start_game_mode != None:
			self.first_player_check()
		return is_busy

	def on_state_update(self, state: GameState, old_state: GameState):
		self.state = state
		if state.state != STATE_START:
			self.start_game_mode = None
			self.order_player_index = None
			self.order_animation_ts = None
		elif self.start_game_mode == None:
			self.cycle_start_game_mode()

		for seat_0, line_definition in enumerate(self.seat_definitions):
			new_color_s = None
			new_length = line_definition[1]
			player = next((p for p in state.players if p.seat == seat_0+1), None)
			if not isinstance(player, Player):
				new_color_s = None
			elif state.state == STATE_SIM_TURN:
				if (seat_0+1) in state.seat:
					# Player is involved.
					new_color_s = player.color.highlight
					if player.action != 'in':
						# Player has passed
						new_length = ceil(new_length / 4)
						new_color_s = player.color.dim
			elif state.state == STATE_ADMIN:
				if (seat_0+1) in state.seat:
					# Player is involved. Since it is an admin turn, all involved players gets a short line.
					new_color_s = player.color.dim
					new_length = ceil(new_length / 4)
			else:
				new_color_s = player.color.dim

			seat = self.seat_lines[seat_0]
			old = seat.line
			if old.color_d == BLACK and new_color_s != None and old.color_d != new_color_s:
				old.length = 0
				old.color_d = new_color_s.create_display_color()
				seat.transitions = [PropertyTransition(old, 'length', new_length, FADE_EASE, FADE_DURATION)]
			elif old.color_d != BLACK and new_color_s == None:
				seat.transitions = [PropertyTransition(old, 'length', 0, FADE_EASE, FADE_DURATION)]
			elif old.color_d != BLACK and (old.color_d != new_color_s or old.length != new_length):
				trannies = []
				if old.color_d != new_color_s:
					trannies.append(ColorTransitionFunction(old.color_d, new_color_s, FADE_EASE(0, 1, FADE_DURATION)))
				if old.length != new_length:
					trannies.append(PropertyTransition(old, 'length', new_length, FADE_EASE, FADE_DURATION))
				seat.transitions = [ParallellTransitionFunctions(*trannies)]

	def on_time_reminder(self, time_reminder_count: int):
		self.blinks_left = min(time_reminder_count, TIME_REMINDER_MAX_PULSES)
		self.blink_transition = None

	def first_player_check(self):
		# Temporarily start the first-player selection on first press. Later, wait for all buttons to be pressed.
		# all_pressed = len(self.parent.seats_with_pressed_keys) > 1
		all_pressed = len(self.parent.seats_with_pressed_keys) > 1 and len(self.parent.state.players) == len(self.parent.seats_with_pressed_keys)
		if not all_pressed:
			self.first_player_init_ts = None
		elif self.first_player_init_ts == None:
			self.first_player_init_ts = time.monotonic()
		elif time.monotonic() - self.first_player_init_ts > 1:
			if self.start_game_mode == START_GAME_MODE_USE_CURRENT_ORDER:
				self.parent.sgt_connection.enqueue_send_start_game()
			else:
				self.parent.switch_to_random_start_animation(self.start_game_mode)

	def cycle_start_game_mode(self):
		# Order goes No Mode -> Keep Order -> Random 1st -> Scramble -> Keep Order
		# Scramble has no index as there is no order.
		# The other two does show the order, so must set the index
		if self.start_game_mode == START_GAME_MODE_RANDOMIZE_FIRST_PLAYER:
			self.start_game_mode = START_GAME_MODE_SCRAMBLE_PLAYER_ORDER
			self.order_player_index = None
			self.order_animation_ts = None
		elif self.start_game_mode == START_GAME_MODE_SCRAMBLE_PLAYER_ORDER or self.start_game_mode == None:
			self.start_game_mode = START_GAME_MODE_USE_CURRENT_ORDER
			self.order_player_index = 0
			self.order_animation_ts = time.monotonic()
		elif self.start_game_mode == START_GAME_MODE_USE_CURRENT_ORDER:
			self.start_game_mode = START_GAME_MODE_RANDOMIZE_FIRST_PLAYER