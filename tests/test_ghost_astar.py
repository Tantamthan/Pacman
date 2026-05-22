from __future__ import annotations

import copy
import unittest

import pygame

from pacman.board import boards
from pacman.constants import (
    BLINKY_ID,
    BLINKY_START,
    BLINKY_SCATTER_TARGET,
    BOX_EXIT_TARGET,
    CELL_H,
    CELL_W,
    CLYDE_ID,
    CLYDE_START,
    CLYDE_SCATTER_TARGET,
    GATE_TILE,
    GHOST_BOX_MAX_X,
    GHOST_BOX_MAX_Y,
    GHOST_BOX_MIN_X,
    GHOST_BOX_MIN_Y,
    GHOST_CENTER_OFFSET,
    GHOST_NORMAL_SPEED,
    GHOST_TUNNEL_LEFT,
    INKY_ID,
    INKY_START,
    INKY_SCATTER_TARGET,
    PINKY_ID,
    PINKY_START,
    PINKY_SCATTER_TARGET,
    PLAYER_CENTER_OFFSET_X,
    PLAYER_CENTER_OFFSET_Y,
    PLAYER_UNSTICK_FRAMES,
    DOWN,
    RIGHT,
    TURN_WINDOW_MIN,
    TURN_WINDOW_MAX,
    UP,
    WALL_TILE,
)
from pacman.ghost import Ghost, _can_detect_player, _patrol_cells, _patrol_target, _reachable_patrol_cells, get_targets
from pacman.main import move_ghosts
from pacman.player import Player


def make_ghost_at_cell(
    row: int,
    col: int,
    *,
    dead: bool = False,
    in_box: bool = False,
    ghost_id: int = BLINKY_ID,
) -> Ghost:
    x_pos = col * CELL_W + CELL_W // 2 - GHOST_CENTER_OFFSET
    y_pos = row * CELL_H + CELL_H // 2 - GHOST_CENTER_OFFSET
    return Ghost(
        x_pos,
        y_pos,
        (0, 0),
        GHOST_NORMAL_SPEED,
        pygame.Surface((1, 1)),
        RIGHT,
        dead,
        in_box,
        ghost_id,
    )


def put_player_at_cell(player: Player, row: int, col: int) -> None:
    player.x_pos = col * CELL_W + CELL_W // 2 - PLAYER_CENTER_OFFSET_X
    player.y_pos = row * CELL_H + CELL_H // 2 - PLAYER_CENTER_OFFSET_Y


class GhostAStarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.level = copy.deepcopy(boards)

    def test_astar_returns_empty_when_start_is_goal(self) -> None:
        ghost = make_ghost_at_cell(2, 2)

        self.assertEqual(ghost._astar(self.level, (2, 2), (2, 2)), [])

    def test_astar_finds_path_without_crossing_walls(self) -> None:
        ghost = make_ghost_at_cell(2, 2)

        path = ghost._astar(self.level, (2, 2), (6, 7))

        self.assertTrue(path)
        self.assertEqual(path[-1], (6, 7))
        self.assertTrue(all(self.level[row][col] < WALL_TILE for row, col in path))

    def test_gate_is_blocked_until_ghost_is_in_box_or_dead(self) -> None:
        ghost = make_ghost_at_cell(2, 2)

        self.assertEqual(ghost._astar(self.level, (14, 14), (12, 14)), [])

        ghost.in_box = True
        in_box_path = ghost._astar(self.level, (14, 14), (12, 14))
        self.assertIn((13, 14), in_box_path)
        self.assertEqual(self.level[13][14], GATE_TILE)

        ghost.in_box = False
        ghost.dead = True
        dead_path = ghost._astar(self.level, (14, 14), (12, 14))
        self.assertIn((13, 14), dead_path)

    def test_target_outside_board_uses_nearest_passable_cell(self) -> None:
        ghost = make_ghost_at_cell(2, 2)

        target = ghost._nearest_passable_cell(self.level, ghost._cell_from_point((900, 900)))

        self.assertTrue(self.level[target[0]][target[1]] < WALL_TILE)

    def test_move_astar_moves_inside_same_target_cell(self) -> None:
        ghost = make_ghost_at_cell(24, 15)
        start = (ghost.x_pos, ghost.y_pos)
        target = (ghost.center_x + 6, ghost.center_y)

        ghost.move_astar(self.level, target)

        self.assertGreater(ghost.x_pos, start[0])

    def test_move_astar_does_not_move_when_different_target_cell_is_unreachable(self) -> None:
        ghost = make_ghost_at_cell(15, 8)
        start = (ghost.x_pos, ghost.y_pos)
        target = (2 * CELL_W + CELL_W // 2, 18 * CELL_H + CELL_H // 2)

        ghost.move_astar(self.level, target)

        self.assertEqual((ghost.x_pos, ghost.y_pos), start)

    def test_mode_change_invalidates_stale_gate_path(self) -> None:
        ghost = make_ghost_at_cell(2, 2)
        target = (7 * CELL_W + CELL_W // 2, 6 * CELL_H + CELL_H // 2)

        ghost.move_astar(self.level, target)
        self.assertTrue(ghost._path)
        self.assertEqual(ghost._path_mode, (False, False))

        ghost.in_box = True
        ghost.move_astar(self.level, target)

        self.assertTrue(ghost._path)
        self.assertEqual(ghost._path_mode, (False, True))

    def test_gate_stays_open_while_exiting_chase_box(self) -> None:
        ghost = make_ghost_at_cell(14, 14)
        ghost.y_pos = GHOST_BOX_MIN_Y - 2
        ghost.in_box = False

        path = ghost._astar(self.level, (14, 14), (12, 14))

        self.assertIn((13, 14), path)

    def test_tunnel_wrap_clears_cached_path(self) -> None:
        ghost = make_ghost_at_cell(15, 1)
        ghost._path = [(15, 2)]
        ghost._path_target = (15, 2)
        ghost.x_pos = GHOST_TUNNEL_LEFT - 1

        ghost._wrap_tunnel()

        self.assertEqual(ghost._path, [])
        self.assertEqual(ghost._path_target, (-1, -1))

    def test_normal_targets_scatter_until_player_is_detected(self) -> None:
        player = Player()
        ghosts = [
            make_ghost_at_cell(2, 2, ghost_id=BLINKY_ID),
            make_ghost_at_cell(2, 3, ghost_id=INKY_ID),
            make_ghost_at_cell(2, 4, ghost_id=PINKY_ID),
            make_ghost_at_cell(2, 5, ghost_id=CLYDE_ID),
        ]

        targets = get_targets(player, ghosts, self.level)

        self.assertNotIn((player.x_pos, player.y_pos), targets)
        self.assertGreater(len(set(targets)), 1)
        for target in targets:
            target_cell = ghosts[0]._cell_from_point(target)
            self.assertTrue(self.level[target_cell[0]][target_cell[1]] < WALL_TILE)

    def test_normal_target_does_not_pull_outside_ghost_back_to_exit(self) -> None:
        player = Player()
        put_player_at_cell(player, 24, 15)
        ghost = make_ghost_at_cell(18, 12)
        ghost.x_pos = 343
        ghost.y_pos = 465
        ghost.in_box = False

        targets = get_targets(
            player,
            [ghost, make_ghost_at_cell(2, 3), make_ghost_at_cell(2, 4), make_ghost_at_cell(2, 5)],
            self.level,
        )

        self.assertNotEqual(targets[BLINKY_ID], BOX_EXIT_TARGET)
        self.assertTrue(ghost.is_patrolling)

    def test_patrol_target_advances_after_reaching_waypoint(self) -> None:
        ghost = make_ghost_at_cell(2, 2)
        patrol_cells = _patrol_cells(self.level, ghost)
        ghost._patrol_index = 0
        first_cell = patrol_cells[0]
        ghost.x_pos = first_cell[1] * CELL_W + CELL_W // 2 - GHOST_CENTER_OFFSET
        ghost.y_pos = first_cell[0] * CELL_H + CELL_H // 2 - GHOST_CENTER_OFFSET

        target = _patrol_target(self.level, ghost, BLINKY_SCATTER_TARGET)

        self.assertEqual(target, (patrol_cells[1][1] * CELL_W + CELL_W // 2, patrol_cells[1][0] * CELL_H + CELL_H // 2))
        self.assertEqual(ghost._patrol_index, 1)

    def test_patrol_cells_cover_multiple_board_regions(self) -> None:
        ghost = make_ghost_at_cell(2, 2)

        patrol_cells = _patrol_cells(self.level, ghost)
        rows = [row for row, _ in patrol_cells]
        cols = [col for _, col in patrol_cells]

        self.assertGreaterEqual(len(patrol_cells), 12)
        self.assertGreater(max(rows) - min(rows), 20)
        self.assertGreater(max(cols) - min(cols), 20)

    def test_patrol_target_skips_unreachable_waypoints(self) -> None:
        ghost = make_ghost_at_cell(15, 8)
        patrol_cells = _patrol_cells(self.level, ghost)

        target = _patrol_target(self.level, ghost, BLINKY_SCATTER_TARGET)
        target_cell = ghost._cell_from_point(target)

        self.assertTrue(ghost._astar(self.level, (15, 8), target_cell))
        self.assertNotIn((18, 2), patrol_cells)

    def test_patrol_cells_are_reachable_from_current_component(self) -> None:
        ghost = make_ghost_at_cell(15, 8)

        reachable = _reachable_patrol_cells(self.level, ghost)
        patrol_cells = _patrol_cells(self.level, ghost)

        self.assertTrue(patrol_cells)
        self.assertTrue(set(patrol_cells).issubset(reachable))

    def test_patrolling_inky_and_clyde_use_astar_paths(self) -> None:
        ghosts = [
            make_ghost_at_cell(2, 2, ghost_id=BLINKY_ID),
            make_ghost_at_cell(2, 3, ghost_id=INKY_ID),
            make_ghost_at_cell(2, 4, ghost_id=PINKY_ID),
            make_ghost_at_cell(2, 5, ghost_id=CLYDE_ID),
        ]
        for ghost in ghosts:
            ghost.target = (13 * CELL_W + CELL_W // 2, 6 * CELL_H + CELL_H // 2)
        ghosts[INKY_ID].is_patrolling = True
        ghosts[CLYDE_ID].is_patrolling = True

        move_ghosts(ghosts, self.level)

        self.assertTrue(ghosts[INKY_ID]._path)
        self.assertTrue(ghosts[CLYDE_ID]._path)

    def test_all_ghost_start_positions_are_inside_ghost_house(self) -> None:
        for x_pos, y_pos, _ in (BLINKY_START, INKY_START, PINKY_START, CLYDE_START):
            center_x = x_pos + GHOST_CENTER_OFFSET
            center_y = y_pos + GHOST_CENTER_OFFSET
            row = center_y // CELL_H
            col = center_x // CELL_W

            self.assertGreater(x_pos, GHOST_BOX_MIN_X)
            self.assertLess(x_pos, GHOST_BOX_MAX_X)
            self.assertGreater(y_pos, GHOST_BOX_MIN_Y)
            self.assertLess(y_pos, GHOST_BOX_MAX_Y)
            self.assertLess(self.level[row][col], WALL_TILE)

    def test_in_box_uses_ghost_center_not_sprite_top_left(self) -> None:
        ghost = make_ghost_at_cell(18, 12)
        ghost.x_pos = GHOST_BOX_MIN_X + 1
        ghost.y_pos = GHOST_BOX_MAX_Y - 15

        ghost.check_collisions(self.level)

        self.assertFalse(ghost.in_box)

    def test_detection_uses_clear_line_of_sight(self) -> None:
        player = Player()
        put_player_at_cell(player, 6, 13)
        ghost = make_ghost_at_cell(6, 2)

        self.assertTrue(_can_detect_player(self.level, player, ghost))

    def test_walls_block_line_of_sight_detection(self) -> None:
        player = Player()
        put_player_at_cell(player, 2, 17)
        ghost = make_ghost_at_cell(2, 2)

        self.assertFalse(_can_detect_player(self.level, player, ghost))

    def test_player_snaps_to_lane_center_when_turning(self) -> None:
        player = Player()
        put_player_at_cell(player, 24, 15)
        player.y_pos += 5
        player.direction = UP

        player.set_direction(RIGHT)

        self.assertEqual(player.center_y % CELL_H, CELL_H // 2)
        self.assertEqual(player.direction, RIGHT)

    def test_player_turn_window_is_forgiving_near_lane_center(self) -> None:
        player = Player()
        put_player_at_cell(player, 24, 15)
        player.direction = RIGHT
        player.y_pos += TURN_WINDOW_MAX - CELL_H // 2

        player.check_collisions(self.level)

        self.assertTrue(player.turns_allowed[RIGHT])
        self.assertGreaterEqual(player.center_y % CELL_H, TURN_WINDOW_MIN)
        self.assertLessEqual(player.center_y % CELL_H, TURN_WINDOW_MAX)

    def test_player_auto_unsticks_after_holding_blocked_direction(self) -> None:
        player = Player()
        put_player_at_cell(player, 24, 16)
        player.direction = DOWN
        player.direction_command = DOWN

        for _ in range(PLAYER_UNSTICK_FRAMES):
            player.check_collisions(self.level)
            player.move(self.level)

        self.assertEqual(player.direction, UP)
        self.assertLess(player.y_pos, 24 * CELL_H + CELL_H // 2 - PLAYER_CENTER_OFFSET_Y)


if __name__ == "__main__":
    unittest.main()
