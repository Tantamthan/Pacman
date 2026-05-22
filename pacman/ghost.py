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

    # Khởi tạo một con ma với vị trí, target, tốc độ, hình ảnh, hướng đi và các cờ trạng thái (chết/trong hộp).
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
        self._last_pos: tuple[int, int] = (self.x_pos, self.y_pos)
        self._stuck_frames: int = 0
        # Patrol reachability cache — recomputed when level identity or gate access changes.
        self._patrol_cache_key: tuple[int, bool] | None = None
        self._patrol_reachable: set[Cell] = set()
        self._patrol_cells_cache: list[Cell] = []

    # Trả về tọa độ x tâm hộp va chạm của ma.
    @property
    def center_x(self) -> int:
        """Return the horizontal collision center."""
        return self.x_pos + GHOST_CENTER_OFFSET

    # Trả về tọa độ y tâm hộp va chạm của ma.
    @property
    def center_y(self) -> int:
        """Return the vertical collision center."""
        return self.y_pos + GHOST_CENTER_OFFSET

    # Vẽ ma lên màn hình với sprite tương ứng (bình thường / sợ khi Pac-Man có powerup / mắt khi đã bị ăn); trả về rect va chạm.
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

    # Xét bản đồ quanh ma để liệt kê 4 hướng có thể đi và xác định ma có đang ở trong hộp nhà ma không.
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

    # Kiểm tra một điểm pixel có đi qua được với ma này không (xét cả cổng nhà ma tùy trạng thái).
    def _is_open(self, level: Level, pixel_y: int, pixel_x: int) -> bool:
        """Return whether a pixel coordinate is passable for this ghost."""
        tile = level[pixel_y // CELL_H][pixel_x // CELL_W]
        return tile < WALL_TILE or (tile == GATE_TILE and self._can_use_gate())

    # Đưa ma về vị trí khởi đầu, xóa trạng thái dead/in_box và path đã cache.
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
        self._last_pos = (self.x_pos, self.y_pos)
        self._stuck_frames = 0

    # Di chuyển 1 frame kiểu Clyde: khi leo dọc còn tạt ngang để truy đuổi (hung hăng hơn Inky).
    def move_clyde(self) -> tuple[int, int, int]:
        """Move using Clyde's original pursuit behavior (aggressive sideways turns)."""
        if self.direction == RIGHT:
            self._pursue_right()
        elif self.direction == LEFT:
            self._pursue_left()
        elif self.direction == UP:
            self._pursue_up_aggressive()
        elif self.direction == DOWN:
            self._pursue_down_aggressive()
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    # Di chuyển 1 frame kiểu Inky: khi leo dọc đi thẳng (không tạt ngang) — đơn giản hơn Clyde.
    def move_inky(self) -> tuple[int, int, int]:
        """Move using Inky's original pursuit behavior (straight-through vertical)."""
        if self.direction == RIGHT:
            self._pursue_right()
        elif self.direction == LEFT:
            self._pursue_left()
        elif self.direction == UP:
            self._pursue_up_simple()
        elif self.direction == DOWN:
            self._pursue_down_simple()
        self._wrap_tunnel()
        return self.x_pos, self.y_pos, self.direction

    # Logic đuổi theo target khi ma đang đi sang phải: ưu tiên đi tiếp, rẽ dọc khi bị chặn (chung cho Inky/Clyde).
    def _pursue_right(self) -> None:
        """RIGHT-direction pursuit. Identical for Inky and Clyde."""
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

    # Logic đuổi theo target khi ma đang đi sang trái (chung cho Inky/Clyde).
    def _pursue_left(self) -> None:
        """LEFT-direction pursuit. Identical for Inky and Clyde."""
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

    # Đuổi target khi đi lên kiểu Clyde: ưu tiên rẽ ngang về phía target trong khi đang leo.
    def _pursue_up_aggressive(self) -> None:
        """Clyde's UP: prefer LEFT toward target, take sideways turns while ascending."""
        if self.target[0] < self.x_pos and self.turns[LEFT]:
            self.direction = LEFT
            self.x_pos -= self.speed
        elif self.target[1] < self.y_pos and self.turns[UP]:
            self.y_pos -= self.speed
        elif not self.turns[UP]:
            self._vertical_fallback(up=True)
        elif self.turns[UP]:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.direction = RIGHT
                self.x_pos += self.speed
            elif self.target[0] < self.x_pos and self.turns[LEFT]:
                self.direction = LEFT
                self.x_pos -= self.speed
            else:
                self.y_pos -= self.speed

    # Đuổi target khi đi lên kiểu Inky: chỉ đi thẳng lên, bị chặn thì fallback.
    def _pursue_up_simple(self) -> None:
        """Inky's UP: just go up if possible, else fallback."""
        if self.target[1] < self.y_pos and self.turns[UP]:
            self.y_pos -= self.speed
        elif not self.turns[UP]:
            self._vertical_fallback(up=True)
        elif self.turns[UP]:
            self.y_pos -= self.speed

    # Đuổi target khi đi xuống kiểu Clyde: kết hợp rẽ ngang khi đang đi xuống.
    def _pursue_down_aggressive(self) -> None:
        """Clyde's DOWN: take sideways turns while descending."""
        if self.target[1] > self.y_pos and self.turns[DOWN]:
            self.y_pos += self.speed
        elif not self.turns[DOWN]:
            self._vertical_fallback(up=False)
        elif self.turns[DOWN]:
            if self.target[0] > self.x_pos and self.turns[RIGHT]:
                self.direction = RIGHT
                self.x_pos += self.speed
            elif self.target[0] < self.x_pos and self.turns[LEFT]:
                self.direction = LEFT
                self.x_pos -= self.speed
            else:
                self.y_pos += self.speed

    # Đuổi target khi đi xuống kiểu Inky: chỉ đi thẳng, bị chặn thì fallback.
    def _pursue_down_simple(self) -> None:
        """Inky's DOWN: just go down if possible, else fallback."""
        if self.target[1] > self.y_pos and self.turns[DOWN]:
            self.y_pos += self.speed
        elif not self.turns[DOWN]:
            self._vertical_fallback(up=False)
        elif self.turns[DOWN]:
            self.y_pos += self.speed

    # Chuỗi fallback chung khi ma đang đi dọc (lên/xuống) bị chặn: thử ngang, đảo chiều, rồi đến hướng bất kỳ hợp lệ.
    def _vertical_fallback(self, up: bool) -> None:
        """Shared fallback chain when blocked while moving UP or DOWN."""
        opposite_y = DOWN if up else UP
        opposite_sign = 1 if up else -1  # opposite direction y-delta sign
        if self.target[0] > self.x_pos and self.turns[RIGHT]:
            self.direction = RIGHT
            self.x_pos += self.speed
        elif self.target[0] < self.x_pos and self.turns[LEFT]:
            self.direction = LEFT
            self.x_pos -= self.speed
        elif (self.target[1] > self.y_pos if up else self.target[1] < self.y_pos) and self.turns[opposite_y]:
            self.direction = opposite_y
            self.y_pos += opposite_sign * self.speed
        elif self.turns[LEFT if up else UP]:
            if up:
                self.direction = LEFT
                self.x_pos -= self.speed
            else:
                self.direction = UP
                self.y_pos -= self.speed
        elif self.turns[DOWN if up else LEFT]:
            if up:
                self.direction = DOWN
                self.y_pos += self.speed
            else:
                self.direction = LEFT
                self.x_pos -= self.speed
        elif self.turns[RIGHT]:
            self.direction = RIGHT
            self.x_pos += self.speed

    # Cho ma đi xuyên đường hầm trái: nếu vượt mép trái thì teleport sang mép phải, đồng thời xóa path đã cache.
    def _wrap_tunnel(self) -> None:
        """Apply the original left-side ghost tunnel wrap."""
        if self.x_pos < GHOST_TUNNEL_LEFT:
            self.x_pos = GHOST_WRAP_RIGHT
            self._clear_path()

    # Di chuyển ma 1 frame về phía target bằng A*: tận dụng path đã cache, chỉ tính lại khi target/state đổi hoặc path stale.
    def move_astar(self, level: Level, target: Point) -> None:
        """Move one frame toward target using a cached A* path."""
        target_cell = self._nearest_passable_cell(level, self._cell_from_point(target))
        curr_cell = self._cell_from_point((self.center_x, self.center_y))
        mode = (self.dead, self.in_box)

        path_changed = mode != self._path_mode or target_cell != self._path_target
        if path_changed:
            self._path = self._astar(level, curr_cell, target_cell)
            self._path_target = target_cell
            self._path_mode = mode
        else:
            self._trim_path_to_current_cell(curr_cell)
            if self._path_is_stale(curr_cell):
                self._path = self._astar(level, curr_cell, target_cell)
                self._path_target = target_cell
                self._path_mode = mode

        # Always recompute when path empty but not yet at goal — prevents permanent stalling.
        if not self._path and curr_cell != target_cell:
            self._path = self._astar(level, curr_cell, target_cell)

        if not self._path and curr_cell == target_cell:
            target_x, target_y = self._target_point_in_cell(target, target_cell)
            self._move_toward_pixel(target_x, target_y)
            self._handle_stuck(level, curr_cell, target_cell)
            self._wrap_tunnel()
            return

        if not self._path:
            self._handle_stuck(level, curr_cell, target_cell)
            self._wrap_tunnel()
            return

        next_cell = self._path[0]
        next_x = next_cell[1] * CELL_W + CELL_W // 2
        next_y = next_cell[0] * CELL_H + CELL_H // 2
        if self.center_x == next_x and self.center_y == next_y:
            self._path.pop(0)
        else:
            self._move_toward_pixel(next_x, next_y)

        self._handle_stuck(level, curr_cell, target_cell)
        self._wrap_tunnel()

    # Phát hiện ma bị kẹt (không di chuyển nhiều frame liên tiếp); xóa path cache và chọn neighbor gần target nhất để thoát.
    def _handle_stuck(self, level: Level, curr_cell: Cell, target_cell: Cell) -> None:
        """Detect zero-movement frames and force a fresh path / sideways step."""
        if (self.x_pos, self.y_pos) != self._last_pos:
            self._stuck_frames = 0
            self._last_pos = (self.x_pos, self.y_pos)
            return
        self._stuck_frames += 1
        if self._stuck_frames < 6:
            return
        # Stuck too long — drop cached path, try any passable neighbor toward target.
        self._clear_path()
        neighbors = self._neighbor_cells(level, curr_cell)
        if not neighbors:
            self._stuck_frames = 0
            return
        neighbors.sort(key=lambda cell: self._heuristic(cell, target_cell))
        chosen = neighbors[0]
        self._path = [chosen]
        self._path_target = target_cell
        self._stuck_frames = 0

    # Thuật toán A* với heuristic Manhattan: trả về danh sách cell từ sau start đến goal (rỗng nếu start==goal hoặc không có đường).
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

    # Xóa toàn bộ path A* đã cache để buộc tính lại ở lần move tiếp theo.
    def _clear_path(self) -> None:
        """Invalidate the cached A* route."""
        self._path = []
        self._path_target = (-1, -1)
        self._path_mode = (self.dead, self.in_box)

    # Di chuyển 1 frame về phía một điểm pixel cụ thể, không vượt quá điểm đích, đồng thời cập nhật hướng đi.
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

    # Clamp tọa độ pixel target để chắc chắn nằm trong giới hạn cell đích (tránh nhảy ra ngoài cell).
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

    # Chuyển tọa độ pixel sang chỉ số (row, col) trên board, đã clamp trong giới hạn bản đồ.
    def _cell_from_point(self, point: Point) -> Cell:
        """Convert pixel coordinates to a clamped board cell."""
        x, y = point
        row = max(0, min(BOARD_ROWS - 1, y // CELL_H))
        col = max(0, min(BOARD_COLS - 1, x // CELL_W))
        return row, col

    # Bỏ tất cả các bước trong path đã được ma đi qua (đến và bao gồm cell hiện tại).
    def _trim_path_to_current_cell(self, curr_cell: Cell) -> None:
        """Discard cached steps the ghost has already reached."""
        if curr_cell not in self._path:
            return
        index = self._path.index(curr_cell)
        del self._path[: index + 1]

    # Kiểm tra path cache có còn hợp lệ không: cell đầu tiên của path phải kề với cell hiện tại của ma.
    def _path_is_stale(self, curr_cell: Cell) -> bool:
        """Return whether the cached path no longer starts beside this cell."""
        if not self._path:
            return True
        next_cell = self._path[0]
        return self._heuristic(curr_cell, next_cell) != 1

    # Nếu cell qua được thì trả về luôn; ngược lại dùng BFS tìm cell qua được gần nhất (để target không rơi vào tường).
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

    # Trả về danh sách 4 cell láng giềng có thể đi qua được (dùng để mở rộng node trong A*/BFS).
    def _neighbor_cells(self, level: Level, cell: Cell) -> list[Cell]:
        """Return passable neighbors for A* expansion."""
        return [neighbor for neighbor in self._bounded_neighbor_cells(cell) if self._is_passable_cell(level, neighbor)]

    # Trả về 4 cell láng giềng nằm trong giới hạn bản đồ (chưa xét tường).
    def _bounded_neighbor_cells(self, cell: Cell) -> list[Cell]:
        """Return neighbors that are inside the board."""
        row, col = cell
        neighbors: list[Cell] = []
        for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_cell = (row + row_delta, col + col_delta)
            if 0 <= next_cell[0] < BOARD_ROWS and 0 <= next_cell[1] < BOARD_COLS:
                neighbors.append(next_cell)
        return neighbors

    # Một cell có đi qua được không (đường, hoặc cổng nhà ma nếu trạng thái cho phép).
    def _is_passable_cell(self, level: Level, cell: Cell) -> bool:
        """Return whether a board cell is passable for this ghost state."""
        row, col = cell
        tile = level[row][col]
        return tile < WALL_TILE or (tile == GATE_TILE and self._can_use_gate())

    # Ma này có được phép đi qua cổng nhà ma không (cần khi chết về hồi sinh, đang ở trong hộp, hoặc gần hộp).
    def _can_use_gate(self) -> bool:
        """Return whether this ghost may pass through the ghost-house gate."""
        return self.dead or self.in_box or _in_chase_box(self)

    # Heuristic Manhattan cho A*: khoảng cách giữa 2 cell.
    @staticmethod
    def _heuristic(cell: Cell, goal: Cell) -> int:
        """Return Manhattan distance between two cells."""
        return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

    # Dựng lại path từ dict came_from của A*; trả về danh sách cell từ sau start đến goal (bỏ start).
    @staticmethod
    def _reconstruct_path(came_from: dict[Cell, Cell], current: Cell) -> list[Cell]:
        """Build a start-exclusive path from A* parent links."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path[1:]


# Tính target cho 4 con ma mỗi frame: chế độ chạy trốn khi Pac-Man có powerup, ngược lại chase/scatter/patrol theo từng ma.
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


# Kiểm tra ma có nằm trong vùng "chase box" (vùng gần nhà ma dùng để xét luật cổng).
def _in_chase_box(ghost: Ghost) -> bool:
    """Return whether a ghost is inside the house target box."""
    return CHASE_BOX_MIN_X < ghost.x_pos < CHASE_BOX_MAX_X and CHASE_BOX_MIN_Y < ghost.y_pos < CHASE_BOX_MAX_Y


# Tính target ở chế độ bình thường: ưu tiên về hộp khi chết, ra khỏi hộp khi in_box, chase nếu thấy Pac-Man, ngược lại patrol/scatter.
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


# Trả về điểm tuần tra hiện tại trên bản đồ; xoay sang điểm khác nếu ma đã quá gần điểm hiện tại.
def _patrol_target(level: Level, ghost: Ghost, fallback_target: Point) -> Point:
    """Return the current whole-map patrol target."""
    patrol_cells = _patrol_cells(level, ghost)
    if not patrol_cells:
        return fallback_target

    ghost_cell = ghost._cell_from_point((ghost.center_x, ghost.center_y))
    # patrol_cells are already filtered to the ghost's reachable component,
    # so no per-cell A* check is needed — just skip targets that are too close.
    for _ in range(len(patrol_cells)):
        target_cell = patrol_cells[ghost._patrol_index % len(patrol_cells)]
        if Ghost._heuristic(ghost_cell, target_cell) > PATROL_REACHED_DISTANCE:
            return _point_from_cell(target_cell)
        ghost._patrol_index += 1

    return fallback_target


# Trả về danh sách cell tuần tra rải đều trên toàn bản đồ (có cache theo level + khả năng dùng cổng).
def _patrol_cells(level: Level, ghost: Ghost) -> list[Cell]:
    """Return passable patrol cells spread across the whole board."""
    cache_key = (id(level), ghost._can_use_gate())
    if ghost._patrol_cache_key == cache_key:
        return ghost._patrol_cells_cache

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

    if not cells:
        cells = [cell for cell in reachable if not _is_ghost_house_cell(cell)]

    ghost._patrol_cache_key = cache_key
    ghost._patrol_reachable = reachable
    ghost._patrol_cells_cache = cells
    return cells


# BFS từ vị trí ma để tìm tập cell có thể tới được (dùng để lọc patrol cells khả thi).
def _reachable_patrol_cells(level: Level, ghost: Ghost) -> set[Cell]:
    """Return all patrol cells reachable from the ghost's current cell."""
    cache_key = (id(level), ghost._can_use_gate())
    if ghost._patrol_cache_key == cache_key and ghost._patrol_reachable:
        return ghost._patrol_reachable

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


# Kiểm tra cell có nằm bên trong nhà ma không (tránh chọn làm điểm tuần tra).
def _is_ghost_house_cell(cell: Cell) -> bool:
    """Return whether a cell is inside the ghost house."""
    row, col = cell
    x_pos = col * CELL_W + CELL_W // 2
    y_pos = row * CELL_H + CELL_H // 2
    return GHOST_BOX_MIN_X < x_pos < GHOST_BOX_MAX_X and GHOST_BOX_MIN_Y < y_pos < GHOST_BOX_MAX_Y


# Đổi (row, col) sang tọa độ pixel tâm cell tương ứng.
def _point_from_cell(cell: Cell) -> Point:
    """Return the pixel center for a board cell."""
    row, col = cell
    return col * CELL_W + CELL_W // 2, row * CELL_H + CELL_H // 2


# Ma có phát hiện Pac-Man không: True nếu trong bán kính cảm nhận hoặc có line-of-sight thẳng hàng không bị tường chặn.
def _can_detect_player(level: Level, player: Player, ghost: Ghost) -> bool:
    """Return whether the ghost can currently detect Pac-Man."""
    ghost_cell = ghost._cell_from_point((ghost.center_x, ghost.center_y))
    player_cell = ghost._cell_from_point((player.center_x, player.center_y))
    distance = abs(ghost_cell[0] - player_cell[0]) + abs(ghost_cell[1] - player_cell[1])
    if distance <= GHOST_DETECTION_RADIUS_CELLS:
        return True
    return _has_line_of_sight(level, ghost_cell, player_cell)


# Ma và Pac-Man có cùng hàng/cột mà giữa không có tường nào không (đường ngắm thẳng).
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
