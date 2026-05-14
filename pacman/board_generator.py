"""Genetic board generator for random playable Pac-Man maps."""

from __future__ import annotations

import random
from collections import deque

from pacman.board import boards
from pacman.constants import (
    BOARD_COLS,
    BOARD_ROWS,
    BOTTOM_LEFT_WALL_TILE,
    BOTTOM_RIGHT_WALL_TILE,
    CELL_H,
    CELL_W,
    DOT_TILE,
    EMPTY_TILE,
    GATE_TILE,
    HORIZONTAL_WALL_TILE,
    PLAYER_CENTER_OFFSET_X,
    PLAYER_CENTER_OFFSET_Y,
    PLAYER_START_X,
    PLAYER_START_Y,
    POWER_DOT_TILE,
    TOP_LEFT_WALL_TILE,
    TOP_RIGHT_WALL_TILE,
    VERTICAL_WALL_TILE,
    VOID_TILE,
    WALL_TILE,
)

Level = list[list[int]]
Chromosome = list[list[int]]
Cell = tuple[int, int]
Shape = tuple[Cell, ...]
ClassicSlot = tuple[int, int, int, int, tuple[Shape, ...]]

HALF_COLS = BOARD_COLS // 2
PLAYER_CELL: Cell = (
    (PLAYER_START_Y + PLAYER_CENTER_OFFSET_Y) // CELL_H,
    (PLAYER_START_X + PLAYER_CENTER_OFFSET_X) // CELL_W,
)
GHOST_EXIT_CELL: Cell = (13, 14)
GATE_CELLS: tuple[Cell, Cell] = ((13, 14), (13, 15))
GHOST_HOUSE_ROWS = range(13, 17)
GHOST_HOUSE_COLS = range(12, 18)
PLAYER_SAFE_ROWS = range(23, 26)
PLAYER_SAFE_COLS = range(13, 17)
TUNNEL_ROW = 15
TUNNEL_LEFT_COLS = range(0, 7)
TUNNEL_RIGHT_COLS = range(23, 30)
SPINE_COLS = (14, 15)
SPINE_ROWS = (6, 11, 15, 20, 24)
# Cols just outside ghost house walls; guaranteed path so upper/lower halves stay connected.
GHOST_BYPASS_ROWS = range(12, 18)
GHOST_BYPASS_COLS = (11, 18)

TARGET_PATH_DENSITY = 0.38
DEFAULT_POPULATION_SIZE = 20
DEFAULT_GENERATIONS = 5
TOURNAMENT_SIZE = 4
MUTATION_RATE = 0.4
CROSSOVER_RATE = 0.9
MIN_GHOST_DISTANCE = 12
MIN_EARLY_STOP_GENERATION = 3
EARLY_STOP_SCORE = -7_500

LAST_GENERATION_INFO: dict[str, float | int | bool | None] = {
    "seed": None,
    "fitness": None,
    "playable": False,
    "dead_ends": None,
}


def _solid_rect(height: int, width: int) -> Shape:
    """Return a filled rectangular wall block."""
    return tuple((row, col) for row in range(height) for col in range(width))


def _offset(shape: Shape, row_offset: int, col_offset: int) -> Shape:
    """Move a relative wall shape inside its slot."""
    return tuple((row + row_offset, col + col_offset) for row, col in shape)


def _hollow_rect(height: int, width: int) -> Shape:
    """Return only the outline of a rectangle (interior is path)."""
    if height < 3 or width < 3:
        return _solid_rect(height, width)
    cells = []
    for r in range(height):
        for c in range(width):
            if r == 0 or r == height - 1 or c == 0 or c == width - 1:
                cells.append((r, c))
    return tuple(cells)


def _l_shape(height: int, width: int, corner: str = "bl") -> Shape:
    """L-shape: one full column + one full row at the chosen corner.
    corner ∈ {'tl', 'tr', 'bl', 'br'}.
    """
    cells = set()
    if corner in ("tl", "tr"):
        for c in range(width):
            cells.add((0, c))  # top row
    else:
        for c in range(width):
            cells.add((height - 1, c))  # bottom row
    if corner in ("tl", "bl"):
        for r in range(height):
            cells.add((r, 0))  # left col
    else:
        for r in range(height):
            cells.add((r, width - 1))  # right col
    return tuple(sorted(cells))


def _t_shape(height: int, width: int, orient: str = "down") -> Shape:
    """T-shape: full bar + perpendicular stem.
    orient ∈ {'down','up','left','right'} — direction the stem points to.
    """
    cells = set()
    if orient in ("down", "up"):
        # horizontal bar
        bar_row = 0 if orient == "down" else height - 1
        for c in range(width):
            cells.add((bar_row, c))
        stem_col = width // 2
        for r in range(height):
            cells.add((r, stem_col))
    else:
        # vertical bar
        bar_col = 0 if orient == "right" else width - 1
        for r in range(height):
            cells.add((r, bar_col))
        stem_row = height // 2
        for c in range(width):
            cells.add((stem_row, c))
    return tuple(sorted(cells))


def _bar(height: int, width: int, side: str = "bottom") -> Shape:
    """Single-cell-thick bar on one edge.
    side ∈ {'top','bottom','left','right'}.
    """
    if side == "top":
        return tuple((0, c) for c in range(width))
    if side == "bottom":
        return tuple((height - 1, c) for c in range(width))
    if side == "left":
        return tuple((r, 0) for r in range(height))
    return tuple((r, width - 1) for r in range(height))


def _step(height: int, width: int) -> Shape:
    """Staircase shape — fills bottom-left triangle."""
    cells = []
    for r in range(height):
        for c in range(width):
            if c <= int(r * width / max(1, height)):
                cells.append((r, c))
    return tuple(cells)


CLASSIC_WALL_SLOTS: tuple[ClassicSlot, ...] = (
    (3, 3, 3, 4, (
        _solid_rect(3, 4),
        _offset(_solid_rect(3, 3), 0, 0),
        _offset(_solid_rect(2, 4), 0, 0),
        _hollow_rect(3, 4),
        _l_shape(3, 4, "bl"),
        _t_shape(3, 4, "down"),
        _offset(_solid_rect(2, 3), 0, 1),
    )),
    (3, 8, 3, 5, (
        _solid_rect(3, 5),
        _offset(_solid_rect(3, 4), 0, 1),
        _offset(_solid_rect(2, 5), 1, 0),
        _hollow_rect(3, 5),
        _l_shape(3, 5, "br"),
        _t_shape(3, 5, "up"),
        _offset(_solid_rect(2, 3), 0, 1),
    )),
    (7, 3, 2, 4, (
        _solid_rect(2, 4),
        _offset(_solid_rect(2, 3), 0, 0),
        _offset(_solid_rect(1, 4), 0, 0),
        _bar(2, 4, "bottom"),
        _offset(_solid_rect(2, 2), 0, 0),
        _offset(_solid_rect(2, 2), 0, 2),
        _t_shape(2, 4, "down"),
    )),
    (7, 8, 4, 2, (
        _solid_rect(4, 2),
        _offset(_solid_rect(3, 2), 1, 0),
        _offset(_solid_rect(4, 1), 0, 0),
        _offset(_solid_rect(4, 1), 0, 1),
        _l_shape(4, 2, "tr"),
        _bar(4, 2, "left"),
        _offset(_solid_rect(2, 2), 1, 0),
    )),
    (10, 1, 5, 6, (
        _solid_rect(5, 6),
        _offset(_solid_rect(4, 6), 0, 0),
        _offset(_solid_rect(5, 5), 0, 1),
        _hollow_rect(5, 6),
        _l_shape(5, 6, "tr"),
        _t_shape(5, 6, "right"),
        _offset(_solid_rect(3, 5), 1, 1),
    )),
    (10, 9, 4, 4, (
        _solid_rect(4, 4),
        _offset(_solid_rect(3, 4), 0, 0),
        _offset(_solid_rect(4, 3), 0, 0),
        _hollow_rect(4, 4),
        _l_shape(4, 4, "tl"),
        _t_shape(4, 4, "left"),
        _offset(_solid_rect(2, 3), 1, 0),
    )),
    (17, 1, 4, 6, (
        _solid_rect(4, 6),
        _offset(_solid_rect(4, 5), 0, 1),
        _offset(_solid_rect(3, 6), 1, 0),
        _hollow_rect(4, 6),
        _l_shape(4, 6, "br"),
        _t_shape(4, 6, "right"),
        _offset(_solid_rect(2, 5), 1, 1),
    )),
    (17, 9, 4, 4, (
        _solid_rect(4, 4),
        _offset(_solid_rect(3, 4), 1, 0),
        _offset(_solid_rect(4, 3), 0, 0),
        _hollow_rect(4, 4),
        _l_shape(4, 4, "bl"),
        _t_shape(4, 4, "left"),
        _offset(_solid_rect(2, 3), 0, 0),
    )),
    (22, 3, 2, 4, (
        _solid_rect(2, 4),
        _offset(_solid_rect(2, 3), 0, 0),
        _offset(_solid_rect(1, 4), 1, 0),
        _bar(2, 4, "top"),
        _offset(_solid_rect(2, 2), 0, 0),
        _offset(_solid_rect(2, 2), 0, 2),
        _t_shape(2, 4, "up"),
    )),
    (22, 8, 2, 5, (
        _solid_rect(2, 5),
        _offset(_solid_rect(2, 4), 0, 1),
        _offset(_solid_rect(1, 5), 0, 0),
        _bar(2, 5, "bottom"),
        _offset(_solid_rect(2, 3), 0, 0),
        _offset(_solid_rect(2, 3), 0, 2),
        _t_shape(2, 5, "down"),
    )),
    (25, 1, 2, 6, (
        _solid_rect(2, 6),
        _offset(_solid_rect(2, 5), 0, 1),
        _offset(_solid_rect(1, 6), 0, 0),
        _bar(2, 6, "top"),
        _offset(_solid_rect(2, 3), 0, 0),
        _offset(_solid_rect(2, 3), 0, 3),
        _l_shape(2, 6, "tl"),
    )),
    (25, 8, 2, 5, (
        _solid_rect(2, 5),
        _offset(_solid_rect(2, 4), 0, 0),
        _offset(_solid_rect(1, 5), 1, 0),
        _bar(2, 5, "bottom"),
        _offset(_solid_rect(2, 3), 0, 0),
        _offset(_solid_rect(2, 3), 0, 2),
        _l_shape(2, 5, "br"),
    )),
    (28, 3, 2, 10, (
        _solid_rect(2, 10),
        _offset(_solid_rect(2, 8), 0, 1),
        _offset(_solid_rect(1, 10), 0, 0),
        _bar(2, 10, "top"),
        _bar(2, 10, "bottom"),
        _hollow_rect(2, 10),
        _t_shape(2, 10, "down"),
    )),
)

CLASSIC_ROW_BANDS: tuple[tuple[int, int], ...] = (
    (0, 7),
    (7, 13),
    (13, 18),
    (18, 25),
    (25, BOARD_ROWS),
)


def generate_board(
    seed: int | None = None,
    population_size: int = DEFAULT_POPULATION_SIZE,
    generations: int = DEFAULT_GENERATIONS,
) -> Level:
    """Generate a random playable board using a genetic algorithm."""
    rng = random.Random(seed)
    population = [_random_chromosome(rng) for _ in range(population_size)]

    best_board = _fallback_board()
    best_score = -1_000_000.0
    playable_candidates: list[tuple[float, Level]] = []

    for generation in range(generations):
        scored: list[tuple[float, Chromosome]] = []
        for chrom in population:
            board = decode_chromosome(chrom)
            fitness = score_board(board)
            scored.append((fitness, chrom))
            if fitness > best_score:
                best_score = fitness
                best_board = board
            if is_playable(board):
                playable_candidates.append((fitness, board))

        if len(playable_candidates) >= MIN_EARLY_STOP_GENERATION and best_score >= EARLY_STOP_SCORE:
            break

        if generation == generations - 1:
            break

        next_population: list[Chromosome] = []
        while len(next_population) < population_size:
            parent_a = _select_parent(scored, rng)
            parent_b = _select_parent(scored, rng)
            if rng.random() < CROSSOVER_RATE:
                child = _uniform_crossover(parent_a, parent_b, rng)
            else:
                child = _clone_chromosome(parent_a)
            _mutate(child, rng)
            next_population.append(child)
        population = next_population

    if playable_candidates:
        playable_candidates.sort(key=lambda item: item[0], reverse=True)
        top_count = min(5, len(playable_candidates))
        best_score, best_board = rng.choice(playable_candidates[:top_count])

    playable = is_playable(best_board)
    LAST_GENERATION_INFO["seed"] = seed
    LAST_GENERATION_INFO["fitness"] = best_score
    LAST_GENERATION_INFO["playable"] = playable
    if playable:
        LAST_GENERATION_INFO["dead_ends"] = _dead_end_count(best_board, _bfs_board(best_board, PLAYER_CELL)[0])
    else:
        LAST_GENERATION_INFO["dead_ends"] = None
    if playable:
        return best_board
    return _fallback_board()


def decode_chromosome(chromosome: Chromosome) -> Level:
    """Decode a half-board chromosome into a full Pac-Man tile map."""
    logical = _chromosome_to_logical(chromosome)
    _repair_connectivity(logical)
    _remove_dead_end_paths(logical)
    board = _logical_to_tiles(logical)
    _place_power_pellets(board)
    return board


def score_board(board: Level) -> float:
    """Return a weighted fitness score for map quality and playability."""
    if not _has_valid_shape(board):
        return -1_000_000.0

    reachable, distances = _bfs_board(board, PLAYER_CELL)
    ghost_reachable, _ = _bfs_board(board, PLAYER_CELL, include_gate=True)
    walkable = _public_walkable_cells(board)
    pellets = _pellet_cells(board)
    unreachable_count = len(walkable - reachable)
    regions = _region_count(board, walkable)
    dead_ends = _dead_end_count(board, reachable)
    junctions = _junction_count(board, reachable)
    path_density = len(walkable) / (BOARD_ROWS * BOARD_COLS)
    corridor_length = _average_corridor_length(board)
    power_distance = _average_power_distance(board, distances)

    score = 0.0
    if not pellets or not pellets.issubset(reachable):
        score -= 100_000
    if GHOST_EXIT_CELL not in ghost_reachable:
        score -= 80_000
    score -= 5_000 * max(0, regions - 1)
    score -= 100 * unreachable_count
    score -= 900 * dead_ends
    score -= 80 * abs(path_density - TARGET_PATH_DENSITY) * 100
    score += 40 * min(junctions, 35)
    score += 20 * min(corridor_length, 12)
    score += 15 * power_distance
    ghost_distance = distances.get(GHOST_EXIT_CELL)
    if ghost_distance is None or ghost_distance < MIN_GHOST_DISTANCE:
        score -= 3_000
    return score


def is_playable(board: Level) -> bool:
    """Return whether the board satisfies hard gameplay constraints."""
    if not _has_valid_shape(board):
        return False
    if any(tile not in range(VOID_TILE + 1) for row in board for tile in row):
        return False
    if board[13][14] != GATE_TILE or board[13][15] != GATE_TILE:
        return False
    if board[13][12] != TOP_LEFT_WALL_TILE or board[13][17] != TOP_RIGHT_WALL_TILE:
        return False
    if board[16][12] != BOTTOM_LEFT_WALL_TILE or board[16][17] != BOTTOM_RIGHT_WALL_TILE:
        return False
    for col in (13, 16):
        if board[13][col] != HORIZONTAL_WALL_TILE or board[16][col] != HORIZONTAL_WALL_TILE:
            return False
    for row in range(14, 16):
        if board[row][12] != VERTICAL_WALL_TILE or board[row][17] != VERTICAL_WALL_TILE:
            return False
        for col in range(13, 17):
            if board[row][col] != EMPTY_TILE:
                return False
    if sum(tile == POWER_DOT_TILE for row in board for tile in row) != 4:
        return False
    reachable, _ = _bfs_board(board, PLAYER_CELL)
    ghost_reachable, _ = _bfs_board(board, PLAYER_CELL, include_gate=True)
    pellets = _pellet_cells(board)
    public_walkable = _public_walkable_cells(board)
    if _dead_end_count(board, reachable) > 0:
        return False
    return bool(pellets) and public_walkable.issubset(reachable) and GHOST_EXIT_CELL in ghost_reachable


def _random_chromosome(rng: random.Random) -> Chromosome:
    """Build a classic Pac-Man style half-board from block slots."""
    chromosome = _classic_template_chromosome()
    for _ in range(rng.randint(2, 5)):
        _apply_classic_slot_variant(chromosome, rng)
    _apply_fixed_mask_to_chromosome(chromosome)
    return chromosome


def _classic_template_chromosome() -> Chromosome:
    """Return the original maze's route layout, with decorative voids blocked."""
    route_cells, _ = _bfs_board(boards, PLAYER_CELL, include_gate=True)
    chromosome = [[0] * HALF_COLS for _ in range(BOARD_ROWS)]
    for row in range(BOARD_ROWS):
        for col in range(HALF_COLS):
            fixed = _fixed_logical_value(row, col)
            if fixed is not None:
                chromosome[row][col] = fixed
            elif (row, col) in route_cells and _is_walkable_tile(boards[row][col], include_gate=True):
                chromosome[row][col] = 0
            else:
                chromosome[row][col] = 1
    return chromosome


def _apply_classic_slot_variant(chromosome: Chromosome, rng: random.Random) -> None:
    """Replace one classic wall slot with a shape-level variant."""
    top, left, height, width, variants = rng.choice(CLASSIC_WALL_SLOTS)
    for row in range(top, min(top + height, BOARD_ROWS)):
        for col in range(left, min(left + width, HALF_COLS)):
            if _fixed_logical_value(row, col) is None:
                chromosome[row][col] = 0

    for row_delta, col_delta in rng.choice(variants):
        row = top + row_delta
        col = left + col_delta
        if 0 <= row < BOARD_ROWS and 0 <= col < HALF_COLS and _fixed_logical_value(row, col) is None:
            chromosome[row][col] = 1


def _apply_fixed_mask_to_chromosome(chromosome: Chromosome) -> None:
    """Restore immutable cells in a left-half chromosome."""
    for row in range(BOARD_ROWS):
        for col in range(HALF_COLS):
            fixed = _fixed_logical_value(row, col)
            if fixed is not None:
                chromosome[row][col] = fixed


def _clone_chromosome(chromosome: Chromosome) -> Chromosome:
    """Return a deep copy of a chromosome."""
    return [row[:] for row in chromosome]


def _select_parent(scored: list[tuple[float, Chromosome]], rng: random.Random) -> Chromosome:
    """Select a parent with tournament selection."""
    sample = rng.sample(scored, min(TOURNAMENT_SIZE, len(scored)))
    return max(sample, key=lambda item: item[0])[1]


def _uniform_crossover(parent_a: Chromosome, parent_b: Chromosome, rng: random.Random) -> Chromosome:
    """Combine two parents by whole row bands so wall blocks stay coherent."""
    child = [[0] * HALF_COLS for _ in range(BOARD_ROWS)]
    for start, stop in CLASSIC_ROW_BANDS:
        source = parent_a if rng.random() < 0.5 else parent_b
        for row in range(start, stop):
            child[row] = source[row][:]
    return child


def _mutate(chromosome: Chromosome, rng: random.Random) -> None:
    """Mutate one or two whole wall slots, not random single cells."""
    if rng.random() < MUTATION_RATE:
        _apply_classic_slot_variant(chromosome, rng)
    if rng.random() < MUTATION_RATE * 0.5:
        _apply_classic_slot_variant(chromosome, rng)
    _apply_fixed_mask_to_chromosome(chromosome)


def _chromosome_to_logical(chromosome: Chromosome) -> list[list[int]]:
    """Mirror the left-half chromosome and restore fixed cells."""
    logical = [[1 for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
    for row in range(BOARD_ROWS):
        for col in range(HALF_COLS):
            logical[row][col] = chromosome[row][col]
            logical[row][BOARD_COLS - 1 - col] = chromosome[row][col]
    _apply_fixed_mask(logical)
    return logical


def _apply_fixed_mask(logical: list[list[int]]) -> None:
    """Restore immutable path and wall regions."""
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            fixed = _fixed_logical_value(row, col)
            if fixed is not None:
                logical[row][col] = fixed


def _fixed_logical_value(row: int, col: int) -> int | None:
    """Return fixed logical value for a cell, or None when mutable."""
    if row == 0 or row == BOARD_ROWS - 1:
        return 1
    if col == 0 or col == BOARD_COLS - 1:
        return 0 if row == TUNNEL_ROW else 1
    if row == TUNNEL_ROW and (col in TUNNEL_LEFT_COLS or col in TUNNEL_RIGHT_COLS):
        return 0
    if row in GHOST_HOUSE_ROWS and col in GHOST_HOUSE_COLS:
        return 0
    if row in PLAYER_SAFE_ROWS and col in PLAYER_SAFE_COLS:
        return 0
    if row in GHOST_BYPASS_ROWS and col in GHOST_BYPASS_COLS:
        return 0
    return None


def _repair_connectivity(logical: list[list[int]]) -> None:
    """Connect isolated path regions by carving corridors on the left half only, then re-mirroring."""
    _apply_fixed_mask(logical)

    for _ in range(50):
        reachable = _bfs_logical(logical, PLAYER_CELL)
        # Only look at isolated cells in the left half so repairs stay symmetric.
        isolated = {
            (row, col)
            for row in range(BOARD_ROWS)
            for col in range(HALF_COLS)
            if logical[row][col] == 0
            and (row, col) not in reachable
            and _fixed_logical_value(row, col) is None
        }
        if not isolated:
            break
        path = _shortest_repair_path(logical, reachable, isolated)
        if not path:
            for row, col in isolated:
                if col < HALF_COLS and _fixed_logical_value(row, col) is None:
                    logical[row][col] = 1
        else:
            for row, col in path:
                if col < HALF_COLS and _fixed_logical_value(row, col) is None:
                    logical[row][col] = 0
        # Mirror left half to right half to preserve symmetry after each repair pass.
        for row in range(BOARD_ROWS):
            for col in range(HALF_COLS):
                logical[row][BOARD_COLS - 1 - col] = logical[row][col]
        _apply_fixed_mask(logical)


def _remove_dead_end_paths(logical: list[list[int]]) -> None:
    """Prune mutable cul-de-sacs into blocked wall interiors."""
    changed = True
    while changed:
        changed = False
        for row in range(1, BOARD_ROWS - 1):
            for col in range(BOARD_COLS):
                if logical[row][col] != 0 or _fixed_logical_value(row, col) is not None:
                    continue
                if _logical_walkable_degree(logical, row, col) <= 1:
                    logical[row][col] = 1
                    changed = True
        _apply_fixed_mask(logical)


def _logical_walkable_degree(logical: list[list[int]], row: int, col: int) -> int:
    """Return the number of neighboring path cells in the logical maze."""
    return sum(1 for nr, nc in _neighbors(row, col) if logical[nr][nc] == 0)


def _shortest_repair_path(
    logical: list[list[int]],
    reachable: set[Cell],
    isolated: set[Cell],
) -> list[Cell]:
    """Return the shortest mutable path from reachable cells to an isolated cell."""
    queue = deque(reachable)
    parents: dict[Cell, Cell | None] = {cell: None for cell in reachable}
    target = None
    while queue and target is None:
        row, col = queue.popleft()
        for next_cell in _neighbors(row, col):
            if next_cell in parents:
                continue
            fixed = _fixed_logical_value(next_cell[0], next_cell[1])
            if fixed == 1:
                continue
            parents[next_cell] = (row, col)
            if next_cell in isolated:
                target = next_cell
                break
            queue.append(next_cell)

    if target is None:
        return []

    path = []
    cursor: Cell | None = target
    while cursor is not None:
        path.append(cursor)
        cursor = parents[cursor]
    return path


def _logical_to_tiles(logical: list[list[int]]) -> Level:
    """Convert path/wall logic into renderable Pac-Man tile values."""
    board = [[DOT_TILE for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            if logical[row][col] == 0:
                board[row][col] = DOT_TILE
            elif _is_wall_void(logical, row, col):
                board[row][col] = VOID_TILE
            else:
                board[row][col] = _wall_tile(logical, row, col)

    _stamp_ghost_house(board)
    for col in list(TUNNEL_LEFT_COLS) + list(TUNNEL_RIGHT_COLS):
        board[TUNNEL_ROW][col] = EMPTY_TILE
    return board


def _stamp_ghost_house(board: Level) -> None:
    """Stamp a fixed, framed ghost house with a two-tile gate."""
    for row in GHOST_HOUSE_ROWS:
        for col in GHOST_HOUSE_COLS:
            board[row][col] = EMPTY_TILE

    board[13][12] = TOP_LEFT_WALL_TILE
    board[13][13] = HORIZONTAL_WALL_TILE
    board[13][14] = GATE_TILE
    board[13][15] = GATE_TILE
    board[13][16] = HORIZONTAL_WALL_TILE
    board[13][17] = TOP_RIGHT_WALL_TILE

    for row in range(14, 16):
        board[row][12] = VERTICAL_WALL_TILE
        board[row][17] = VERTICAL_WALL_TILE
        for col in range(13, 17):
            board[row][col] = EMPTY_TILE

    board[16][12] = BOTTOM_LEFT_WALL_TILE
    board[16][17] = BOTTOM_RIGHT_WALL_TILE
    for col in range(13, 17):
        board[16][col] = HORIZONTAL_WALL_TILE


def _wall_tile(logical: list[list[int]], row: int, col: int) -> int:
    """Choose a wall drawing tile based on neighboring wall cells."""
    up = _is_logical_wall(logical, row - 1, col)
    down = _is_logical_wall(logical, row + 1, col)
    left = _is_logical_wall(logical, row, col - 1)
    right = _is_logical_wall(logical, row, col + 1)
    if down and right and not up and not left:
        return TOP_LEFT_WALL_TILE
    if down and left and not up and not right:
        return TOP_RIGHT_WALL_TILE
    if up and right and not down and not left:
        return BOTTOM_LEFT_WALL_TILE
    if up and left and not down and not right:
        return BOTTOM_RIGHT_WALL_TILE
    if not left and right and (up or down):
        return VERTICAL_WALL_TILE
    if not right and left and (up or down):
        return VERTICAL_WALL_TILE
    if not up and down and (left or right):
        return HORIZONTAL_WALL_TILE
    if not down and up and (left or right):
        return HORIZONTAL_WALL_TILE
    if left or right:
        return HORIZONTAL_WALL_TILE
    if up or down:
        return VERTICAL_WALL_TILE
    return WALL_TILE


def _is_wall_void(logical: list[list[int]], row: int, col: int) -> bool:
    """Return whether a wall cell is a blocked black interior."""
    return (
        _is_logical_wall(logical, row - 1, col)
        and _is_logical_wall(logical, row + 1, col)
        and _is_logical_wall(logical, row, col - 1)
        and _is_logical_wall(logical, row, col + 1)
    )


def _is_logical_wall(logical: list[list[int]], row: int, col: int) -> bool:
    """Return whether a logical cell is a wall."""
    return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS and logical[row][col] == 1


def _place_power_pellets(board: Level) -> None:
    """Place four reachable power pellets in broad board quadrants."""
    reachable, _ = _bfs_board(board, PLAYER_CELL)
    candidates = [
        cell
        for cell in reachable
        if board[cell[0]][cell[1]] == DOT_TILE
        and cell[0] not in GHOST_HOUSE_ROWS
        and cell[0] != TUNNEL_ROW
    ]
    quadrants = [
        (lambda cell: cell[0] < 14 and cell[1] < 13, (2, 2)),
        (lambda cell: cell[0] < 14 and cell[1] >= 17, (2, BOARD_COLS - 3)),
        (lambda cell: cell[0] >= 18 and cell[1] < 13, (BOARD_ROWS - 3, 2)),
        (lambda cell: cell[0] >= 18 and cell[1] >= 17, (BOARD_ROWS - 3, BOARD_COLS - 3)),
    ]
    chosen: list[Cell] = []
    for quadrant, corner in quadrants:
        quadrant_cells = [cell for cell in candidates if quadrant(cell)]
        if quadrant_cells:
            chosen.append(
                min(quadrant_cells, key=lambda cell: abs(cell[0] - corner[0]) + abs(cell[1] - corner[1]))
            )
    if len(chosen) < 4:
        remaining = [cell for cell in candidates if cell not in chosen]
        corners = ((2, 2), (2, BOARD_COLS - 3), (BOARD_ROWS - 3, 2), (BOARD_ROWS - 3, BOARD_COLS - 3))
        remaining.sort(key=lambda cell: min(abs(cell[0] - row) + abs(cell[1] - col) for row, col in corners))
        chosen.extend(remaining[: 4 - len(chosen)])
    for row, col in chosen[:4]:
        board[row][col] = POWER_DOT_TILE


def _has_valid_shape(board: Level) -> bool:
    """Return whether the board has the expected dimensions."""
    return len(board) == BOARD_ROWS and all(len(row) == BOARD_COLS for row in board)


def _is_walkable_tile(tile: int, include_gate: bool = False) -> bool:
    """Return whether a tile can be traversed for generation checks."""
    return tile < WALL_TILE or (include_gate and tile == GATE_TILE)


def _walkable_cells(board: Level) -> set[Cell]:
    """Return all walkable cells in a board."""
    return {
        (row, col)
        for row in range(BOARD_ROWS)
        for col in range(BOARD_COLS)
        if _is_walkable_tile(board[row][col])
    }


def _public_walkable_cells(board: Level) -> set[Cell]:
    """Return walkable cells outside the ghost-house interior."""
    return {
        cell
        for cell in _walkable_cells(board)
        if not (cell[0] in GHOST_HOUSE_ROWS and cell[1] in GHOST_HOUSE_COLS)
    }


def _pellet_cells(board: Level) -> set[Cell]:
    """Return all dot and power pellet cells."""
    return {
        (row, col)
        for row in range(BOARD_ROWS)
        for col in range(BOARD_COLS)
        if board[row][col] in (DOT_TILE, POWER_DOT_TILE)
    }


def _region_count(board: Level, cells: set[Cell]) -> int:
    """Count connected walkable regions in the supplied cell set."""
    remaining = set(cells)
    regions = 0
    while remaining:
        regions += 1
        start = remaining.pop()
        queue = deque([start])
        while queue:
            row, col = queue.popleft()
            for next_cell in _neighbors(row, col):
                if next_cell in remaining and _is_walkable_tile(board[next_cell[0]][next_cell[1]]):
                    remaining.remove(next_cell)
                    queue.append(next_cell)
    return regions


def _bfs_board(board: Level, start: Cell, include_gate: bool = False) -> tuple[set[Cell], dict[Cell, int]]:
    """Run BFS over board walkable cells."""
    if not _is_walkable_tile(board[start[0]][start[1]], include_gate):
        return set(), {}
    queue = deque([start])
    seen = {start}
    distances = {start: 0}
    while queue:
        row, col = queue.popleft()
        for next_cell in _neighbors(row, col):
            nr, nc = next_cell
            if next_cell not in seen and _is_walkable_tile(board[nr][nc], include_gate):
                seen.add(next_cell)
                distances[next_cell] = distances[(row, col)] + 1
                queue.append(next_cell)
    return seen, distances


def _bfs_logical(logical: list[list[int]], start: Cell) -> set[Cell]:
    """Run BFS over logical path cells."""
    if logical[start[0]][start[1]] != 0:
        return set()
    queue = deque([start])
    seen = {start}
    while queue:
        row, col = queue.popleft()
        for next_cell in _neighbors(row, col):
            nr, nc = next_cell
            if next_cell not in seen and logical[nr][nc] == 0:
                seen.add(next_cell)
                queue.append(next_cell)
    return seen


def _neighbors(row: int, col: int) -> list[Cell]:
    """Return orthogonal in-bounds neighbors."""
    cells = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nr = row + dr
        nc = col + dc
        if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
            cells.append((nr, nc))
    if row == TUNNEL_ROW and col == 0:
        cells.append((row, BOARD_COLS - 1))
    elif row == TUNNEL_ROW and col == BOARD_COLS - 1:
        cells.append((row, 0))
    return cells


def _walkable_degree(board: Level, row: int, col: int) -> int:
    """Return the number of walkable neighbors for a cell."""
    return sum(1 for nr, nc in _neighbors(row, col) if _is_walkable_tile(board[nr][nc]))


def _dead_end_count(board: Level, reachable: set[Cell]) -> int:
    """Count reachable dead-end path cells."""
    return sum(1 for row, col in reachable if board[row][col] != GATE_TILE and _walkable_degree(board, row, col) <= 1)


def _junction_count(board: Level, reachable: set[Cell]) -> int:
    """Count reachable intersections."""
    return sum(1 for row, col in reachable if _walkable_degree(board, row, col) >= 3)


def _average_corridor_length(board: Level) -> float:
    """Estimate average straight corridor length."""
    lengths = []
    for row in range(BOARD_ROWS):
        run = 0
        for col in range(BOARD_COLS):
            if _is_walkable_tile(board[row][col]):
                run += 1
            elif run:
                if run > 1:
                    lengths.append(run)
                run = 0
        if run > 1:
            lengths.append(run)
    for col in range(BOARD_COLS):
        run = 0
        for row in range(BOARD_ROWS):
            if _is_walkable_tile(board[row][col]):
                run += 1
            elif run:
                if run > 1:
                    lengths.append(run)
                run = 0
        if run > 1:
            lengths.append(run)
    if not lengths:
        return 0.0
    return sum(lengths) / len(lengths)


def _average_power_distance(board: Level, distances: dict[Cell, int]) -> float:
    """Return average player distance to power pellets."""
    powers = [
        distances[(row, col)]
        for row in range(BOARD_ROWS)
        for col in range(BOARD_COLS)
        if board[row][col] == POWER_DOT_TILE and (row, col) in distances
    ]
    if not powers:
        return 0.0
    return sum(powers) / len(powers)


def _fallback_board() -> Level:
    """Return a copy of the default board."""
    return [row[:] for row in boards]
