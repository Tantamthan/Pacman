"""Template-based random board generator for Pac-Man."""

from __future__ import annotations

import random
from collections import deque

from pacman.constants import (
    BOARD_COLS,
    BOARD_ROWS,
    BOTTOM_LEFT_WALL_TILE,
    BOTTOM_RIGHT_WALL_TILE,
    DOT_TILE,
    EMPTY_TILE,
    GATE_TILE,
    HORIZONTAL_WALL_TILE,
    POWER_DOT_TILE,
    TOP_LEFT_WALL_TILE,
    TOP_RIGHT_WALL_TILE,
    VERTICAL_WALL_TILE,
    VOID_TILE,
    WALL_TILE,
)

Level = list[list[int]]

LAST_GENERATION_INFO: dict[str, float | int | bool | None] = {
    "seed": None,
    "fitness": 100.0,
    "playable": True,
    "dead_ends": 0,
}

TUNNEL_ROW = 16

def _is_logical_wall(logical: list[list[int]], row: int, col: int) -> bool:
    return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS and logical[row][col] == 1

def _wall_tile(logical: list[list[int]], row: int, col: int) -> int:
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
    # A wall is an interior void if and only if all 8 neighbors are walls.
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                if logical[nr][nc] == 0:
                    return False
    return True

def _stamp_ghost_house(board: Level) -> None:
    for row in range(13, 17):
        for col in range(12, 18):
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

def generate_board(seed: int | None = None, **kwargs) -> Level:
    rng = random.Random(seed)
    LAST_GENERATION_INFO["seed"] = seed
    
    # Grid sizes for template placement (each node is a 2x2 wall block)
    GRID_ROWS = 10
    GRID_COLS = 4
    
    # 0 = path, 1 = wall
    logical_half = [[0 for _ in range(15)] for _ in range(BOARD_ROWS)]
    
    # Border walls
    for r in range(BOARD_ROWS):
        logical_half[r][0] = 1
    for c in range(15):
        logical_half[0][c] = 1
        logical_half[BOARD_ROWS-1][c] = 1
    for r in range(BOARD_ROWS):
        logical_half[r][14] = 1  # Center dividing wall

    # Template shapes relative coordinates
    SHAPES = [
        [(0,0)], # 1x1
        [(0,0), (0,1)], # 1x2
        [(0,0), (1,0)], # 2x1
        [(0,0), (0,1), (0,2)], # 1x3
        [(0,0), (1,0), (2,0)], # 3x1
        [(0,0), (1,0), (1,1)], # L
        [(0,0), (0,1), (1,0)],
        [(0,0), (0,1), (1,1)],
        [(0,1), (1,0), (1,1)],
        [(0,0), (0,1), (0,2), (1,1)], # T
        [(1,0), (1,1), (1,2), (0,1)],
        [(0,0), (1,0), (2,0), (1,1)],
        [(0,1), (1,1), (2,1), (1,0)],
        [(0,0), (0,1), (1,0), (1,1)]  # 2x2
    ]
    
    def is_ghost_area(r, c):
        return 3 <= r <= 5 and c >= 2
        
    grid = [[-1 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    shape_id = 0
    nodes = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)]
    rng.shuffle(nodes)
    
    for r, c in nodes:
        if grid[r][c] != -1:
            continue
            
        available_shapes = list(SHAPES)
        rng.shuffle(available_shapes)
        placed = False
        
        for shape in available_shapes:
            fits = True
            for dr, dc in shape:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS):
                    fits = False
                    break
                if grid[nr][nc] != -1:
                    fits = False
                    break
            
            if not fits:
                continue
                
            in_ghost = any(is_ghost_area(r+dr, c+dc) for dr, dc in shape)
            if in_ghost and len(shape) > 1:
                continue
                
            has_4 = any(r+dr == 4 for dr, dc in shape)
            has_5 = any(r+dr == 5 for dr, dc in shape)
            if has_4 and has_5:
                continue # Do not block tunnel path at row 16
                
            for dr, dc in shape:
                grid[r+dr][c+dc] = shape_id
            shape_id += 1
            placed = True
            break
            
        if not placed:
            grid[r][c] = shape_id
            shape_id += 1

    # Map blocks to logical_half
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            sr = 2 + r * 3
            sc = 2 + c * 3
            # Draw 2x2 wall block
            logical_half[sr][sc] = 1
            logical_half[sr+1][sc] = 1
            logical_half[sr][sc+1] = 1
            logical_half[sr+1][sc+1] = 1
            
            # Connect right
            if c + 1 < GRID_COLS and grid[r][c] == grid[r][c+1]:
                logical_half[sr][sc+2] = 1
                logical_half[sr+1][sc+2] = 1
                
            # Connect down
            if r + 1 < GRID_ROWS and grid[r][c] == grid[r+1][c]:
                logical_half[sr+2][sc] = 1
                logical_half[sr+2][sc+1] = 1

    # Crossings at center wall
    crossings = [4, 10, 22, 28]
    for row in crossings:
        logical_half[row][14] = 0
        
    # Tunnel
    logical_half[16][0] = 0
    logical_half[16][1] = 0
    
    # Ghost house exit
    logical_half[12][13] = 0
    logical_half[12][14] = 0
    logical_half[11][13] = 0

    # Mirror
    logical = [[1 for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
    for r in range(BOARD_ROWS):
        for c in range(15):
            logical[r][c] = logical_half[r][c]
            logical[r][BOARD_COLS - 1 - c] = logical_half[r][c]

    # Ensure player start is clear in logical
    logical[24][14] = 0
    logical[24][15] = 0
    
    # Flood fill to find reachable dots from player start
    reachable = set()
    start_pos = (24, 14)
    q = deque([start_pos])
    reachable.add(start_pos)
    while q:
        curr_r, curr_c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = curr_r + dr, curr_c + dc
            if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                if logical[nr][nc] == 0:
                    if (nr, nc) not in reachable:
                        reachable.add((nr, nc))
                        q.append((nr, nc))
    
    # Fill unreachable dots as walls
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            if logical[r][c] == 0 and (r, c) not in reachable:
                logical[r][c] = 1

    # Convert to specific tiles
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
    
    if board[12][14] >= WALL_TILE: board[12][14] = DOT_TILE
    if board[12][15] >= WALL_TILE: board[12][15] = DOT_TILE
    
    # Tunnel tiles
    for col in range(0, 5):
        board[16][col] = EMPTY_TILE
        board[16][BOARD_COLS - 1 - col] = EMPTY_TILE
        
    # Player start space
    board[24][14] = EMPTY_TILE
    board[24][15] = EMPTY_TILE

    # Power dots
    board[1][1] = POWER_DOT_TILE
    board[1][BOARD_COLS - 2] = POWER_DOT_TILE
    board[31][1] = POWER_DOT_TILE
    board[31][BOARD_COLS - 2] = POWER_DOT_TILE

    return board
