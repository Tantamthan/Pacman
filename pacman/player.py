"""Player model and movement rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from pacman.constants import (
    BLACK,
    BOARD_COLS,
    CELL_H,
    CELL_W,
    DOT_TILE,
    DOWN,
    EMPTY_TILE,
    FRAME_IMAGE_DIVISOR,
    LEFT,
    PLAYER_CENTER_OFFSET_X,
    PLAYER_CENTER_OFFSET_Y,
    PLAYER_COLLISION_RADIUS,
    PLAYER_COLLISION_WIDTH,
    PLAYER_DOT_MAX_X,
    PLAYER_DOT_MIN_X,
    PLAYER_LIVES,
    PLAYER_SPEED,
    PLAYER_START_DIRECTION,
    PLAYER_START_X,
    PLAYER_START_Y,
    PLAYER_TURN_FUDGE,
    PLAYER_UNSTICK_FRAMES,
    PLAYER_TUNNEL_LEFT,
    PLAYER_TUNNEL_RIGHT,
    PLAYER_WRAP_LEFT,
    PLAYER_WRAP_RIGHT,
    POWER_DOT_TILE,
    RIGHT,
    TURN_WINDOW_MAX,
    TURN_WINDOW_MIN,
    UP,
    WALL_TILE,
)

if TYPE_CHECKING:
    from pacman.ghost import Ghost

Level = list[list[int]]


class Player:
    """Store Pac-Man state and handle player movement."""

    # Khởi tạo Pac-Man với trạng thái ban đầu: vị trí, hướng đi, tốc độ, điểm, số mạng, các cờ powerup.
    def __init__(self) -> None:
        """Create a player with the original starting state."""
        self.x_pos: int = PLAYER_START_X
        self.y_pos: int = PLAYER_START_Y
        self.direction: int = PLAYER_START_DIRECTION
        self.direction_command: int = PLAYER_START_DIRECTION
        self.speed: int = PLAYER_SPEED
        self.score: int = 0
        self.lives: int = PLAYER_LIVES
        self.powerup: bool = False
        self.power_counter: int = 0
        self.turns_allowed: list[bool] = [False, False, False, False]
        self.eaten_ghost: list[bool] = [False, False, False, False]
        self.blocked_frames: int = 0

    # Trả về tọa độ x tâm hộp va chạm của Pac-Man.
    @property
    def center_x(self) -> int:
        """Return the horizontal collision center."""
        return self.x_pos + PLAYER_CENTER_OFFSET_X

    # Trả về tọa độ y tâm hộp va chạm của Pac-Man.
    @property
    def center_y(self) -> int:
        """Return the vertical collision center."""
        return self.y_pos + PLAYER_CENTER_OFFSET_Y

    # Vẽ Pac-Man lên màn hình theo hướng hiện tại (xoay/flip ảnh sprite); trả về rect dùng cho phát hiện va chạm.
    def draw(
        self,
        screen: pygame.Surface,
        images: list[pygame.Surface],
        counter: int,
        flicker: bool,
    ) -> pygame.Rect:
        """Draw Pac-Man and return the collision circle rect."""
        del flicker
        rect = pygame.draw.circle(
            screen,
            BLACK,
            (self.center_x, self.center_y),
            PLAYER_COLLISION_RADIUS,
            PLAYER_COLLISION_WIDTH,
        )
        image = images[counter // FRAME_IMAGE_DIVISOR]
        if self.direction == RIGHT:
            screen.blit(image, (self.x_pos, self.y_pos))
        elif self.direction == LEFT:
            screen.blit(pygame.transform.flip(image, True, False), (self.x_pos, self.y_pos))
        elif self.direction == UP:
            screen.blit(pygame.transform.rotate(image, 90), (self.x_pos, self.y_pos))
        elif self.direction == DOWN:
            screen.blit(pygame.transform.rotate(image, 270), (self.x_pos, self.y_pos))
        return rect

    # Xét bản đồ xung quanh để xác định 4 hướng (R/L/U/D) nào Pac-Man có thể rẽ, lưu vào turns_allowed.
    def check_collisions(self, level: Level) -> list[bool]:
        """Return legal turn directions for the current board position."""
        turns = [False, False, False, False]
        center_x = self.center_x
        center_y = self.center_y
        if center_x // CELL_W < BOARD_COLS - 1:
            if self.direction == RIGHT and level[center_y // CELL_H][(center_x - PLAYER_TURN_FUDGE) // CELL_W] < WALL_TILE:
                turns[LEFT] = True
            if self.direction == LEFT and level[center_y // CELL_H][(center_x + PLAYER_TURN_FUDGE) // CELL_W] < WALL_TILE:
                turns[RIGHT] = True
            if self.direction == UP and level[(center_y + PLAYER_TURN_FUDGE) // CELL_H][center_x // CELL_W] < WALL_TILE:
                turns[DOWN] = True
            if self.direction == DOWN and level[(center_y - PLAYER_TURN_FUDGE) // CELL_H][center_x // CELL_W] < WALL_TILE:
                turns[UP] = True

            if self.direction == UP or self.direction == DOWN:
                if TURN_WINDOW_MIN <= center_x % CELL_W <= TURN_WINDOW_MAX:
                    if level[(center_y + PLAYER_TURN_FUDGE) // CELL_H][center_x // CELL_W] < WALL_TILE:
                        turns[DOWN] = True
                    if level[(center_y - PLAYER_TURN_FUDGE) // CELL_H][center_x // CELL_W] < WALL_TILE:
                        turns[UP] = True
                if TURN_WINDOW_MIN <= center_y % CELL_H <= TURN_WINDOW_MAX:
                    if level[center_y // CELL_H][(center_x - CELL_W) // CELL_W] < WALL_TILE:
                        turns[LEFT] = True
                    if level[center_y // CELL_H][(center_x + CELL_W) // CELL_W] < WALL_TILE:
                        turns[RIGHT] = True
            if self.direction == RIGHT or self.direction == LEFT:
                if TURN_WINDOW_MIN <= center_x % CELL_W <= TURN_WINDOW_MAX:
                    if level[(center_y + CELL_H) // CELL_H][center_x // CELL_W] < WALL_TILE:
                        turns[DOWN] = True
                    if level[(center_y - CELL_H) // CELL_H][center_x // CELL_W] < WALL_TILE:
                        turns[UP] = True
                if TURN_WINDOW_MIN <= center_y % CELL_H <= TURN_WINDOW_MAX:
                    if level[center_y // CELL_H][(center_x - PLAYER_TURN_FUDGE) // CELL_W] < WALL_TILE:
                        turns[LEFT] = True
                    if level[center_y // CELL_H][(center_x + PLAYER_TURN_FUDGE) // CELL_W] < WALL_TILE:
                        turns[RIGHT] = True
        else:
            turns[RIGHT] = True
            turns[LEFT] = True

        self.turns_allowed = turns
        return turns

    # Di chuyển Pac-Man 1 frame theo hướng hiện tại; nếu bị kẹt quá lâu sẽ tự chọn hướng khác để thoát.
    def move(self, level: Level) -> None:
        """Move Pac-Man one frame using the current direction."""
        del level
        if self._move_in_direction(self.direction):
            self.blocked_frames = 0
            return

        self.blocked_frames += 1
        if self.blocked_frames < PLAYER_UNSTICK_FRAMES:
            return

        fallback = self._fallback_direction()
        if fallback is None:
            return

        self.set_direction(fallback)
        if self._move_in_direction(self.direction):
            self.blocked_frames = 0

    # Thử di chuyển 1 frame theo hướng cho trước nếu được phép; trả về True nếu đi thành công.
    def _move_in_direction(self, direction: int) -> bool:
        """Move one frame in direction when allowed."""
        if direction == RIGHT and self.turns_allowed[RIGHT]:
            self.x_pos += self.speed
            return True
        if direction == LEFT and self.turns_allowed[LEFT]:
            self.x_pos -= self.speed
            return True
        if direction == UP and self.turns_allowed[UP]:
            self.y_pos -= self.speed
            return True
        if direction == DOWN and self.turns_allowed[DOWN]:
            self.y_pos += self.speed
            return True
        return False

    # Chọn hướng dự phòng khi Pac-Man bị chặn: ưu tiên direction_command, rồi đến hướng ngược lại, cuối cùng là hướng bất kỳ hợp lệ.
    def _fallback_direction(self) -> int | None:
        """Choose a legal direction after Pac-Man has been blocked."""
        if self.turns_allowed[self.direction_command]:
            return self.direction_command
        reverse = {RIGHT: LEFT, LEFT: RIGHT, UP: DOWN, DOWN: UP}
        reverse_direction = reverse[self.direction]
        if self.turns_allowed[reverse_direction]:
            return reverse_direction
        for direction, allowed in enumerate(self.turns_allowed):
            if allowed:
                return direction
        return None

    # Đổi hướng đi và canh Pac-Man vào tâm làn để tránh kẹt cạnh tường khi rẽ.
    def set_direction(self, direction: int) -> None:
        """Set direction and align Pac-Man to the lane being entered."""
        if direction == self.direction:
            return
        if direction in (RIGHT, LEFT):
            self._snap_center_y_to_cell()
        else:
            self._snap_center_x_to_cell()
        self.direction = direction

    # Canh tọa độ x của Pac-Man về đúng tâm cột hiện tại (dùng khi chuẩn bị rẽ lên/xuống).
    def _snap_center_x_to_cell(self) -> None:
        """Align Pac-Man horizontally to the current cell center."""
        col = self.center_x // CELL_W
        self.x_pos = col * CELL_W + CELL_W // 2 - PLAYER_CENTER_OFFSET_X

    # Canh tọa độ y của Pac-Man về đúng tâm hàng hiện tại (dùng khi chuẩn bị rẽ trái/phải).
    def _snap_center_y_to_cell(self) -> None:
        """Align Pac-Man vertically to the current cell center."""
        row = self.center_y // CELL_H
        self.y_pos = row * CELL_H + CELL_H // 2 - PLAYER_CENTER_OFFSET_Y

    # Ăn dot (+10đ) hoặc power-dot (+50đ + bật powerup) tại ô đang chứa tâm Pac-Man.
    def eat_tile_at(self, level: Level, center_x: int, center_y: int) -> None:
        """Consume dots and power dots at the supplied board center."""
        if PLAYER_DOT_MIN_X < self.x_pos < PLAYER_DOT_MAX_X:
            row = center_y // CELL_H
            col = center_x // CELL_W
            if level[row][col] == DOT_TILE:
                level[row][col] = EMPTY_TILE
                self.score += 10
            if level[row][col] == POWER_DOT_TILE:
                level[row][col] = EMPTY_TILE
                self.score += 50
                self.powerup = True
                self.power_counter = 0
                self.eaten_ghost = [False, False, False, False]

    # Reset Pac-Man về vị trí khởi đầu và xóa trạng thái powerup (giữ nguyên điểm và mạng).
    def reset(self) -> None:
        """Reset Pac-Man position and temporary power state."""
        self.x_pos = PLAYER_START_X
        self.y_pos = PLAYER_START_Y
        self.direction = PLAYER_START_DIRECTION
        self.direction_command = PLAYER_START_DIRECTION
        self.powerup = False
        self.power_counter = 0
        self.eaten_ghost = [False, False, False, False]
        self.blocked_frames = 0

    # Reset toàn bộ cho ván mới: vị trí, điểm = 0 và số mạng về tối đa.
    def reset_full(self) -> None:
        """Reset score, lives, and all player state for a new game."""
        self.reset()
        self.score = 0
        self.lives = PLAYER_LIVES

    # Khi Pac-Man đi qua mép phải/trái màn hình thì teleport sang phía đối diện (đường hầm).
    def wrap_tunnel(self) -> None:
        """Move Pac-Man across the side tunnel when crossing the edge."""
        if self.x_pos > PLAYER_TUNNEL_RIGHT:
            self.x_pos = PLAYER_WRAP_LEFT
        elif self.x_pos < PLAYER_TUNNEL_LEFT:
            self.x_pos = PLAYER_WRAP_RIGHT

    # TODO: Hàm AI Minimax + Alpha-Beta Pruning cho Pac-Man (chưa cài đặt - hiện trả về None).
    def get_best_move_minimax(
        self,
        ghosts: list["Ghost"],
        level: Level,
        depth: int = 3,
    ) -> int | None:
        """
        TODO: Minimax + Alpha-Beta Pruning.
        Player = MAX, Ghosts = MIN, depth default 3.
        Return the best direction (0=R,1=L,2=U,3=D).
        """
        pass
