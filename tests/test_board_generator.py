from __future__ import annotations

import unittest

from pacman.board_generator import (
    PLAYER_CELL,
    _bfs_board,
    _dead_end_count,
    _junction_count,
    generate_board,
    is_playable,
)
from pacman.constants import BOARD_COLS, BOARD_ROWS, GATE_TILE, POWER_DOT_TILE, VOID_TILE, WALL_TILE


def _route_kind(tile: int) -> str:
    if tile == GATE_TILE:
        return "gate"
    if tile == VOID_TILE:
        return "void"
    if tile >= WALL_TILE:
        return "wall"
    return "route"


class BoardGeneratorTests(unittest.TestCase):
    def test_generated_boards_are_classic_symmetric_and_open(self) -> None:
        for seed in range(20):
            with self.subTest(seed=seed):
                board = generate_board(seed=seed)
                reachable, _ = _bfs_board(board, PLAYER_CELL)

                self.assertTrue(is_playable(board))
                self.assertEqual(_dead_end_count(board, reachable), 0)
                self.assertGreaterEqual(_junction_count(board, reachable), 28)
                self.assertGreaterEqual(sum(tile == VOID_TILE for row in board for tile in row), 24)
                self.assertEqual(sum(tile == POWER_DOT_TILE for row in board for tile in row), 4)

                for row in range(BOARD_ROWS):
                    for col in range(BOARD_COLS // 2):
                        mirror_col = BOARD_COLS - 1 - col
                        self.assertEqual(_route_kind(board[row][col]), _route_kind(board[row][mirror_col]))


if __name__ == "__main__":
    unittest.main()
