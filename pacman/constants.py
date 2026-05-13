"""Shared constants for the Pac-Man game."""

from __future__ import annotations

import math

WIDTH: int = 900
HEIGHT: int = 950
FPS: int = 60
UI_HEIGHT: int = 50

BOARD_ROWS: int = 33
BOARD_COLS: int = 30
CELL_H: int = (HEIGHT - UI_HEIGHT) // BOARD_ROWS
CELL_W: int = WIDTH // BOARD_COLS

PI: float = math.pi
ASSET_DIR: str = __file__.replace("\\", "/").rsplit("/", 2)[0] + "/assets"

BLACK: str = "black"
WHITE: str = "white"
BLUE: str = "blue"
DARK_GRAY: str = "dark gray"
RED: str = "red"
GREEN: str = "green"

EMPTY_TILE: int = 0
DOT_TILE: int = 1
POWER_DOT_TILE: int = 2
WALL_TILE: int = 3
VERTICAL_WALL_TILE: int = 3
HORIZONTAL_WALL_TILE: int = 4
TOP_RIGHT_WALL_TILE: int = 5
TOP_LEFT_WALL_TILE: int = 6
BOTTOM_LEFT_WALL_TILE: int = 7
BOTTOM_RIGHT_WALL_TILE: int = 8
GATE_TILE: int = 9

RIGHT: int = 0
LEFT: int = 1
UP: int = 2
DOWN: int = 3
DIRECTIONS: tuple[int, int, int, int] = (RIGHT, LEFT, UP, DOWN)

PLAYER_START_X: int = 450
PLAYER_START_Y: int = 637
PLAYER_START_DIRECTION: int = RIGHT
PLAYER_SPEED: int = 2
PLAYER_LIVES: int = 3
PLAYER_CENTER_OFFSET_X: int = 23
PLAYER_CENTER_OFFSET_Y: int = 24
PLAYER_COLLISION_RADIUS: int = 20
PLAYER_COLLISION_WIDTH: int = 2
PLAYER_TURN_FUDGE: int = 15
PLAYER_UNSTICK_FRAMES: int = 10
PLAYER_DOT_MIN_X: int = 0
PLAYER_DOT_MAX_X: int = 870
PLAYER_TUNNEL_RIGHT: int = 900
PLAYER_TUNNEL_LEFT: int = -50
PLAYER_WRAP_LEFT: int = -47
PLAYER_WRAP_RIGHT: int = 897

GHOST_CENTER_OFFSET: int = 22
GHOST_RECT_OFFSET: int = 18
GHOST_RECT_SIZE: int = 36
GHOST_TURN_FUDGE: int = 15
GHOST_TUNNEL_LEFT: int = -30
GHOST_TUNNEL_RIGHT: int = 900
GHOST_WRAP_RIGHT: int = 900
GHOST_NORMAL_SPEED: int = 2
GHOST_POWER_SPEED: int = 1
GHOST_DEAD_SPEED: int = 4

BLINKY_START: tuple[int, int, int] = (410, 388, UP)
INKY_START: tuple[int, int, int] = (470, 388, UP)
PINKY_START: tuple[int, int, int] = (410, 423, UP)
CLYDE_START: tuple[int, int, int] = (470, 423, UP)

BLINKY_ID: int = 0
INKY_ID: int = 1
PINKY_ID: int = 2
CLYDE_ID: int = 3
GHOST_COUNT: int = 4

GHOST_BOX_MIN_X: int = 350
GHOST_BOX_MAX_X: int = 550
GHOST_BOX_MIN_Y: int = 370
GHOST_BOX_MAX_Y: int = 480
CHASE_BOX_MIN_X: int = 340
CHASE_BOX_MAX_X: int = 560
CHASE_BOX_MIN_Y: int = 340
CHASE_BOX_MAX_Y: int = 500
RETURN_TARGET: tuple[int, int] = (380, 400)
BOX_EXIT_TARGET: tuple[int, int] = (400, 100)
CLYDE_POWER_TARGET: tuple[int, int] = (450, 450)
RUNAWAY_SPLIT: int = 450
RUNAWAY_MIN: int = 0
RUNAWAY_MAX: int = 900
GHOST_DETECTION_RADIUS_CELLS: int = 6
BLINKY_SCATTER_TARGET: tuple[int, int] = (WIDTH - CELL_W * 3, CELL_H * 2)
INKY_SCATTER_TARGET: tuple[int, int] = (WIDTH - CELL_W * 3, HEIGHT - UI_HEIGHT - CELL_H * 3)
PINKY_SCATTER_TARGET: tuple[int, int] = (CELL_W * 2, CELL_H * 2)
CLYDE_SCATTER_TARGET: tuple[int, int] = (CELL_W * 2, HEIGHT - UI_HEIGHT - CELL_H * 3)

PLAYER_IMAGE_SIZE: tuple[int, int] = (45, 45)
PLAYER_ANIMATION_FRAMES: int = 4
GHOST_IMAGE_SIZE: tuple[int, int] = (45, 45)
LIFE_IMAGE_SIZE: tuple[int, int] = (30, 30)
SCORE_POS: tuple[int, int] = (10, 920)
POWERUP_INDICATOR_POS: tuple[int, int] = (140, 930)
POWERUP_INDICATOR_RADIUS: int = 15
LIFE_START_X: int = 650
LIFE_Y: int = 915
LIFE_SPACING: int = 40
MESSAGE_OUTER_RECT: tuple[int, int, int, int] = (50, 200, 800, 300)
MESSAGE_INNER_RECT: tuple[int, int, int, int] = (70, 220, 760, 260)
MESSAGE_RADIUS: int = 10
MESSAGE_POS: tuple[int, int] = (100, 300)

ANIMATION_MAX: int = 19
FLICKER_THRESHOLD: int = 3
FRAME_IMAGE_DIVISOR: int = 5
POWERUP_DURATION: int = 600
STARTUP_DELAY: int = 180

DOT_RADIUS: int = 4
POWER_DOT_RADIUS: int = 10
WALL_WIDTH: int = 3
ARC_OFFSET_RATIO: float = 0.4
ARC_HALF_RATIO: float = 0.5
ARC_EDGE_ADJUST: int = 2
TURN_WINDOW_MIN: int = 9
TURN_WINDOW_MAX: int = 21
FONT_SIZE: int = 20
GHOST_EAT_SCORE_BASE: int = 2
GHOST_EAT_SCORE_UNIT: int = 100
