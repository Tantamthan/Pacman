from __future__ import annotations

import pygame

from pacman.constants import (
    BLINKY_ID,
    BOARD_COLS,
    BOX_EXIT_TARGET,
    CELL_H,
    CELL_W,
    CHASE_BOX_MAX_X,
    CHASE_BOX_MAX_Y,
    CHASE_BOX_MIN_X,
    CHASE_BOX_MIN_Y,
    CLYDE_ID,
    CLYDE_POWER_TARGET,
    DOWN,
    GATE_TILE,
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
    LEFT,
    PINKY_ID,
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

        self.in_box = GHOST_BOX_MIN_X < self.x_pos < GHOST_BOX_MAX_X and GHOST_BOX_MIN_Y < self.y_pos < GHOST_BOX_MAX_Y
        self.turns = turns
        return self.turns, self.in_box

    def _is_open(self, level: Level, pixel_y: int, pixel_x: int) -> bool:
        """Return whether a pixel coordinate is passable for this ghost."""
        tile = level[pixel_y // CELL_H][pixel_x // CELL_W]
        return tile < WALL_TILE or (tile == GATE_TILE and (self.in_box or self.dead))

    def reset(self, x_coord: int, y_coord: int, direction: int) -> None:
        """Reset position and temporary ghost state."""
        self.x_pos = x_coord
        self.y_pos = y_coord
        self.direction = direction
        self.dead = False
        self.in_box = False
        self.turns = [False, False, False, False]

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

    def move_astar(self, level: Level, target: Point) -> None:
        """
        TODO: Replace move_blinky/move_clyde with A* pathfinding.
        Use level as graph, heuristic = Manhattan distance to target.
        """
        pass


def get_targets(player: Player, ghosts: list[Ghost]) -> list[Point]:
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
        blink_target = BOX_EXIT_TARGET if not blinky.dead and _in_chase_box(blinky) else (player.x_pos, player.y_pos)
        if blinky.dead:
            blink_target = RETURN_TARGET
        ink_target = BOX_EXIT_TARGET if not inky.dead and _in_chase_box(inky) else (player.x_pos, player.y_pos)
        if inky.dead:
            ink_target = RETURN_TARGET
        pink_target = BOX_EXIT_TARGET if not pinky.dead and _in_chase_box(pinky) else (player.x_pos, player.y_pos)
        if pinky.dead:
            pink_target = RETURN_TARGET
        clyd_target = BOX_EXIT_TARGET if not clyde.dead and _in_chase_box(clyde) else (player.x_pos, player.y_pos)
        if clyde.dead:
            clyd_target = RETURN_TARGET
    return [blink_target, ink_target, pink_target, clyd_target]


def _in_chase_box(ghost: Ghost) -> bool:
    """Return whether a ghost is inside the house target box."""
    return CHASE_BOX_MIN_X < ghost.x_pos < CHASE_BOX_MAX_X and CHASE_BOX_MIN_Y < ghost.y_pos < CHASE_BOX_MAX_Y
