import adafruit_logging as logging
log = logging.getLogger()

from core.transition.transition import PropertyTransition
from table.seated_animation.seated_animation import SgtSeatedAnimation, Line, LineTransition
from table.view_table_outline import ViewTableOutline, BLACK, FADE_EASE, FADE_DURATION

class SgtSeatedSimTurnSelection(SgtSeatedAnimation):
	seat_lines: list[LineTransition]
	def __init__(self, parent_view: ViewTableOutline, initiator_seat: int):
		super().__init__(parent_view)
		self.seat_lines = []
		for seat_0, s in enumerate(self.seat_definitions):
			seat = seat_0+1
			player = self.parent.state.get_player_by_seat(seat)
			if player == None:
				line = Line(midpoint=s[0], length=0, color_ds=BLACK)
			elif seat == initiator_seat:
				line = Line(midpoint=s[0], length=s[1], color_ds=player.color.dim)
				line.sparkle = True
			elif seat in self.parent.seats_with_pressed_keys:
				line = Line(midpoint=s[0], length=s[1], color_ds=player.color.dim)
			else:
				line = Line(midpoint=s[0], length=0, color_ds=player.color.dim)
			self.seat_lines.append(LineTransition(line, []))
		self.initiator_seat = initiator_seat
		self.selection_completed = False
		self.has_seen_more_than_initiator = len(self.parent.seats_with_pressed_keys) > 1

	def animate(self):
		self.pixels.fill(0x0)
		for seat_line in self.seat_lines:
			if len(seat_line.transitions) > 0:
				if(seat_line.transitions[0].loop()):
					seat_line.transitions = seat_line.transitions[1:]
			seat_line.line.draw(self.pixels)
		self.pixels.show()
		return False

	def on_pressed_keys_change(self):
		if self.selection_completed:
			# We are done. Ignore button changes.
			return
		self.has_seen_more_than_initiator = self.has_seen_more_than_initiator or len(self.parent.seats_with_pressed_keys) > 1
		for seat_0, definition in enumerate(self.seat_definitions):
			seat = seat_0 + 1
			seat_line = self.seat_lines[seat_0]
			if seat in self.parent.seats_with_pressed_keys:
				if seat_line.line.length == 0:
					self.seat_lines[seat_0].transitions.append(PropertyTransition(seat_line.line, 'length', definition[1], FADE_EASE, FADE_DURATION))
			else:
				if seat == self.initiator_seat:
					# The player who initiated the sim turn selection has released their button.
					# Issue the Start Sim Turn command!
					self.selection_completed = True
					seats_in_sim_turn = self.parent.seats_with_pressed_keys.copy()
					for included_seat in seats_in_sim_turn:
						self.seat_lines[included_seat-1].line.sparkle = True
					seats_in_sim_turn.add(self.initiator_seat)
					if len(seats_in_sim_turn) == 1:
						# We only have the initiator. What should we do?
						if self.has_seen_more_than_initiator:
							# Cancel
							expect_state_change = False
						else:
							# Sim turn everyone
							for player in self.parent.state.players:
								seats_in_sim_turn.add(player.seat)
							expect_state_change = self.parent.sgt_connection.enqueue_send_start_sim_turn(seats_in_sim_turn)
					else:
						expect_state_change = self.parent.sgt_connection.enqueue_send_start_sim_turn(seats_in_sim_turn)
					if not expect_state_change:
						log.debug('Illegal state for sim turn. Rever state')
						state = self.parent.state
						self.parent.state = None
						self.parent.set_state(state)
					else:
						log.debug('Waiting for state update')
				elif seat_line.line.length != 0:
					self.seat_lines[seat_0].transitions.append(PropertyTransition(seat_line.line, 'length', 0, FADE_EASE, FADE_DURATION))
