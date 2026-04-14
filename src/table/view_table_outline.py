from core.utils.settings import get_int, get_float
from core.transition.transition import get_ease

# Speed of comet animations, in Pixels/Second.
COMET_SPEED_PPS = get_int('TABLE_COMET_SPEED_PPS', 10)

# Easing function for color fades
FADE_EASE = get_ease('TABLE_FADE_EASE', 'LinearInOut')
# Duration of color fades
FADE_DURATION = get_float('TABLE_FADE_DURATION', 0.8)

from adafruit_pixelbuf import PixelBuf
from adafruit_led_animation.animation.rainbowcomet import RainbowComet
from adafruit_led_animation.animation.comet import Comet
import adafruit_logging as logging
log = logging.getLogger()
from gc import collect, mem_free

import core.reorder as reorder
from core.connection.sgt_connection import SgtConnection
from core.view.view import View
from core.game_state import GameState
from core.sgt_animation import SgtAnimation, SgtSolid
from core.color import BLUE as BLUE_PC, RED as RED_PC, BLACK as BLACK_PC
from core.transition.transition import SerialTransitionFunctions, PropertyTransition

BLACK = BLACK_PC.black
BLUE = BLUE_PC.highlight
RED = RED_PC.highlight

class ViewTableOutline(View):
	seats_with_pressed_keys: set[int]
	sgt_connection: SgtConnection
	def __init__(self,
			pixels: PixelBuf,
			seat_definitions: list[tuple[float, int]],
		):
		super().__init__()
		self.pixels = pixels
		self.seat_definitions = seat_definitions
		self.seat_count = len(seat_definitions)
		self.seats_with_pressed_keys = set()
		self.pixels.auto_write = False
		self.comet_refresh_rate = 1/COMET_SPEED_PPS
		self.animation = SgtAnimation(BLACK, (SgtSolid(self.pixels, 0x0), None, True))
		self.switch_to_not_connected()
	def set_connection(self, connection: SgtConnection):
		self.sgt_connection = connection
	def animate(self) -> bool:
		shared_stuff_busy = super().animate()
		from table.seated_animation.seated_reorder import SgtSeatedReorder
		if reorder.singleton is not None and not isinstance(self.animation, SgtSeatedReorder):
			self.fade_to_new_animation(SgtSeatedReorder(self))
		elif reorder.singleton is None and isinstance(self.animation, SgtSeatedReorder):
			self.set_state(self.state, True)
		if self.fade_to_black_tranny != None:
			if self.fade_to_black_tranny.loop():
				self.fade_to_black_tranny = None
				self.fade_out_animation = None
			elif len(self.fade_to_black_tranny.fns) < 2:
				self.fade_out_animation = None
		if self.fade_out_animation:
			this_animation_busy = self.fade_out_animation.animate()
		else:
			this_animation_busy = self.animation.animate()
		return this_animation_busy or shared_stuff_busy
	def fade_to_new_animation(self, new_animation):
		self.fade_out_animation = self.animation
		self.animation = new_animation
		self.fade_to_black_tranny = SerialTransitionFunctions([
			PropertyTransition(self.pixels, 'brightness', 0, FADE_EASE, FADE_DURATION),
			PropertyTransition(self.pixels, 'brightness', 1, FADE_EASE, FADE_DURATION)
		])
	def set_connection_progress_text(self, text):
		pass
	def switch_to_playing(self, state: GameState, old_state: GameState):
		self._activate_singleplayer_animation()
	def switch_to_simultaneous_turn(self, state: GameState, old_state: GameState):
		self._activate_multiplayer_animation()
	def switch_to_admin_time(self, state: GameState, old_state: GameState):
		for player in state.players:
			if player.action == 'in':
				self._activate_multiplayer_animation()
				return
			elif player.action != None:
				self._activate_singleplayer_animation()
				return
		raise Exception('Weird admin state...')
	def switch_to_paused(self, state: GameState, old_state: GameState):
		log.debug(f'--> Free memory: {mem_free():,} @ switch_to_paused b4')
		collect()
		log.debug(f'--> Free memory: {mem_free():,} @ switch_to_paused after')
		from table.seated_animation.seated_pause import SgtPauseAnimation
		if not isinstance(self.animation, SgtPauseAnimation):
			self.fade_to_new_animation(SgtPauseAnimation(self))
	def switch_to_sandtimer_running(self, state: GameState, old_state: GameState):
		raise Exception('Not implemented yet')
	def switch_to_sandtimer_not_running(self, state: GameState, old_state: GameState):
		raise Exception('Not implemented yet')
	def switch_to_start(self, state: GameState, old_state: GameState):
		self._activate_multiplayer_animation()
	def switch_to_end(self, state: GameState, old_state: GameState):
		self._activate_multiplayer_animation()
	def switch_to_no_game(self):
		super().switch_to_no_game()
		self.fade_to_new_animation(SgtAnimation(
			BLACK,
			(RainbowComet(self.pixels, self.comet_refresh_rate, tail_length=round(len(self.pixels)/2), ring=True), None, True),
		))
	def switch_to_not_connected(self):
		super().switch_to_not_connected()
		self.fade_to_new_animation(SgtAnimation(
			BLUE,
			(Comet(self.pixels, self.comet_refresh_rate, 0x0, tail_length=round(len(self.pixels)/2), ring=True), None, True),
		))
	def switch_to_error(self):
		super().switch_to_error()
		from table.seated_animation.seated_error import SgtErrorAnimation
		if not isinstance(self.animation, SgtErrorAnimation):
			self.fade_to_new_animation(SgtErrorAnimation(self))
	def switch_to_random_start_animation(self, start_game_mode: str):
		from table.seated_animation.seated_random_start_animation import SgtSeatedRandomStartAnimation
		self.fade_to_new_animation(SgtSeatedRandomStartAnimation(self, start_game_mode))
	def on_state_update(self, state: GameState|None, old_state: GameState|None):
		from table.seated_animation.seated_animation import SgtSeatedAnimation
		if isinstance(self.animation, SgtSeatedAnimation):
			self.animation.on_state_update(state, old_state)
	def _activate_multiplayer_animation(self):
		from table.seated_animation.seated_multiplayer import SgtSeatedMultiplayerAnimation
		if not isinstance(self.animation, SgtSeatedMultiplayerAnimation):
			self.fade_to_new_animation(SgtSeatedMultiplayerAnimation(self))
	def _activate_singleplayer_animation(self):
		from table.seated_animation.seated_singleplayer import SgtSeatedSingleplayerAnimation
		if not isinstance(self.animation, SgtSeatedSingleplayerAnimation):
			from table.seated_animation.seated_random_start_animation import SgtSeatedRandomStartAnimation
			random_first_player = None if not isinstance(self.animation, SgtSeatedRandomStartAnimation) else self.animation.selected_player
			if random_first_player == None:
				self.fade_to_new_animation(SgtSeatedSingleplayerAnimation(self))
			else:
				self.animation = SgtSeatedSingleplayerAnimation(self, random_first_player)
	def on_time_reminder(self, time_reminder_count: int):
		from table.seated_animation.seated_animation import SgtSeatedAnimation
		if isinstance(self.animation, SgtSeatedAnimation):
			self.animation.on_time_reminder(time_reminder_count)
	def on_pressed_seats_change(self, seats: set[int]):
		self.seats_with_pressed_keys = seats
		from table.seated_animation.seated_sim_turn_selection import SgtSeatedSimTurnSelection
		if isinstance(self.animation, SgtSeatedSimTurnSelection):
			self.animation.on_pressed_keys_change()
	def begin_sim_turn_selection(self, seat: int):
		if self.state.allow_sim_turn_start():
			from table.seated_animation.seated_sim_turn_selection import SgtSeatedSimTurnSelection
			self.fade_to_new_animation(SgtSeatedSimTurnSelection(self, seat))
