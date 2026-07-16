# tests/test_p0_polish.py
"""P0 UX/control/feedback polish — exercises shipped pure logic & entry paths."""
import os
import sys
import unittest

# Headless-friendly before pygame import
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame
pygame.init()

from settings import (
    CARD_DRAW_THRESHOLDS, NORMAL_DROP_INTERVAL, SOFT_DROP_INTERVAL,
    GRID_WIDTH, GRID_HEIGHT, CHAR_KEQING, global_state,
)
from game_logic import (
    Game,
    remaining_score_to_next_card,
    get_effective_drop_interval,
    get_top_filled_row,
    danger_level_from_top_row,
)


class TestRemainingScoreToNextCard(unittest.TestCase):
    def test_first_threshold(self):
        self.assertEqual(remaining_score_to_next_card(0, 0), CARD_DRAW_THRESHOLDS[0])
        self.assertEqual(remaining_score_to_next_card(400, 0), CARD_DRAW_THRESHOLDS[0] - 400)

    def test_mid_threshold(self):
        # after first draw, index=1, need 2000 - score
        self.assertEqual(remaining_score_to_next_card(1500, 1), CARD_DRAW_THRESHOLDS[1] - 1500)

    def test_clamped_non_negative(self):
        self.assertEqual(remaining_score_to_next_card(99999, 0), 0)

    def test_exhausted_returns_none(self):
        self.assertIsNone(
            remaining_score_to_next_card(0, len(CARD_DRAW_THRESHOLDS)))

    def test_game_wrapper(self):
        g = Game()
        g.score = 250
        g.card_draw_index = 0
        self.assertEqual(g.remaining_to_next_card(), CARD_DRAW_THRESHOLDS[0] - 250)


class TestSoftDropInterval(unittest.TestCase):
    def test_normal_when_not_held(self):
        self.assertEqual(
            get_effective_drop_interval(False, False),
            NORMAL_DROP_INTERVAL)

    def test_soft_when_held(self):
        self.assertEqual(
            get_effective_drop_interval(True, False),
            SOFT_DROP_INTERVAL)

    def test_disable_down_blocks_soft(self):
        self.assertEqual(
            get_effective_drop_interval(True, True),
            NORMAL_DROP_INTERVAL)

    def test_soft_faster_than_normal(self):
        soft = get_effective_drop_interval(True, False)
        normal = get_effective_drop_interval(False, False)
        self.assertLess(soft, normal)


class TestHardDrop(unittest.TestCase):
    def test_hard_drop_places_at_bottom(self):
        g = Game()
        g.start_new_game()
        # Ensure clean columns under spawn
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                g.grid[y][x] = None
        g.current_blocks = [
            {"color": "blue", "x": 2, "y": 0},
            {"color": "green", "x": 2, "y": 1},
        ]
        g.hard_drop()
        # Pair stacked: bottom at y=11, upper at y=10 (spawn may refill current_blocks)
        self.assertEqual(g.grid[11][2], "green")
        self.assertEqual(g.grid[10][2], "blue")
        # Dropped pair must no longer be the falling piece at top of same column
        for b in g.current_blocks:
            self.assertFalse(b["y"] >= 10 and b["x"] == 2 and b["color"] in ("blue", "green")
                             and g.grid[b["y"]][b["x"]] is None)

    def test_hard_drop_lands_on_stack(self):
        g = Game()
        g.start_new_game()
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                g.grid[y][x] = None
        g.grid[11][3] = "stone"
        g.current_blocks = [
            {"color": "red", "x": 3, "y": 0},
            {"color": "red", "x": 3, "y": 1},
        ]
        g.hard_drop()
        self.assertEqual(g.grid[10][3], "red")
        self.assertEqual(g.grid[9][3], "red")
        self.assertEqual(g.grid[11][3], "stone")


class TestGameOverRestart(unittest.TestCase):
    def test_restart_resets_score_and_cards_keeps_character(self):
        global_state["current_character"] = CHAR_KEQING
        g = Game()
        g.start_new_game()
        self.assertEqual(g.skill_manager.character_name, CHAR_KEQING)

        g.score = 12345
        g.owned_cards = ["0101", "0104"]
        g.card_draw_index = 3
        g.game_over_flag = True
        g.running = True

        g.start_new_game()

        self.assertEqual(g.score, 0)
        self.assertEqual(g.owned_cards, [])
        self.assertEqual(g.card_draw_index, 0)
        self.assertFalse(g.game_over_flag)
        self.assertTrue(g.running)
        self.assertEqual(g.skill_manager.character_name, CHAR_KEQING)
        self.assertEqual(global_state["current_character"], CHAR_KEQING)


class TestDangerLevel(unittest.TestCase):
    def test_empty_board_safe(self):
        grid = [[None] * GRID_WIDTH for _ in range(GRID_HEIGHT)]
        top = get_top_filled_row(grid)
        self.assertEqual(top, GRID_HEIGHT)
        self.assertEqual(danger_level_from_top_row(top), 0.0)

    def test_top_row_max_danger(self):
        grid = [[None] * GRID_WIDTH for _ in range(GRID_HEIGHT)]
        grid[0][0] = "blue"
        top = get_top_filled_row(grid)
        self.assertEqual(top, 0)
        self.assertGreaterEqual(danger_level_from_top_row(top), 0.99)

    def test_low_stack_safe(self):
        grid = [[None] * GRID_WIDTH for _ in range(GRID_HEIGHT)]
        grid[11][0] = "blue"
        self.assertEqual(danger_level_from_top_row(get_top_filled_row(grid)), 0.0)


class TestVfxScaleCache(unittest.TestCase):
    def test_explosion_frame_cached_by_size(self):
        from resources import R
        R.load_assets()
        # Even with empty frames list, API returns consistent cached None
        a = R.get_explosion_frame_scaled("blue", 0, 64)
        b = R.get_explosion_frame_scaled("blue", 0, 64)
        self.assertIs(a, b)
        # Different size keys diverge
        c = R.get_explosion_frame_scaled("blue", 0, 48)
        if a is not None and c is not None:
            self.assertIsNot(a, c)

    def test_named_scale_cache_same_key(self):
        from resources import R
        R.load_assets()
        a = R.get_scaled_named("meteorite", 100, 100)
        b = R.get_scaled_named("meteorite", 100, 100)
        if a is not None:
            self.assertIs(a, b)


class TestImportMainModules(unittest.TestCase):
    def test_import_core_modules(self):
        import importlib
        for name in ("settings", "game_logic", "effects", "resources",
                     "renderer", "cards", "skill", "ui"):
            importlib.import_module(name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
