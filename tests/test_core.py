import ctypes as C
import json
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from geometry import project, look_endpoint, player_box
from offsets import validate
from winreader import Reader, PROCESSENTRY32W, MODULEENTRY32W


class GeometryTests(unittest.TestCase):
    matrix = (1, 0, 0, 0, 0, 0, 1, -36, 0, 0, 1, 0, 0, 1, 0, 0)

    def test_center_and_screen_edges(self):
        self.assertEqual(project((0, 100, 36), self.matrix, 1000, 600), (500, 300))
        self.assertEqual(project((100, 100, 36), self.matrix, 1000, 600), (1000, 300))

    def test_behind_camera_and_nan(self):
        self.assertIsNone(project((0, -10, 0), self.matrix, 1000, 600))
        self.assertIsNone(project((math.nan, 10, 0), self.matrix, 1000, 600))

    def test_yaw_axes_and_downward_pitch(self):
        self.assertEqual(look_endpoint((0, 0, 0), 0, 0, 100), (100, 0, 0))
        point = look_endpoint((0, 0, 0), 0, 90, 100)
        self.assertAlmostEqual(point[0], 0)
        self.assertAlmostEqual(point[1], 100)
        self.assertAlmostEqual(look_endpoint((0, 0, 0), 90, 0, 100)[2], -100)

    def test_box_head_above_feet(self):
        left, top, right, bottom = player_box((0, 100, 0), (0, 100, 64), self.matrix, 1000, 600)
        self.assertLess(left, right)
        self.assertLess(top, bottom)
        self.assertAlmostEqual((left + right) / 2, 500)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.offsets = json.loads((Path(__file__).parents[1] / 'offsets.json').read_text())
        self.memory = {}
        memory = self.memory

        class FakeReader(Reader):
            def __init__(self, offsets):
                self.offsets = offsets
                self.base = 0x100000
                self.handle = 1
                self.stride = None

            def read(self, address, length):
                try:
                    return bytes(memory[address + i] for i in range(length))
                except KeyError:
                    raise OSError('missing test memory')

        self.reader = FakeReader(self.offsets)

    def put(self, address, format, *values):
        self.put_bytes(address, struct.pack(format, *values))

    def put_bytes(self, address, data):
        self.memory.update({address + i: value for i, value in enumerate(data)})

    def test_entity_chunk_resolution_and_handle_mask(self):
        self.put(0x200010 + 8, '<Q', 0x300000)
        self.put(0x300000 + 0x70 * 3, '<Q', 0x400000)
        self.assertEqual(self.reader.entity(0x200000, 0x8000 | 515, 0x70), 0x400000)

    def test_frame_filters_team_and_reads_enemy_angles(self):
        g, f = self.offsets['globals'], self.offsets['fields']
        self.put(self.reader.base + g['dwViewMatrix'], '<16f', *GeometryTests.matrix)
        self.put(self.reader.base + g['dwEntityList'], '<Q', 0x200000)
        self.put(self.reader.base + g['dwLocalPlayerPawn'], '<Q', 0x400000)
        self.put(0x200010, '<Q', 0x300000)
        self.put(0x400000 + f['team'], '<B', 2)
        for index, pawn, team in ((1, 0x400000, 2), (2, 0x500000, 3), (3, 0x600000, 2)):
            controller = 0x700000 + index * 0x10000
            self.put(0x300000 + 0x78 * index, '<Q', controller)
            self.put(controller + f['pawn_handle'], '<I', 100 + index)
            self.put(0x300000 + 0x78 * (100 + index), '<Q', pawn)
            self.put(pawn + f['health'], '<i', 85)
            self.put(pawn + f['team'], '<B', team)
            self.put(pawn + f['life_state'], '<B', 0)
            self.put(pawn + f['scene_node'], '<Q', 0x900000)
            self.put(0x900000 + f['dormant'], '<B', 0)
            self.put(0x900000 + f['origin'], '<3f', 10, 100, 0)
            self.put(pawn + f['view_offset'], '<3f', 0, 0, 64)
            self.put(pawn + f['eye_angles'], '<3f', 15, 90, 0)
            self.put_bytes(controller + f['name'], b'Enemy\0' + bytes(122))

        def alive(handle, pointer):
            pointer._obj.value = 259
            return True

        with patch('winreader.exit_code', side_effect=alive):
            matrix, players = self.reader.frame()
        self.assertEqual(self.reader.stride, 0x78)
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]['angles'], (15, 90))
        self.assertEqual(players[0]['eye'], (10, 100, 64))
        self.assertEqual(players[0]['name'], 'Enemy')

    def test_win32_structure_sizes(self):
        self.assertEqual(C.sizeof(PROCESSENTRY32W), 568)
        self.assertEqual(C.sizeof(MODULEENTRY32W), 1080)

    def test_offset_validation(self):
        validate(self.offsets)
        self.offsets['fields']['health'] = 'not an integer'
        with self.assertRaises(ValueError):
            validate(self.offsets)


if __name__ == '__main__':
    unittest.main()
