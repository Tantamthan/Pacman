
from __future__ import annotations

import random
from collections import deque
from typing import TYPE_CHECKING

from pacman.constants import (
    BOARD_COLS,
    BOARD_ROWS,
    CELL_H,
    CELL_W,
    DIRECTIONS,
    DOT_TILE,
    DOWN,
    GHOST_CENTER_OFFSET,
    LEFT,
    PLAYER_CENTER_OFFSET_X,
    PLAYER_CENTER_OFFSET_Y,
    POWER_DOT_TILE,
    POWERUP_DURATION,
    RIGHT,
    UP,
    WALL_TILE,
)

if TYPE_CHECKING:
    from pacman.ghost import Ghost
    from pacman.player import Player

Level = list[list[int]]
Cell = tuple[int, int]

DIRECTION_DELTAS: dict[int, tuple[int, int]] = {
    RIGHT: (0, 1),
    LEFT: (0, -1),
    UP: (-1, 0),
    DOWN: (1, 0),
}
REVERSE: dict[int, int] = {RIGHT: LEFT, LEFT: RIGHT, UP: DOWN, DOWN: UP}

# Search parameters
DEFAULT_DEPTH = 2
DECISION_INTERVAL = 6
ACTIVE_GHOSTS = 2
UNREACHABLE_DISTANCE = BOARD_ROWS * BOARD_COLS

W_SCORE = 1.0
W_DOT_REMAINING = 8.0
W_NEAREST_DOT = 2.5
W_NEAREST_POWER = 1.0       
W_GHOST_DANGER_CLOSE = 300.0 # ↑ Tăng sợ ma sát mặt (was 200)
W_GHOST_DANGER_NEAR = 120.0  # ↑ x2 — react với ma trong dist <= 4 (was 60)
GHOST_DANGER_RANGE = 4       # ↑ Cảm nhận ma từ xa hơn (was 2)

# End-game push: when few dots remain, AI tends to circle around them
# because nearest-dot gradient is too weak compared to safety. Boost the
# gradient so Pac-Man commits to the last isolated dots.
ENDGAME_DOT_THRESHOLD = 15
ENDGAME_DOT_MULTIPLIER = 3.0
W_SCARED_GHOST = 250.0       # Nhiều điểm hơn cho việc săn ma sợ
W_EXPLORATION_PENALTY = 10.0 # Phạt cell đã thăm gần đây (Option A: 3 -> 10)
EXPLORATION_MEMORY = 200     # Số frame nhớ "đã thăm" (Option A: 80 -> 200)

# Anti-stagnation: if score hasn't increased for this many frames, kick
# Pac-Man with a random valid direction to break out of safe-loop traps.
STAGNATION_THRESHOLD = 300


CLUSTER_RADIUS = 5           # cells within this radius count as "cluster"
W_CLUSTER_NEAR = 1.5         # ↓ from 5 — avoid trapping at local max
W_CLUSTER_FAR = 0.5          # ↓ from 1.5
CLUSTER_RADIUS_FAR = 10      # broader radius for distant clusters

W_TARGET_BIAS = 0.0          # disabled: target bias hurt more than helped
W_TARGET_DENSITY = 3.0       # candidate-target scoring: dots near it
W_TARGET_GHOST_PENALTY = 20.0  # avoid targets close to ghosts
W_TARGET_VISIT_PENALTY = 5.0   # avoid recently visited targets
TARGET_REFRESH_INTERVAL = 60   # frames between target re-evaluations


class GameState:
    """Lightweight, hashable game state for expectimax search."""

    __slots__ = ("pacman", "ghosts", "ghost_dirs", "dots", "power_dots", "powerup_timer", "score")

    # Khởi tạo snapshot trạng thái game (vị trí Pac-Man + ma, dots còn lại, powerup, điểm) phục vụ search Expectimax.
    def __init__(
        self,
        pacman: Cell,
        ghosts: tuple[Cell, ...],
        ghost_dirs: tuple[int, ...],
        dots: frozenset[Cell],
        power_dots: frozenset[Cell],
        powerup_timer: int,
        score: int,
    ) -> None:
        self.pacman = pacman
        self.ghosts = ghosts
        self.ghost_dirs = ghost_dirs
        self.dots = dots
        self.power_dots = power_dots
        self.powerup_timer = powerup_timer
        self.score = score


class ExpectimaxAgent:
    """Expectimax-based Pac-Man controller.

    Usage:
        agent = ExpectimaxAgent(depth=2)
        direction = agent.get_action(player, ghosts, level)
    """

    # Khởi tạo agent Expectimax: depth tìm kiếm, các bộ đếm frame, cache action, distance map BFS, target A* và RNG.
    def __init__(self, depth: int = DEFAULT_DEPTH) -> None:
        self.depth = depth
        self._frame_counter = 0
        self._cached_action: int | None = None
        # Exploration memory: frame at which each cell was last visited.
        self._visit_frame: dict[Cell, int] = {}
        # BFS distance map from current pacman position — computed once
        # per get_action call, used in eval for accurate ghost danger
        # (Manhattan distance lies through walls).
        self._dist_from_pacman: dict[Cell, int] = {}
        # Anti-stagnation: track last score change so we can detect loops.
        self._last_score: int = 0
        self._last_score_change_frame: int = 0
        self._rng = random.Random()
        # Option C: A* target bias. The target is picked periodically and
        # injected into the Expectimax eval as a distance gradient.
        self._astar_target: Cell | None = None
        self._dist_from_target: dict[Cell, int] = {}
        self._last_target_frame: int = -TARGET_REFRESH_INTERVAL
        # Diagnostics
        self.mode_astar_count = 0       # target re-picks
        self.mode_expectimax_count = 0  # expectimax search runs

    # Cổng vào AI mỗi frame: cập nhật trạng thái, chống đứng yên (stagnation), tái dùng action cache, tính BFS + target rồi chạy Expectimax.
    def get_action(self, player: "Player", ghosts: list["Ghost"], level: Level) -> int:
        """Return the next direction Pac-Man should commit to."""
        self._frame_counter += 1
        # Track current cell as visited for exploration penalty.
        pacman_cell = (
            (player.y_pos + PLAYER_CENTER_OFFSET_Y) // CELL_H,
            (player.x_pos + PLAYER_CENTER_OFFSET_X) // CELL_W,
        )
        self._visit_frame[pacman_cell] = self._frame_counter

        # Track score changes — used to detect stagnation loops.
        if player.score != self._last_score:
            self._last_score = player.score
            self._last_score_change_frame = self._frame_counter
        stagnation = self._frame_counter - self._last_score_change_frame

        # Anti-stagnation kick: if score has been frozen for too long, the
        # agent has fallen into a "safe-loop" cycle. Force a random legal
        # direction to break out, then invalidate the cache.
        if stagnation >= STAGNATION_THRESHOLD:
            legal = [d for d, ok in enumerate(player.turns_allowed) if ok]
            if legal:
                kick = self._rng.choice(legal)
                self._cached_action = kick
                # Reset stagnation counter so we don't kick every frame.
                self._last_score_change_frame = self._frame_counter
                return kick

        # Re-use the cached decision while it remains legal.
        if (
            self._cached_action is not None
            and self._frame_counter % DECISION_INTERVAL != 0
            and player.turns_allowed[self._cached_action]
        ):
            return self._cached_action

        # Precompute true BFS distance + parent pointers from pacman.
        dist_field, parents = _bfs_with_parents(level, pacman_cell)
        self._dist_from_pacman = dist_field

        # Build ghost cell list (reused for target picking + eval).
        ghost_cells: list[Cell] = []
        for g in ghosts:
            if g.dead:
                continue
            gc = ((g.y_pos + GHOST_CENTER_OFFSET) // CELL_H,
                  (g.x_pos + GHOST_CENTER_OFFSET) // CELL_W)
            ghost_cells.append(gc)

        is_scared = player.powerup and player.power_counter < POWERUP_DURATION

        # ---- A* TARGET (refreshed periodically) ----
        # Invalidate target if eaten, unreachable, or stale.
        should_refresh = (
            self._astar_target is None
            or self._astar_target not in dist_field
            or self._astar_target == pacman_cell
            or self._frame_counter - self._last_target_frame >= TARGET_REFRESH_INTERVAL
        )
        if not should_refresh and not is_scared:
            tr, tc = self._astar_target
            if level[tr][tc] not in (DOT_TILE, POWER_DOT_TILE):
                should_refresh = True
        if should_refresh:
            self._astar_target = self._pick_target(
                level, pacman_cell, dist_field, ghost_cells, ghosts, is_scared
            )
            self._last_target_frame = self._frame_counter
            # Precompute distance field FROM the target so eval is O(1).
            if self._astar_target is not None:
                self._dist_from_target = _bfs_distance_field(level, self._astar_target)
            else:
                self._dist_from_target = {}
            self.mode_astar_count += 1

        # ---- Run Expectimax with target-bias-aware eval ----
        state = self._build_state(player, ghosts, level)
        action = self._best_action(state, level)
        if action is None:
            action = player.direction
        self._cached_action = action
        self.mode_expectimax_count += 1
        return action

    # ----- A* high-level planner (Option C) -----

    # Chọn (hoặc tái dùng) target chiến lược bằng A* rồi trả về hướng đi của bước đầu tiên trên path tới target.
    def _astar_action(
        self,
        level: Level,
        pacman_cell: Cell,
        dist_field: dict[Cell, int],
        parents: dict[Cell, Cell | None],
        ghost_cells: list[Cell],
        ghosts: list["Ghost"],
        player: "Player",
        is_scared: bool,
    ) -> int | None:
        """Pick or reuse an A* target and return the next-step direction."""
        # Invalidate target if it was eaten, became unreachable, or we hit it.
        if self._astar_target is not None:
            tr, tc = self._astar_target
            tile = level[tr][tc]
            if (
                self._astar_target not in dist_field
                or self._astar_target == pacman_cell
                or (not is_scared and tile not in (DOT_TILE, POWER_DOT_TILE))
            ):
                self._astar_target = None

        if self._astar_target is None:
            self._astar_target = self._pick_target(
                level, pacman_cell, dist_field, ghost_cells, ghosts, is_scared
            )

        if self._astar_target is None:
            return None

        first_step = _first_step_on_path(parents, pacman_cell, self._astar_target)
        if first_step is None:
            return None
        return _direction_between(pacman_cell, first_step)

    # Chọn cell mục tiêu có giá trị cao nhất: săn ma sợ khi có powerup; bình thường chấm điểm dot theo cụm/khoảng cách/risk ma.
    def _pick_target(
        self,
        level: Level,
        pacman_cell: Cell,
        dist_field: dict[Cell, int],
        ghost_cells: list[Cell],
        ghosts: list["Ghost"],
        is_scared: bool,
    ) -> Cell | None:
        """Choose the highest-value reachable target cell.

        Scared mode: aim at scared ghost cells (nearest = highest value).
        Normal mode: score each dot by cluster density / (dist + ghost risk).
        """
        if is_scared:
            best_g: tuple[Cell, float] | None = None
            for g in ghosts:
                if g.dead:
                    continue
                gc = ((g.y_pos + GHOST_CENTER_OFFSET) // CELL_H,
                      (g.x_pos + GHOST_CENTER_OFFSET) // CELL_W)
                d = dist_field.get(gc, UNREACHABLE_DISTANCE)
                if d >= UNREACHABLE_DISTANCE:
                    continue
                value = -d  # nearer = higher
                if best_g is None or value > best_g[1]:
                    best_g = (gc, value)
            if best_g is not None:
                return best_g[0]
            # else fall through to dot hunting

        # Collect candidate dots from the live board.
        dots: list[Cell] = []
        for r in range(BOARD_ROWS):
            row = level[r]
            for c in range(BOARD_COLS):
                if row[c] in (DOT_TILE, POWER_DOT_TILE):
                    dots.append((r, c))
        if not dots:
            return None

        best_value = float("-inf")
        best_cell: Cell | None = None
        # For each candidate dot, compute a composite value:
        #   + dots-near-candidate (cluster)
        #   - distance from pacman
        #   - 1/dist to each ghost (avoid going into danger)
        #   - visit penalty (skip recently-eaten regions)
        for cell in dots:
            d = dist_field.get(cell)
            if d is None:
                continue
            nearby = 0
            cr, cc = cell
            for tr, tc in dots:
                if abs(tr - cr) + abs(tc - cc) <= CLUSTER_RADIUS:
                    nearby += 1
            ghost_risk = 0.0
            for gr, gc in ghost_cells:
                gd = abs(gr - cr) + abs(gc - cc)
                ghost_risk += 1.0 / (gd + 1)
            visit_penalty = 0.0
            last = self._visit_frame.get(cell)
            if last is not None and self._frame_counter - last < EXPLORATION_MEMORY:
                visit_penalty = W_TARGET_VISIT_PENALTY
            value = (
                W_TARGET_DENSITY * nearby
                - d
                - W_TARGET_GHOST_PENALTY * ghost_risk
                - visit_penalty
            )
            if value > best_value:
                best_value = value
                best_cell = cell
        return best_cell

    # ----- State construction -----

    # Quét bản đồ và đối tượng game để dựng GameState gọn (cell Pac-Man, ma, hướng ma, dots, power dots, powerup_timer, score).
    @staticmethod
    def _build_state(player: "Player", ghosts: list["Ghost"], level: Level) -> GameState:
        pacman_cell = (
            (player.y_pos + PLAYER_CENTER_OFFSET_Y) // CELL_H,
            (player.x_pos + PLAYER_CENTER_OFFSET_X) // CELL_W,
        )
        ghost_cells = tuple(
            (
                (g.y_pos + GHOST_CENTER_OFFSET) // CELL_H,
                (g.x_pos + GHOST_CENTER_OFFSET) // CELL_W,
            )
            for g in ghosts
        )
        ghost_dirs = tuple(g.direction for g in ghosts)
        dots: set[Cell] = set()
        power_dots: set[Cell] = set()
        for r in range(BOARD_ROWS):
            row = level[r]
            for c in range(BOARD_COLS):
                tile = row[c]
                if tile == DOT_TILE:
                    dots.add((r, c))
                elif tile == POWER_DOT_TILE:
                    power_dots.add((r, c))
        powerup_timer = (
            max(0, POWERUP_DURATION - player.power_counter) if player.powerup else 0
        )
        return GameState(
            pacman_cell,
            ghost_cells,
            ghost_dirs,
            frozenset(dots),
            frozenset(power_dots),
            powerup_timer,
            player.score,
        )

    # ----- Expectimax search -----

    # Tầng MAX trên cùng của Expectimax: thử mọi action hợp lệ của Pac-Man và chọn cái có giá trị ước lượng cao nhất.
    def _best_action(self, state: GameState, level: Level) -> int | None:
        """Top-level MAX: pick the best Pac-Man action."""
        active_ghosts = self._pick_active_ghosts(state)
        best_value = float("-inf")
        best_action: int | None = None
        for action in self._legal_pacman_actions(state, level):
            child = self._apply_pacman(state, action)
            value = self._expectimax(
                child, level, depth=self.depth, agent_index=1, active_ghosts=active_ghosts
            )
            if value > best_value:
                best_value = value
                best_action = action
        return best_action

    # Chọn chỉ số của ACTIVE_GHOSTS con ma gần Pac-Man nhất để mở rộng làm chance node; các ma còn lại coi như đứng yên trong search.
    @staticmethod
    def _pick_active_ghosts(state: GameState) -> tuple[int, ...]:
        """Pick indexes of ghosts nearest to Pac-Man to expand as chance nodes.

        The rest are treated as stationary during search — keeps the tree
        small enough for 60 FPS while preserving expectimax semantics on
        the threats that actually matter.
        """
        order = sorted(
            range(len(state.ghosts)),
            key=lambda i: _manhattan(state.pacman, state.ghosts[i]),
        )
        return tuple(order[:ACTIVE_GHOSTS])

    # Đệ quy expectimax: tầng Pac-Man là MAX; tầng từng con ma là CHANCE (trung bình đều trên các action hợp lệ).
    def _expectimax(
        self,
        state: GameState,
        level: Level,
        depth: int,
        agent_index: int,
        active_ghosts: tuple[int, ...],
    ) -> float:
        """Recursive expectimax. agent 0 = Pac-Man (MAX), >=1 = ghost (CHANCE)."""
        if depth == 0 or self._is_terminal(state):
            return self._evaluate(state, level)

        if agent_index == 0:
            # Pac-Man — MAX node
            best = float("-inf")
            for action in self._legal_pacman_actions(state, level):
                child = self._apply_pacman(state, action)
                value = self._expectimax(child, level, depth - 1, 1, active_ghosts)
                if value > best:
                    best = value
            return best if best != float("-inf") else self._evaluate(state, level)

        # Ghost — CHANCE node, only for "active" (nearest) ghosts.
        ghost_slot = agent_index - 1
        if ghost_slot >= len(active_ghosts):
            # All chance nodes for this ply finished — back to Pac-Man.
            return self._expectimax(state, level, depth, 0, active_ghosts)

        ghost_idx = active_ghosts[ghost_slot]
        actions = self._legal_ghost_actions(state, ghost_idx, level)
        next_agent = agent_index + 1
        if not actions:
            return self._expectimax(state, level, depth, next_agent, active_ghosts)
        total = 0.0
        for action in actions:
            child = self._apply_ghost(state, ghost_idx, action)
            total += self._expectimax(child, level, depth, next_agent, active_ghosts)
        return total / len(actions)

    # ----- Successors / Actions -----

    # Liệt kê các hướng Pac-Man có thể đi từ cell hiện tại (cell kế bên không phải tường).
    def _legal_pacman_actions(self, state: GameState, level: Level) -> list[int]:
        actions: list[int] = []
        r, c = state.pacman
        for d in DIRECTIONS:
            dr, dc = DIRECTION_DELTAS[d]
            if _is_walkable_cell(level, r + dr, c + dc):
                actions.append(d)
        return actions

    # Liệt kê hướng hợp lệ cho 1 con ma: cấm quay đầu trừ khi đường cụt buộc phải đảo chiều.
    def _legal_ghost_actions(
        self, state: GameState, ghost_idx: int, level: Level
    ) -> list[int]:
        """Ghost may not reverse direction unless forced (dead end)."""
        gr, gc = state.ghosts[ghost_idx]
        ghost_dir = state.ghost_dirs[ghost_idx]
        forbidden = REVERSE.get(ghost_dir)
        actions: list[int] = []
        for d in DIRECTIONS:
            if d == forbidden:
                continue
            dr, dc = DIRECTION_DELTAS[d]
            if _is_walkable_cell(level, gr + dr, gc + dc):
                actions.append(d)
        if not actions and forbidden is not None:
            dr, dc = DIRECTION_DELTAS[forbidden]
            if _is_walkable_cell(level, gr + dr, gc + dc):
                actions.append(forbidden)
        return actions

    # Sinh GameState mới sau khi Pac-Man đi action: cập nhật cell, ăn dot/power dot, cộng điểm, giảm powerup_timer.
    @staticmethod
    def _apply_pacman(state: GameState, action: int) -> GameState:
        dr, dc = DIRECTION_DELTAS[action]
        new_cell = (state.pacman[0] + dr, state.pacman[1] + dc)
        new_dots = state.dots
        new_power = state.power_dots
        new_score = state.score
        new_powerup = state.powerup_timer
        if new_cell in state.dots:
            new_dots = state.dots - {new_cell}
            new_score += 10
        if new_cell in state.power_dots:
            new_power = state.power_dots - {new_cell}
            new_score += 50
            new_powerup = POWERUP_DURATION
        # Decay powerup roughly per ply.
        if new_powerup > 0:
            new_powerup = max(0, new_powerup - 30)
        return GameState(
            new_cell,
            state.ghosts,
            state.ghost_dirs,
            new_dots,
            new_power,
            new_powerup,
            new_score,
        )

    # Sinh GameState mới sau khi một con ma đi action: cập nhật vị trí và hướng của ma đó.
    @staticmethod
    def _apply_ghost(state: GameState, ghost_idx: int, action: int) -> GameState:
        dr, dc = DIRECTION_DELTAS[action]
        old_cell = state.ghosts[ghost_idx]
        new_ghosts = list(state.ghosts)
        new_ghosts[ghost_idx] = (old_cell[0] + dr, old_cell[1] + dc)
        new_dirs = list(state.ghost_dirs)
        new_dirs[ghost_idx] = action
        return GameState(
            state.pacman,
            tuple(new_ghosts),
            tuple(new_dirs),
            state.dots,
            state.power_dots,
            state.powerup_timer,
            state.score,
        )

    # ----- Terminal / Evaluation -----

    # Kiểm tra state có phải terminal: thắng khi hết dots, thua khi Pac-Man chạm ma mà không có powerup.
    @staticmethod
    def _is_terminal(state: GameState) -> bool:
        # Win: no dots/power dots remain
        if not state.dots and not state.power_dots:
            return True
        # Loss: Pac-Man and a non-scared ghost on the same cell
        if state.powerup_timer <= 0:
            for ghost in state.ghosts:
                if ghost == state.pacman:
                    return True
        return False

    # Hàm heuristic chấm điểm state (cao = tốt cho Pac-Man): cộng score, trừ dot còn lại + nearest dot, cụm dot, ghost danger, exploration, A* target bias.
    def _evaluate(self, state: GameState, level: Level) -> float:
        """Heuristic evaluation. Higher = better for Pac-Man."""
        # Terminal-style adjustments
        if not state.dots and not state.power_dots:
            return W_SCORE * state.score + 10_000  # win bonus
        if state.powerup_timer <= 0:
            for ghost in state.ghosts:
                if ghost == state.pacman:
                    return W_SCORE * state.score - 5_000  # death penalty

        score = W_SCORE * state.score
        # Strong push to consume dots.
        score -= W_DOT_REMAINING * len(state.dots)

        # Single pass over dots: compute (1) nearest dot distance and
        # (2) cluster density at two radii. The density terms pull
        # Pac-Man toward dot-rich regions instead of getting confused
        # by 1-2 scattered dots that are technically "nearest".
        targets = state.dots | state.power_dots
        if targets:
            pr, pc = state.pacman
            d_min = UNREACHABLE_DISTANCE
            near_count = 0
            far_count = 0
            for tr, tc in targets:
                d = abs(pr - tr) + abs(pc - tc)
                if d < d_min:
                    d_min = d
                if d <= CLUSTER_RADIUS:
                    near_count += 1
                elif d <= CLUSTER_RADIUS_FAR:
                    far_count += 1
            # End-game: amplify nearest-dot gradient so Pac-Man commits
            # to isolated final dots instead of orbiting them.
            nearest_weight = W_NEAREST_DOT
            if len(state.dots) + len(state.power_dots) < ENDGAME_DOT_THRESHOLD:
                nearest_weight *= ENDGAME_DOT_MULTIPLIER
            score -= nearest_weight * d_min
            score += W_CLUSTER_NEAR * near_count
            score += W_CLUSTER_FAR * far_count

        if state.power_dots and state.powerup_timer <= 0:
            d_power = min(_manhattan(state.pacman, p) for p in state.power_dots)
            score -= W_NEAREST_POWER * d_power

        # Ghost danger — use BFS distance (walls matter!). The pre-computed
        # map is from pacman's ROOT cell; at depth 2 the search-state cell is
        # at most 2 cells away, so the BFS value is a tight upper bound on
        # the true post-move distance.
        is_scared = state.powerup_timer > 0
        for ghost in state.ghosts:
            # Use true BFS distance through walls — Manhattan would let the
            # agent "see through" walls and underestimate threat in corridors.
            d = self._dist_from_pacman.get(ghost, UNREACHABLE_DISTANCE)
            if is_scared:
                score += W_SCARED_GHOST / max(1, d)
            else:
                if d <= 1:
                    score -= W_GHOST_DANGER_CLOSE
                elif d <= GHOST_DANGER_RANGE:
                    score -= W_GHOST_DANGER_NEAR / d

        # Exploration bonus — penalize the agent for camping in cells it
        # has visited very recently. This breaks the "safe-spawn loop".
        last_visit = self._visit_frame.get(state.pacman)
        if last_visit is not None:
            recency = self._frame_counter - last_visit
            if recency < EXPLORATION_MEMORY:
                # Closer to "now" = bigger penalty.
                score -= W_EXPLORATION_PENALTY * (EXPLORATION_MEMORY - recency) / EXPLORATION_MEMORY * 10

        # Option C: A* target bias. Strong gradient pulling Pac-Man toward
        # the strategically-picked target dot (computed once per refresh
        # interval — see get_action). Distances are pre-computed via BFS
        # from the target cell, so this is O(1) per eval.
        if self._astar_target is not None and self._dist_from_target:
            d_target = self._dist_from_target.get(state.pacman)
            if d_target is not None:
                score -= W_TARGET_BIAS * d_target
        return score


# ----- Helpers -----


# Kiểm tra cell có trong board và không phải tường (đi qua được).
def _is_walkable_cell(level: Level, row: int, col: int) -> bool:
    if not (0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS):
        return False
    return level[row][col] < WALL_TILE


# Khoảng cách Manhattan giữa 2 cell (nhanh, dùng làm heuristic/sắp xếp).
def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# BFS từ `start` ra mọi cell đi được; trả về dict {cell: khoảng_cách} (khoảng cách thật qua hành lang, không xuyên tường).
def _bfs_distance_field(level: Level, start: Cell) -> dict[Cell, int]:
    """Compute BFS distance from `start` to every walkable cell."""
    if not _is_walkable_cell(level, start[0], start[1]):
        return {}
    dist: dict[Cell, int] = {start: 0}
    queue: deque[Cell] = deque([start])
    while queue:
        cell = queue.popleft()
        d = dist[cell]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = cell[0] + dr, cell[1] + dc
            ncell = (nr, nc)
            if ncell in dist or not _is_walkable_cell(level, nr, nc):
                continue
            dist[ncell] = d + 1
            queue.append(ncell)
    return dist


# BFS từ `start` trả về cả khoảng cách và parent pointers để có thể truy ngược path tới bất kỳ cell nào.
def _bfs_with_parents(level: Level, start: Cell) -> tuple[dict[Cell, int], dict[Cell, Cell | None]]:
    """BFS from `start`, returning distance field AND parent pointers.

    Parents let us reconstruct the shortest path to any reachable cell:
        cur = target; while parents[cur] != start: cur = parents[cur]
        # `cur` is now the first step from `start` toward `target`.
    """
    if not _is_walkable_cell(level, start[0], start[1]):
        return {}, {}
    dist: dict[Cell, int] = {start: 0}
    parents: dict[Cell, Cell | None] = {start: None}
    queue: deque[Cell] = deque([start])
    while queue:
        cell = queue.popleft()
        d = dist[cell]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = cell[0] + dr, cell[1] + dc
            ncell = (nr, nc)
            if ncell in dist or not _is_walkable_cell(level, nr, nc):
                continue
            dist[ncell] = d + 1
            parents[ncell] = cell
            queue.append(ncell)
    return dist, parents


# Đi ngược parent chain từ target về start; trả về cell ngay sau start trên đường tới target (bước đầu tiên).
def _first_step_on_path(parents: dict[Cell, Cell | None], start: Cell, target: Cell) -> Cell | None:
    """Walk the parent chain from target back to start; return the cell adjacent to start."""
    if target not in parents or target == start:
        return None
    cur = target
    while parents.get(cur) is not None and parents[cur] != start:
        cur = parents[cur]
    return cur if parents.get(cur) == start else None


# Trả về hướng (RIGHT/LEFT/UP/DOWN) đi từ cell a sang cell b láng giềng trực giao.
def _direction_between(a: Cell, b: Cell) -> int | None:
    """Cardinal direction from `a` to its orthogonal neighbor `b`."""
    dr = b[0] - a[0]
    dc = b[1] - a[1]
    if dr == 1 and dc == 0:
        return DOWN
    if dr == -1 and dc == 0:
        return UP
    if dr == 0 and dc == 1:
        return RIGHT
    if dr == 0 and dc == -1:
        return LEFT
    return None


# BFS từ start tìm cell đầu tiên thuộc tập targets; trả về khoảng cách ngắn nhất hoặc UNREACHABLE_DISTANCE.
def _bfs_distance_multi(level: Level, start: Cell, targets: frozenset[Cell] | set[Cell]) -> int:
    """Shortest walkable distance from start to any cell in targets."""
    if start in targets:
        return 0
    if not _is_walkable_cell(level, start[0], start[1]):
        return UNREACHABLE_DISTANCE
    queue: deque[tuple[Cell, int]] = deque([(start, 0)])
    seen: set[Cell] = {start}
    while queue:
        (r, c), dist = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            ncell = (nr, nc)
            if ncell in seen or not _is_walkable_cell(level, nr, nc):
                continue
            if ncell in targets:
                return dist + 1
            seen.add(ncell)
            queue.append((ncell, dist + 1))
    return UNREACHABLE_DISTANCE