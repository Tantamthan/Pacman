from __future__ import annotations

import heapq

import pygame

from pacman.constants import (
    BLINKY_ID,
    BLINKY_SCATTER_TARGET,
    BOARD_COLS,
    BOARD_ROWS,
    BOX_EXIT_TARGET,
    CELL_H,
    CELL_W,
    CHASE_BOX_MAX_X,
    CHASE_BOX_MAX_Y,
    CHASE_BOX_MIN_X,
    CHASE_BOX_MIN_Y,
    CLYDE_ID,
    CLYDE_POWER_TARGET,
    CLYDE_SCATTER_TARGET,
    DOWN,
    GATE_TILE,
    GHOST_DETECTION_RADIUS_CELLS,
    GHOST_BOX_MAX_X,
    GHOST_BOX_MAX_Y,
    GHOST_BOX_MIN_X,
    GHOST_BOX_MIN_Y,
    GHOST_CENTER_OFFSET,
    GHOST_RECT_OFFSET,
    GHOST_RECT_SIZE,
    GHOST_TUNNEL_LEFT,
    GHOST_TURN_FUDGE,
    GHOST_WRAP_RIGHT,
    INKY_ID,
    INKY_SCATTER_TARGET,
    LEFT,
    PINKY_ID,
    PINKY_SCATTER_TARGET,
    RETURN_TARGET,
    RIGHT,
    RUNAWAY_MAX,
    RUNAWAY_MIN,
    RUNAWAY_SPLIT,
    UP,
    WALL_TILE,
)
from pacman.player import Player

Level = list[list[int]]
Point = tuple[int, int]
Cell = tuple[int, int]
PATROL_ROW_STEP = 4
PATROL_COL_STEP = 5
PATROL_INDEX_OFFSET = 7
PATROL_REACHED_DISTANCE = 2


class Ghost:
    """Store ghost state and run the original pathing logic."""

    def __init__(
        self,
        x_coord: int,
        y_coord: int,
        target: Point,
        speed: int,
        img: pygame.Surface,
        direction: int,
        dead: bool,
        in_box: bool,
        ghost_id: int,
    ) -> None:
        """Create a ghost with position, image, and movement state."""
        self.x_pos = x_coord
        self.y_pos = y_coord
        self.target = target
        self.speed = speed
        self.img = img
        self.direction = direction
        self.dead = dead
        self.in_box = in_box
        self.id = ghost_id
        self.turns: list[bool] = [False, False, False, False]
        self.rect = pygame.Rect(0, 0, GHOST_RECT_SIZE, GHOST_RECT_SIZE)
        self._path: list[Cell] = []
        self._path_target: Cell = (-1, -1)
        self._path_mode: tuple[bool, bool] = (self.dead, self.in_box)
        self._patrol_index = self.id * PATROL_INDEX_OFFSET
        self.is_patrolling = False

    @property
    def center_x(self) -> int:
        """Return the horizontal collision center."""
        return self.x_pos + GHOST_CENTER_OFFSET

    @property
    def center_y(self) -> int:
        """Return the vertical collision center."""
        return self.y_pos + GHOST_CENTER_OFFSET

    def draw(
        self,
        screen: pygame.Surface,
        player: Player,
        spooked_img: pygame.Surface,
        dead_img: pygame.Surface,
    ) -> pygame.Rect:
        """Draw the ghost and return its collision rect."""
        if (not player.powerup and not self.dead) or (
            player.eaten_ghost[self.id] and player.powerup and not self.dead
        ):
            screen.blit(self.img, (self.x_pos, self.y_pos))
        elif player.powerup and not self.dead and not player.eaten_ghost[self.id]:
            screen.blit(spooked_img, (self.x_pos, self.y_pos))
        else:
            screen.blit(dead_img, (self.x_pos, self.y_pos))
        self.rect = pygame.Rect(
            (self.center_x - GHOST_RECT_OFFSET, self.center_y - GHOST_RECT_OFFSET),
            (GHOST_RECT_SIZE, GHOST_RECT_SIZE),
        )
        return self.rect

    def check_collisions(self, level: Level) -> tuple[list[bool], bool]:
        """Return legal turns and whether the ghost is in the box."""
        turns = [False, False, False, False]
        center_x = self.center_x
        center_y = self.center_y
        if 0 < center_x // CELL_W < BOARD_COLS - 1:
            if level[(center_y - GHOST_TURN_FUDGE) // CELL_H][center_x // CELL_W] == GATE_TILE:
                turns[UP] = True
            if self._is_open(level, center_y, center_x - GHOST_TURN_FUDGE):
                turns[LEFT] = True
            if self._is_open(level, center_y, center_x + GHOST_TURN_FUDGE):
                turns[RIGHT] = True
            if self._is_open(level, center_y + GHOST_TURN_FUDGE, center_x):
                turns[DOWN] = True
            if self._is_open(level, center_y - GHOST_TURN_FUDGE, center_x):
                turns[UP] = True

            if self.direction == UP or self.direction == DOWN:
                if 12 <= center_x % CELL_W <= 18:
                    if self._is_open(level, center_y + GHOST_TURN_FUDGE, center_x):
                        turns[DOWN] = True
                    if self._is_open(level, center_y - GHOST_TURN_FUDGE, center_x):
                        turns[UP] = True
                if 12 <= center_y % CELL_H <= 18:
                    if self._is_open(level, center_y, center_x - CELL_W):
                        turns[LEFT] = True
                    if self._is_open(level, center_y, center_x + CELL_W):
                        turns[RIGHT] = True

            if self.direction == RIGHT or self.direction == LEFT:
                if 12 <= center_x % CELL_W <= 18:
                    if self._is_open(level, center_y + GHOST_TURN_FUDGE, center_x):
                        turns[DOWN] = True
                    if self._is_open(level, center_y - GHOST_TURN_FUDGE, center_x):
                        turns[UP] = True
                if 12 <= center_y % CELL_H <= 18:
                    if self._is_open(level, center_y, center_x - GHOST_TURN_FUDGE):
                        turns[LEFT] = True
                    if self._is_open(level, center_y, center_x + GHOST_TURN_FUDGE):
                        turns[RIGHT] = True
        else:
            turns[RIGHT] = True
            turns[LEFT] = True

        self.in_box = GHOST_BOX_MIN_X < center_x < GHOST_BOX_MAX_X and GHOST_BOX_MIN_Y < center_y < GHOST_BOX_MAX_Y
        self.turns = turns
        return self.turns, self.in_box

    def _is_open(self, level: Level, pixel_y: int, pixel_x: int) -> bool:
        """Return whether a pixel coordinate is passable for this ghost."""
        tile = level[pixel_y // CELL_H][pixel_x // CELL_W]
        return tile < WALL_TILE or (tile == GATE_TILE and self._can_use_gate())

    def reset(self, x_coord: int, y_coord: int, direction: int) -> None:
        """Reset position and temporary ghost state."""
        self.x_pos = x_coord
        self.y_pos = y_coord
        self.direction = direction
        self.dead = False
        self.in_box = False
        self.turns = [False, False, False, False]
        self._patrol_index = self.id * PATROL_INDEX_OFFSET
        self.is_patrolling = False
        self._clear_path()

    def move_clyde(self) -> tuple[int, int, int]:
        """Move using Clyde's original pursuit behavior."""
        if self.direction == RIGHT:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.x_pos += self.speed
            elif not self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                if self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                else:
                    self.x_pos += self.speed
        elif self.direction == LEFT:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.direction = DOWN
            elif self.target[0] < self.x_pos and self.turns[LEFT]:
                self.x_pos -= self.speed
            elif not self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                if self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                else:
                    self.x_pos -= self.speed
        elif self.direction == UP:
            if self.target[0] < self.x_pos and self.turns[LEFT]:
                self.direction = LEFT
                self.x_pos -= self.speed
            elif self.target[1] < self.y_pos and self.turns[UP]:
                self.direction = UP
                self.y_pos -= self.speed
            elif not self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                else:
                    self.y_pos -= self.speed
        elif self.direction == DOWN:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.y_pos += self.speed
            elif not self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                else:
                    self.y_pos += self.speed
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    def move_blinky(self) -> tuple[int, int, int]:
        """Move using Blinky's original pursuit behavior."""
        if self.direction == RIGHT:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.x_pos += self.speed
            elif not self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[RIGHT]:
                self.x_pos += self.speed
        elif self.direction == LEFT:
            if self.target[0] < self.x_pos and self.turns[LEFT]:
                self.x_pos -= self.speed
            elif not self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[LEFT]:
                self.x_pos -= self.speed
        elif self.direction == UP:
            if self.target[1] < self.y_pos and self.turns[UP]:
                self.direction = UP
                self.y_pos -= self.speed
            elif not self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[UP]:
                self.y_pos -= self.speed
        elif self.direction == DOWN:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.y_pos += self.speed
            elif not self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[DOWN]:
                self.y_pos += self.speed
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    def move_inky(self) -> tuple[int, int, int]:
        """Move using Inky's original pursuit behavior."""
        return self._move_inky_like()

    def move_pinky(self) -> tuple[int, int, int]:
        """Move using Pinky's original pursuit behavior."""
        return self._move_pinky_like()

    def _move_inky_like(self) -> tuple[int, int, int]:
        """Run the original Inky branch logic."""
        if self.direction == RIGHT:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.x_pos += self.speed
            elif not self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                if self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                else:
                    self.x_pos += self.speed
        elif self.direction == LEFT:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.direction = DOWN
            elif self.target[0] < self.x_pos and self.turns[LEFT]:
                self.x_pos -= self.speed
            elif not self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                if self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                else:
                    self.x_pos -= self.speed
        elif self.direction == UP:
            if self.target[1] < self.y_pos and self.turns[UP]:
                self.direction = UP
                self.y_pos -= self.speed
            elif not self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[UP]:
                self.y_pos -= self.speed
        elif self.direction == DOWN:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.y_pos += self.speed
            elif not self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[DOWN]:
                self.y_pos += self.speed
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    def _move_pinky_like(self) -> tuple[int, int, int]:
        """Run the original Pinky branch logic."""
        if self.direction == RIGHT:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.x_pos += self.speed
            elif not self.turns[RIGHT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
            elif self.turns[RIGHT]:
                self.x_pos += self.speed
        elif self.direction == LEFT:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.direction = DOWN
            elif self.target[0] < self.x_pos and self.turns[LEFT]:
                self.x_pos -= self.speed
            elif not self.turns[LEFT]:
                if self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[LEFT]:
                self.x_pos -= self.speed
        elif self.direction == UP:
            if self.target[0] < self.x_pos and self.turns[LEFT]:
                self.direction = LEFT
                self.x_pos -= self.speed
            elif self.target[1] < self.y_pos and self.turns[UP]:
                self.direction = UP
                self.y_pos -= self.speed
            elif not self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] > self.y_pos and self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[DOWN]:
                    self.direction = DOWN
                    self.y_pos += self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[UP]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                else:
                    self.y_pos -= self.speed
        elif self.direction == DOWN:
            if self.target[1] > self.y_pos and self.turns[DOWN]:
                self.y_pos += self.speed
            elif not self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.target[1] < self.y_pos and self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[UP]:
                    self.direction = UP
                    self.y_pos -= self.speed
                elif self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                elif self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
            elif self.turns[DOWN]:
                if self.target[0] > self.x_pos and self.turns[RIGHT]:
                    self.direction = RIGHT
                    self.x_pos += self.speed
                elif self.target[0] < self.x_pos and self.turns[LEFT]:
                    self.direction = LEFT
                    self.x_pos -= self.speed
                else:
                    self.y_pos += self.speed
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    def _wrap_tunnel(self) -> None:
        """Apply the original left-side ghost tunnel wrap."""
        if self.x_pos < GHOST_TUNNEL_LEFT:
            self.x_pos = GHOST_WRAP_RIGHT
            self._clear_path()

    def move_astar(self, level: Level, target: Point) -> None:
        """Move one frame toward target using a cached A* path."""
        target_cell = self._nearest_passable_cell(level, self._cell_from_point(target))
        curr_cell = self._cell_from_point((self.center_x, self.center_y))
        mode = (self.dead, self.in_box)

        if mode != self._path_mode or target_cell != self._path_target:
            self._path = self._astar(level, curr_cell, target_cell)
            self._path_target = target_cell
            self._path_mode = mode
        else:
            self._trim_path_to_current_cell(curr_cell)
            if self._path_is_stale(curr_cell):
                self._path = self._astar(level, curr_cell, target_cell)
                self._path_target = target_cell
                self._path_mode = mode

        if not self._path and curr_cell == target_cell:
            target_x, target_y = self._target_point_in_cell(target, target_cell)
            self._move_toward_pixel(target_x, target_y)
            self._wrap_tunnel()
            return

        if not self._path:
            return

        next_cell = self._path[0]
        next_x = next_cell[1] * CELL_W + CELL_W // 2
        next_y = next_cell[0] * CELL_H + CELL_H // 2
        if self.center_x == next_x and self.center_y == next_y:
            self._path.pop(0)
        else:
            self._move_toward_pixel(next_x, next_y)

        self._wrap_tunnel()

    def _astar(self, level: Level, start: Cell, goal: Cell) -> list[Cell]:
        """Return the shortest path from start to goal using Manhattan A*."""
        if start == goal:
            return []

        counter = 0
        open_set: list[tuple[int, int, Cell]] = [(self._heuristic(start, goal), counter, start)]
        came_from: dict[Cell, Cell] = {}
        g_score: dict[Cell, int] = {start: 0}
        closed: set[Cell] = set()

        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current in closed:
                continue
            if current == goal:
                return self._reconstruct_path(came_from, current)

            closed.add(current)
            for neighbor in self._neighbor_cells(level, current):
                if neighbor in closed:
                    continue
                tentative_g = g_score[current] + 1
                if tentative_g >= g_score.get(neighbor, BOARD_ROWS * BOARD_COLS):
                    continue
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                counter += 1
                heapq.heappush(
                    open_set,
                    (tentative_g + self._heuristic(neighbor, goal), counter, neighbor),
                )

        return []

    def _clear_path(self) -> None:
        """Invalidate the cached A* route."""
        self._path = []
        self._path_target = (-1, -1)
        self._path_mode = (self.dead, self.in_box)

    def _move_toward_pixel(self, pixel_x: int, pixel_y: int) -> None:
        """Move one frame toward a pixel target without overshooting."""
        dx = pixel_x - self.center_x
        dy = pixel_y - self.center_y

        if abs(dx) >= abs(dy) and dx:
            step = min(self.speed, abs(dx))
            if dx > 0:
                self.x_pos += step
                self.direction = RIGHT
            else:
                self.x_pos -= step
                self.direction = LEFT
        elif dy:
            step = min(self.speed, abs(dy))
            if dy > 0:
                self.y_pos += step
                self.direction = DOWN
            else:
                self.y_pos -= step
                self.direction = UP

    def _target_point_in_cell(self, target: Point, target_cell: Cell) -> Point:
        """Return a safe pixel target inside the requested cell."""
        row, col = target_cell
        min_x = col * CELL_W
        max_x = min_x + CELL_W - 1
        min_y = row * CELL_H
        max_y = min_y + CELL_H - 1
        target_x = max(min_x, min(max_x, target[0]))
        target_y = max(min_y, min(max_y, target[1]))
        return target_x, target_y

    def _cell_from_point(self, point: Point) -> Cell:
        """Convert pixel coordinates to a clamped board cell."""
        x, y = point
        row = max(0, min(BOARD_ROWS - 1, y // CELL_H))
        col = max(0, min(BOARD_COLS - 1, x // CELL_W))
        return row, col

    def _trim_path_to_current_cell(self, curr_cell: Cell) -> None:
        """Discard cached steps the ghost has already reached."""
        if curr_cell not in self._path:
            return
        index = self._path.index(curr_cell)
        del self._path[: index + 1]

    def _path_is_stale(self, curr_cell: Cell) -> bool:
        """Return whether the cached path no longer starts beside this cell."""
        if not self._path:
            return True
        next_cell = self._path[0]
        return self._heuristic(curr_cell, next_cell) != 1

    def _nearest_passable_cell(self, level: Level, cell: Cell) -> Cell:
        """Return cell if passable, otherwise the nearest passable cell."""
        if self._is_passable_cell(level, cell):
            return cell

        queue = [cell]
        seen = {cell}
        for current in queue:
            for neighbor in self._bounded_neighbor_cells(current):
                if neighbor in seen:
                    continue
                if self._is_passable_cell(level, neighbor):
                    return neighbor
                seen.add(neighbor)
                queue.append(neighbor)
        return cell

    def _neighbor_cells(self, level: Level, cell: Cell) -> list[Cell]:
        """Return passable neighbors for A* expansion."""
        return [neighbor for neighbor in self._bounded_neighbor_cells(cell) if self._is_passable_cell(level, neighbor)]

    def _bounded_neighbor_cells(self, cell: Cell) -> list[Cell]:
        """Return neighbors that are inside the board."""
        row, col = cell
        neighbors: list[Cell] = []
        for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_cell = (row + row_delta, col + col_delta)
            if 0 <= next_cell[0] < BOARD_ROWS and 0 <= next_cell[1] < BOARD_COLS:
                neighbors.append(next_cell)
        return neighbors

    def _is_passable_cell(self, level: Level, cell: Cell) -> bool:
        """Return whether a board cell is passable for this ghost state."""
        row, col = cell
        tile = level[row][col]
        return tile < WALL_TILE or (tile == GATE_TILE and self._can_use_gate())

    def _can_use_gate(self) -> bool:
        """Return whether this ghost may pass through the ghost-house gate."""
        return self.dead or self.in_box or _in_chase_box(self)

    @staticmethod
    def _heuristic(cell: Cell, goal: Cell) -> int:
        """Return Manhattan distance between two cells."""
        return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

    @staticmethod
    def _reconstruct_path(came_from: dict[Cell, Cell], current: Cell) -> list[Cell]:
        """Build a start-exclusive path from A* parent links."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path[1:]


def get_targets(player: Player, ghosts: list[Ghost], level: Level) -> list[Point]:
    """Calculate the next target for each ghost."""
    if player.x_pos < RUNAWAY_SPLIT:
        runaway_x = RUNAWAY_MAX
    else:
        runaway_x = RUNAWAY_MIN
    if player.y_pos < RUNAWAY_SPLIT:
        runaway_y = RUNAWAY_MAX
    else:
        runaway_y = RUNAWAY_MIN

    blinky, inky, pinky, clyde = ghosts
    if player.powerup:
        if not blinky.dead and not player.eaten_ghost[BLINKY_ID]:
            blink_target = (runaway_x, runaway_y)
        elif not blinky.dead and player.eaten_ghost[BLINKY_ID]:
            if _in_chase_box(blinky):
                blink_target = BOX_EXIT_TARGET
            else:
                blink_target = (player.x_pos, player.y_pos)
        else:
            blink_target = RETURN_TARGET
        if not inky.dead and not player.eaten_ghost[INKY_ID]:
            ink_target = (runaway_x, player.y_pos)
        elif not inky.dead and player.eaten_ghost[INKY_ID]:
            if _in_chase_box(inky):
                ink_target = BOX_EXIT_TARGET
            else:
                ink_target = (player.x_pos, player.y_pos)
        else:
            ink_target = RETURN_TARGET
        if not pinky.dead:
            pink_target = (player.x_pos, runaway_y)
        else:
            pink_target = RETURN_TARGET
        if not clyde.dead and not player.eaten_ghost[CLYDE_ID]:
            clyd_target = CLYDE_POWER_TARGET
        elif not clyde.dead and player.eaten_ghost[CLYDE_ID]:
            if _in_chase_box(clyde):
                clyd_target = BOX_EXIT_TARGET
            else:
                clyd_target = (player.x_pos, player.y_pos)
        else:
            clyd_target = RETURN_TARGET
    else:
        blink_target = _normal_target(level, player, blinky, BLINKY_SCATTER_TARGET)
        ink_target = _normal_target(level, player, inky, INKY_SCATTER_TARGET)
        pink_target = _normal_target(level, player, pinky, PINKY_SCATTER_TARGET)
        clyd_target = _normal_target(level, player, clyde, CLYDE_SCATTER_TARGET)
    return [blink_target, ink_target, pink_target, clyd_target]


def _in_chase_box(ghost: Ghost) -> bool:
    """Return whether a ghost is inside the house target box."""
    return CHASE_BOX_MIN_X < ghost.x_pos < CHASE_BOX_MAX_X and CHASE_BOX_MIN_Y < ghost.y_pos < CHASE_BOX_MAX_Y


def _normal_target(level: Level, player: Player, ghost: Ghost, fallback_target: Point) -> Point:
    """Return chase, exit, return, or scatter target for normal play."""
    ghost.is_patrolling = False
    if ghost.dead:
        return RETURN_TARGET
    if ghost.in_box:
        return BOX_EXIT_TARGET
    if _can_detect_player(level, player, ghost):
        return player.x_pos, player.y_pos
    ghost.is_patrolling = True
    return _patrol_target(level, ghost, fallback_target)


def _patrol_target(level: Level, ghost: Ghost, fallback_target: Point) -> Point:
    """Return the current whole-map patrol target."""
    patrol_cells = _patrol_cells(level, ghost)
    if not patrol_cells:
        return fallback_target

    ghost_cell = ghost._cell_from_point((ghost.center_x, ghost.center_y))
    for _ in range(len(patrol_cells)):
        target_cell = patrol_cells[ghost._patrol_index % len(patrol_cells)]
        reachable = bool(ghost._astar(level, ghost_cell, target_cell))
        if Ghost._heuristic(ghost_cell, target_cell) > PATROL_REACHED_DISTANCE and reachable:
            return _point_from_cell(target_cell)
        ghost._patrol_index += 1

    return fallback_target


def _patrol_cells(level: Level, ghost: Ghost) -> list[Cell]:
    """Return passable patrol cells spread across the whole board."""
    reachable = _reachable_patrol_cells(level, ghost)
    cells: list[Cell] = []
    rows = list(range(2, BOARD_ROWS - 2, PATROL_ROW_STEP))
    cols = list(range(2, BOARD_COLS - 2, PATROL_COL_STEP))
    for row_index, row in enumerate(rows):
        row_cols = cols if row_index % 2 == 0 else list(reversed(cols))
        for col in row_cols:
            cell = (row, col)
            if cell in reachable and not _is_ghost_house_cell(cell):
                cells.append(cell)

    if cells:
        return cells

    return [cell for cell in reachable if not _is_ghost_house_cell(cell)]


def _reachable_patrol_cells(level: Level, ghost: Ghost) -> set[Cell]:
    """Return all patrol cells reachable from the ghost's current cell."""
    start = ghost._cell_from_point((ghost.center_x, ghost.center_y))
    queue = [start]
    reachable = {start}
    for current in queue:
        for neighbor in ghost._neighbor_cells(level, current):
            if neighbor in reachable:
                continue
            reachable.add(neighbor)
            queue.append(neighbor)
    return reachable


def _is_ghost_house_cell(cell: Cell) -> bool:
    """Return whether a cell is inside the ghost house."""
    row, col = cell
    x_pos = col * CELL_W + CELL_W // 2
    y_pos = row * CELL_H + CELL_H // 2
    return GHOST_BOX_MIN_X < x_pos < GHOST_BOX_MAX_X and GHOST_BOX_MIN_Y < y_pos < GHOST_BOX_MAX_Y


def _point_from_cell(cell: Cell) -> Point:
    """Return the pixel center for a board cell."""
    row, col = cell
    return col * CELL_W + CELL_W // 2, row * CELL_H + CELL_H // 2


def _can_detect_player(level: Level, player: Player, ghost: Ghost) -> bool:
    """Return whether the ghost can currently detect Pac-Man."""
    ghost_cell = ghost._cell_from_point((ghost.center_x, ghost.center_y))
    player_cell = ghost._cell_from_point((player.center_x, player.center_y))
    distance = abs(ghost_cell[0] - player_cell[0]) + abs(ghost_cell[1] - player_cell[1])
    if distance <= GHOST_DETECTION_RADIUS_CELLS:
        return True
    return _has_line_of_sight(level, ghost_cell, player_cell)


def _has_line_of_sight(level: Level, ghost_cell: Cell, player_cell: Cell) -> bool:
    """Return whether ghost and player share an unobstructed row or column."""
    if ghost_cell[0] == player_cell[0]:
        row = ghost_cell[0]
        start = min(ghost_cell[1], player_cell[1]) + 1
        stop = max(ghost_cell[1], player_cell[1])
        return all(level[row][col] < WALL_TILE for col in range(start, stop))
    if ghost_cell[1] == player_cell[1]:
        col = ghost_cell[1]
        start = min(ghost_cell[0], player_cell[0]) + 1
        stop = max(ghost_cell[0], player_cell[0])
        return all(level[row][col] < WALL_TILE for row in range(start, stop))
    return False
