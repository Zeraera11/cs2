import ast
import math
from pathlib import Path
import unittest

from engine import Target, Trainer, smooth_axis


class TrainerTests(unittest.TestCase):
    def arena(self):
        arena = Trainer(seed=42)
        arena.targets = [Target(0, 500, 356, 0, 0)]
        arena.base = [500, 325]
        return arena

    def test_head_hit_and_respawn(self):
        arena = self.arena()
        self.assertTrue(arena.fire())
        self.assertEqual((arena.shots, arena.hits, arena.headshots), (1, 1, 1))
        self.assertEqual(arena.targets[0].generation, 1)

    def test_body_and_miss(self):
        arena = self.arena()
        arena.base = [500, 360]
        self.assertTrue(arena.fire())
        self.assertEqual(arena.headshots, 0)
        arena.cooldown = 0
        arena.base = [0, 0]
        self.assertFalse(arena.fire())
        self.assertEqual(arena.shots, 2)
        self.assertEqual(arena.accuracy, 50)

    def test_cooldown(self):
        arena = self.arena()
        arena.fire()
        arena.fire()
        arena.step(0.1)
        arena.fire()
        self.assertEqual(arena.shots, 1)
        arena.step(0.06)
        arena.fire()
        self.assertEqual(arena.shots, 2)

    def test_autofire_requires_tracking_and_dwell(self):
        arena = self.arena()
        arena.step(0.2, tracking=False)
        self.assertEqual(arena.shots, 0)
        arena.step(0.04, tracking=True)
        self.assertEqual(arena.shots, 0)
        arena.step(0.04, tracking=True)
        self.assertEqual(arena.headshots, 1)

    def test_autofire_switch_and_release(self):
        arena = self.arena()
        arena.auto_fire = False
        arena.step(0.2, tracking=True)
        self.assertEqual(arena.shots, 0)
        arena.release()
        self.assertEqual(arena.dwell, 0)
        self.assertIsNone(arena.locked)

    def test_pause_and_round_end_block_shooting(self):
        arena = self.arena()
        arena.paused = True
        arena.step(0.2, tracking=True, firing=True)
        arena.fire()
        self.assertEqual((arena.shots, arena.elapsed), (0, 0))
        arena.paused = False
        arena.elapsed = arena.duration
        arena.step(0.2, tracking=True, firing=True)
        arena.fire()
        self.assertEqual(arena.shots, 0)

    def test_recoil_compensation_reduces_kick(self):
        corrected, uncorrected = self.arena(), self.arena()
        uncorrected.compensate = False
        corrected.fire()
        uncorrected.fire()
        self.assertLess(abs(corrected.recoil[1]), abs(uncorrected.recoil[1]))
        corrected.step(0.1)
        uncorrected.step(0.1)
        self.assertLess(abs(corrected.recoil[1]), abs(uncorrected.recoil[1]) * 0.1)

    def test_spring_converges_without_static_overshoot(self):
        position, velocity = 0, 0
        for _ in range(120):
            position, velocity = smooth_axis(position, velocity, 100, 1 / 120)
            self.assertLessEqual(position, 100)
        self.assertAlmostEqual(position, 100, places=3)

    def test_moving_target_feedforward_has_no_steady_lag(self):
        position, velocity, target = 0, 0, 100
        for _ in range(240):
            position, velocity = smooth_axis(position, velocity, target, 1 / 120, target_velocity=200)
            target += 200 / 120
        self.assertLess(abs(position - target), 0.01)

    def test_120_and_30_fps_match(self):
        fast, slow = self.arena(), self.arena()
        for arena in (fast, slow):
            arena.auto_fire = False
            arena.base = [450, 320]
            arena.targets[0].vx = 70
        for _ in range(120):
            fast.step(1 / 120, tracking=True)
        for _ in range(30):
            slow.step(1 / 30, tracking=True)
        self.assertAlmostEqual(fast.crosshair[0], slow.crosshair[0], places=6)

    def test_targets_bounce_and_resize(self):
        arena = self.arena()
        arena.targets[0].x = 954
        arena.targets[0].vx = 100
        arena.step(0.1)
        self.assertLess(arena.targets[0].vx, 0)
        arena.resize(600, 400)
        self.assertTrue(45 <= arena.targets[0].x <= 555)
        self.assertTrue(85 <= arena.targets[0].y <= 355)

    def test_no_os_input_process_or_network_modules(self):
        allowed = {'dataclasses', 'math', 'random', 'sys', 'time', 'tkinter', 'engine'}
        root = Path(__file__).parents[1]
        for name in ('engine.py', 'app.py'):
            tree = ast.parse((root / name).read_text('utf-8'))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module.split('.')[0])
            self.assertLessEqual(imported, allowed)


if __name__ == '__main__':
    unittest.main()
