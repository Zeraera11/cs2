import unittest
from unittest.mock import patch

from aim import MouseAimer

MATRIX = (1, 0, 0, 0, 0, 0, 1, -36, 0, 0, 1, 0, 0, 1, 0, 0)
CENTERED = [{'id': 1, 'health': 100, 'eye': (0, 100, 36)}]


class ActionTests(unittest.TestCase):
    def step(self, aimer, now, players=CENTERED, **options):
        return aimer.step(123, players, MATRIX, 1000, 600, 150, 0.16, 0.02, now=now, **options)

    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', side_effect=lambda key: -32768 if key == 0x02 else 0)
    def test_trigger_dwell_cooldown_and_click_pair(self, key, rect):
        calls = []

        def send(count, events, size):
            calls.append([events[index].mi.dwFlags for index in range(count)])
            return count

        aimer = MouseAimer()
        with patch('aim.send_input', side_effect=send):
            self.step(aimer, 1.0, auto_fire=True)
            self.step(aimer, 1.05, auto_fire=True)
            self.assertEqual(calls, [])
            self.step(aimer, 1.09, auto_fire=True)
            self.assertEqual(calls, [[2, 4]])
            self.step(aimer, 1.10, auto_fire=True)
            self.step(aimer, 1.20, auto_fire=True)
            self.assertEqual(len(calls), 1)
            self.step(aimer, 1.40, auto_fire=True)
            self.assertEqual(calls, [[2, 4], [2, 4]])

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=-32768)
    def test_trigger_does_not_override_manual_left_hold(self, key, rect, send):
        aimer = MouseAimer()
        self.step(aimer, 1.0, auto_fire=True)
        self.step(aimer, 1.1, auto_fire=True)
        send.assert_not_called()

    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', return_value=-32768)
    def test_recoil_requires_hold_and_delay(self, key, rect):
        calls = []

        def send(count, pointer, size):
            event = pointer._obj.mi
            calls.append((event.dx, event.dy, event.dwFlags))
            return count

        aimer = MouseAimer()
        with patch('aim.send_input', side_effect=send):
            self.step(aimer, 1.0, players=[], recoil_rate=60)
            self.step(aimer, 1.05, players=[], recoil_rate=60)
            self.assertEqual(calls, [])
            self.step(aimer, 1.15, players=[], recoil_rate=60)
        self.assertEqual(calls, [(0, 3, 1)])

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=None)
    @patch('aim.key_state', return_value=-32768)
    def test_no_recoil_or_shot_when_game_background(self, key, rect, send):
        aimer = MouseAimer()
        self.step(aimer, 1.0, auto_fire=True, recoil_rate=60)
        self.step(aimer, 1.2, auto_fire=True, recoil_rate=60)
        send.assert_not_called()

    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', side_effect=lambda key: -32768 if key == 0x02 else 0)
    def test_partial_click_releases_button_and_errors(self, key, rect):
        calls = []

        def send(count, events, size):
            calls.append(events[0].mi.dwFlags if count == 2 else events._obj.mi.dwFlags)
            return 1

        with patch('aim.send_input', side_effect=send):
            with self.assertRaises(OSError):
                MouseAimer().click(123)
        self.assertEqual(calls, [2, 4])

    @patch('aim.send_input')
    @patch('aim.game_rect', return_value=(0, 0, 1000, 600))
    @patch('aim.key_state', side_effect=lambda key: -32768 if key == 0x02 else 0)
    def test_off_center_target_does_not_shoot(self, key, rect, send):
        aimer = MouseAimer()
        players = [{'id': 1, 'health': 100, 'eye': (5, 100, 36)}]
        send.return_value = 1
        self.step(aimer, 1.0, players=players, auto_fire=True)
        self.step(aimer, 1.2, players=players, auto_fire=True)
        self.assertTrue(all(call.args[0] == 1 for call in send.call_args_list))


if __name__ == '__main__':
    unittest.main()
