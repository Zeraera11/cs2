import ctypes as C
import unittest
from unittest.mock import patch

from aim import INPUT, MouseAimer, aim_step, choose_target


MATRIX = (1, 0, 0, 0, 0, 0, 1, -36, 0, 0, 1, 0, 0, 1, 0, 0)
PLAYERS = [{'id': 1, 'health': 100, 'eye': (10, 100, 36)},
           {'id': 2, 'health': 100, 'eye': (20, 100, 36)}]


class AimTests(unittest.TestCase):
    def test_nearest_and_target_retention(self):
        self.assertEqual(choose_target(PLAYERS, MATRIX, 1000, 600, 150)[1], 1)
        self.assertEqual(choose_target(PLAYERS, MATRIX, 1000, 600, 150, previous=2)[1], 2)

    def test_radius_behind_camera_and_dead_players(self):
        self.assertIsNone(choose_target(PLAYERS, MATRIX, 1000, 600, 10))
        invalid = [{'health': 100, 'eye': (0, -100, 36)}, {'health': 0, 'eye': (0, 100, 36)}]
        self.assertIsNone(choose_target(invalid, MATRIX, 1000, 600, 150))

    def test_step_deadzone_and_limits(self):
        self.assertEqual(aim_step((501, 301), (500, 300), 0.16), (0, 0))
        self.assertEqual(aim_step((1000, 0), (500, 300), 0.5), (25, -25))
        self.assertEqual(aim_step((550, 300), (500, 300), 0.16), (8, 0))

    def test_input_structure_x64(self):
        self.assertEqual(C.sizeof(INPUT), 40)

    def step(self, aimer, age=0.02):
        return aimer.step(123, PLAYERS, MATRIX, 1000, 600, 150, 0.16, age)

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=0)
    def test_button_released_never_sends_input(self, key, rect, send):
        self.step(MouseAimer())
        send.assert_not_called()

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=None)
    @patch('aim.key_state', return_value=-32768)
    def test_background_game_never_sends_input(self, key, rect, send):
        self.step(MouseAimer())
        send.assert_not_called()

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=-32768)
    def test_stale_frame_never_sends_input(self, key, rect, send):
        self.step(MouseAimer(), age=0.2)
        send.assert_not_called()

    @patch('aim.send_input')
    @patch('aim.game_rect', side_effect=[(0, 0, 1000, 600), None])
    @patch('aim.key_state', return_value=-32768)
    def test_focus_changed_before_emission(self, key, rect, send):
        self.step(MouseAimer())
        send.assert_not_called()

    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=-32768)
    def test_only_relative_movement_no_clicks(self, key, rect):
        events = []

        def send(count, pointer, size):
            event = pointer._obj
            events.append((count, size, event.type, event.mi.dx, event.mi.dy, event.mi.dwFlags))
            return 1

        with patch('aim.send_input', side_effect=send):
            self.step(MouseAimer())
        self.assertEqual(events, [(1, 40, 0, 8, 0, 1)])

    @patch('aim.send_input', return_value=0)
    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=-32768)
    def test_blocked_input_returns_error(self, key, rect, send):
        aimer = MouseAimer()
        with self.assertRaises(OSError):
            self.step(aimer)
        self.assertIsNone(aimer.target)


if __name__ == '__main__':
    unittest.main()
