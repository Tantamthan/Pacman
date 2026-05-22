"""Template-based random board generator for Pac-Man using Genetic Algorithm."""

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
    "fitness": 0.0,
    "playable": True,
    "dead_ends": 0,
}

TUNNEL_ROW = 16
GRID_ROWS = 10
GRID_COLS = 4

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

def _is_logical_wall(logical: list[list[int]], row: int, col: int) -> bool:
    return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS and logical[row][col] == 1

def _wall_tile(logical: list[list[int]], row: int, col: int) -> int:
    up = _is_logical_wall(logical, row - 1, col)
    down = _is_logical_wall(logical, row + 1, col)
    left = _is_logical_wall(logical, row, col - 1)
    right = _is_logical_wall(logical, row, col + 1)
    if down and right and not up and not left: return TOP_LEFT_WALL_TILE
    if down and left and not up and not right: return TOP_RIGHT_WALL_TILE
    if up and right and not down and not left: return BOTTOM_LEFT_WALL_TILE
    if up and left and not down and not right: return BOTTOM_RIGHT_WALL_TILE
    if not left and right and (up or down): return VERTICAL_WALL_TILE
    if not right and left and (up or down): return VERTICAL_WALL_TILE
    if not up and down and (left or right): return HORIZONTAL_WALL_TILE
    if not down and up and (left or right): return HORIZONTAL_WALL_TILE
    if left or right: return HORIZONTAL_WALL_TILE
    if up or down: return VERTICAL_WALL_TILE
    return WALL_TILE

def _is_wall_void(logical: list[list[int]], row: int, col: int) -> bool:
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0: continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                if logical[nr][nc] == 0: return False
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
        for col in range(13, 17): board[row][col] = EMPTY_TILE
    board[16][12] = BOTTOM_LEFT_WALL_TILE
    board[16][17] = BOTTOM_RIGHT_WALL_TILE
    for col in range(13, 17): board[16][col] = HORIZONTAL_WALL_TILE

def is_ghost_area(r, c):
    return 3 <= r <= 5 and c >= 2

def build_logical_from_genes(genes: list[int]) -> list[list[int]]:
    """Xây dựng nửa map logic dựa trên chuỗi gien quyết định."""
    logical_half = [[0 for _ in range(15)] for _ in range(BOARD_ROWS)]
    
    # Tạo biên bao bọc cố định bên ngoài
    for r in range(BOARD_ROWS): logical_half[r][0] = 1
    for c in range(15):
        logical_half[0][c] = 1
        logical_half[BOARD_ROWS-1][c] = 1
    for r in range(BOARD_ROWS): logical_half[r][14] = 1

    grid = [[-1 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    shape_id = 0
    gene_idx = 0
    
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if grid[r][c] != -1: continue
            
            # Lấy shape dựa trên gene hiện tại (đảm bảo tính tuần tự tái tạo của GA)
            shape_pool_idx = genes[gene_idx % len(genes)] % len(SHAPES)
            gene_idx += 1
            shape = SHAPES[shape_pool_idx]
            
            fits = True
            for dr, dc in shape:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS) or grid[nr][nc] != -1:
                    fits = False
                    break
            
            if fits:
                in_ghost = any(is_ghost_area(r+dr, c+dc) for dr, dc in shape)
                has_4_5 = any(r+dr == 4 for dr, dc in shape) and any(r+dr == 5 for dr, dc in shape)
                if (in_ghost and len(shape) > 1) or has_4_5:
                    fits = False

            if fits:
                for dr, dc in shape: grid[r+dr][c+dc] = shape_id
            else:
                grid[r][c] = shape_id  # fallback về mảnh 1x1 nếu không vừa
            shape_id += 1

    # Map các block 2x2 lên lưới logical_half
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            sr, sc = 2 + r * 3, 2 + c * 3
            logical_half[sr][sc] = 1
            logical_half[sr+1][sc] = 1
            logical_half[sr][sc+1] = 1
            logical_half[sr+1][sc+1] = 1
            
            if c + 1 < GRID_COLS and grid[r][c] == grid[r][c+1]:
                logical_half[sr][sc+2] = 1
                logical_half[sr+1][sc+2] = 1
            if r + 1 < GRID_ROWS and grid[r][c] == grid[r+1][c]:
                logical_half[sr+2][sc] = 1
                logical_half[sr+2][sc+1] = 1

    # Đục các lối thông cố định quan trọng (Giữ nguyên cấu trúc gameplay gốc)
    for row in [4, 10, 22, 28]: logical_half[row][14] = 0
    logical_half[16][0] = 0
    logical_half[16][1] = 0
    logical_half[12][13] = 0
    logical_half[12][14] = 0
    logical_half[11][13] = 0

    # Đối xứng gương sang nửa bên phải
    logical = [[1 for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
    for r in range(BOARD_ROWS):
        for c in range(15):
            logical[r][c] = logical_half[r][c]
            logical[r][BOARD_COLS - 1 - c] = logical_half[r][c]

    logical[24][14] = 0
    logical[24][15] = 0
    return logical

def evaluate_fitness(logical: list[list[int]]) -> tuple[float, int, bool]:
    """Hàm Fitness đánh giá chất lượng map."""
    # 1. Flood fill kiểm tra tính kết nối toàn bộ đường đi
    start_pos = (24, 14)
    reachable = set()
    q = deque([start_pos])
    reachable.add(start_pos)
    
    total_walkable = 0
    dead_ends = 0
    wall_count = 0
    
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            if logical[r][c] == 0:
                total_walkable += 1
                # Tính toán ngõ cụt (ô trống có >= 3 hướng xung quanh là tường)
                walls_around = 0
                for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                    if _is_logical_wall(logical, r+dr, c+dc):
                        walls_around += 1
                if walls_around >= 3 and (r, c) != start_pos:
                    dead_ends += 1
            else:
                wall_count += 1
                
    while q:
        curr_r, curr_c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = curr_r + dr, curr_c + dc
            if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS and logical[nr][nc] == 0:
                if (nr, nc) not in reachable:
                    reachable.add((nr, nc))
                    q.append((nr, nc))

    # Tính toán tỷ lệ phần trăm map đi tới được
    connectivity = len(reachable) / total_walkable if total_walkable > 0 else 0
    playable = (connectivity == 1.0)
    
    # Tỷ lệ mật độ tường tối ưu lý tưởng cho Pacman (~38%)
    total_tiles = BOARD_ROWS * BOARD_COLS
    wall_ratio = wall_count / total_tiles
    wall_fitness = max(0, 1.0 - abs(wall_ratio - 0.38) * 3)

    # Điểm phạt ngõ cụt (Càng nhiều ngõ cụt map càng dở)
    dead_end_penalty = dead_ends * 5.0
    
    # Tính điểm tổng hợp
    fitness_score = (connectivity * 100.0) + (wall_fitness * 30.0) - dead_end_penalty
    return max(0.0, fitness_score), dead_ends, playable

class GeneticAlgorithm:
    """Bộ engine GA tinh chỉnh thế hệ map tối ưu."""
    def __init__(self, pop_size=20, generations=15, mutation_rate=0.15, rng=None):
        self.pop_size = pop_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.rng = rng if rng else random.Random()
        self.chromosome_len = GRID_ROWS * GRID_COLS

    def generate_individual(self) -> list[int]:
        return [self.rng.randint(0, 100) for _ in range(self.chromosome_len)]

    def crossover(self, parent1: list[int], parent2: list[int]) -> list[int]:
        # Crossover một điểm (Single-point crossover)
        cut = self.rng.randint(1, self.chromosome_len - 1)
        return parent1[:cut] + parent2[cut:]

    def mutate(self, individual: list[int]) -> list[int]:
        for i in range(self.chromosome_len):
            if self.rng.random() < self.mutation_rate:
                individual[i] = self.rng.randint(0, 100)
        return individual

    def evolve(self) -> list[int]:
        # Khởi tạo quần thể ban đầu
        population = [self.generate_individual() for _ in range(self.pop_size)]
        
        best_individual = population[0]
        best_fitness = -1.0

        for _ in range(self.generations):
            scored_pop = []
            for ind in population:
                logical = build_logical_from_genes(ind)
                fit, _, _ = evaluate_fitness(logical)
                scored_pop.append((fit, ind))
                
                if fit > best_fitness:
                    best_fitness = fit
                    best_individual = ind

            # Sắp xếp chọn lọc tự nhiên (Chọn tinh hoa - Roulette Wheel / Selection)
            scored_pop.sort(key=lambda x: x[0], reverse=True)
            elites = [ind for fit, ind in scored_pop[:2]] # Giữ lại 2 cá thể tốt nhất

            # Sinh sản thế hệ mới
            next_pop = list(elites)
            while len(next_pop) < self.pop_size:
                p1 = self.rng.choice(elites)
                p2 = self.rng.choice(population)
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                next_pop.append(child)
            
            population = next_pop

        return best_individual

def generate_board(seed: int | None = None, **kwargs) -> Level:
    rng = random.Random(seed)
    
    # Chạy thuật toán di truyền để tìm bộ gene sinh map tốt nhất
    ga = GeneticAlgorithm(pop_size=25, generations=20, mutation_rate=0.2, rng=rng)
    best_genes = ga.evolve()
    
    # Xây dựng lại bản đồ logic từ nhiễm sắc thể tốt nhất tìm được
    logical = build_logical_from_genes(best_genes)
    fitness, dead_ends, playable = evaluate_fitness(logical)
    
    # Lưu lại thông tin báo cáo của thuật toán
    LAST_GENERATION_INFO["seed"] = seed
    LAST_GENERATION_INFO["fitness"] = round(fitness, 2)
    LAST_GENERATION_INFO["playable"] = playable
    LAST_GENERATION_INFO["dead_ends"] = dead_ends

    # Quá trình chuyển đổi mảng logic thành các Asset Tile đồ họa hoàn chỉnh
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
    
    # Thiết lập vùng trống cho hai cửa đường hầm (Tunnels)
    for col in range(0, 5):
        board[16][col] = EMPTY_TILE
        board[16][BOARD_COLS - 1 - col] = EMPTY_TILE
        
    # Làm trống khu vực spawn của Pacman
    board[24][14] = EMPTY_TILE
    board[24][15] = EMPTY_TILE

    # Đặt 4 viên Power Dots ở 4 góc map chuẩn xác
    board[1][1] = POWER_DOT_TILE
    board[1][BOARD_COLS - 2] = POWER_DOT_TILE
    board[31][1] = POWER_DOT_TILE
    board[31][BOARD_COLS - 2] = POWER_DOT_TILE

    return board