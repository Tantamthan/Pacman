"""Template-based random board generator for Pac-Man driven by Genetic Algorithm."""

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

# Sửa lại danh sách SHAPES trong code của bạn:
SHAPES = [
    # --- KHỐI CƠ BẢN (Giữ lại để tạo khung) ---
    [(0,0), (0,1)],        # 1x2 Ngang
    [(0,0), (1,0)],        # 2x1 Dọc
    [(0,0), (0,1), (0,2)], # 1x3 Ngang (Hành lang dài)
    [(0,0), (1,0), (2,0)], # 3x1 Dọc (Hành lang dài)
    
    # --- KHỐI CHỮ T (Phá vỡ tính đơn điệu của hành lang) ---
    [(0,0), (0,1), (0,2), (1,1)], # T xuôi
    [(1,0), (1,1), (1,2), (0,1)], # T ngược
    [(0,0), (1,0), (2,0), (1,1)], # T quay phải
    [(0,1), (1,1), (2,1), (1,0)], # T quay trái

    # --- KHỐI CHỮ L DÀI (Bẻ góc mượt, bớt vuông vức hơn L ngắn) ---
    [(0,0), (1,0), (2,0), (2,1)], # L xuôi dài (Dọc 3, chân 2)
    [(0,1), (1,1), (2,1), (2,0)], # L ngược dài
    [(0,0), (0,1), (0,2), (1,0)], # L nằm ngang 
    [(0,0), (0,1), (0,2), (1,2)], # L nằm ngang ngược

    # --- KHỐI ZIG-ZAG / KHỐI NGOẰN NGOÈO (Vũ khí bí mật bớt vuông) ---
    # Những khối này tạo ra các đoạn rẽ nhánh so le, triệt tiêu cảm giác ô vuông bàn cờ
    [(0,0), (0,1), (1,1), (1,2)], # Khối bậc thang ngang (Z-shape)
    [(0,1), (0,2), (1,0), (1,1)], # Khối bậc thang ngang ngược
    [(0,0), (1,0), (1,1), (2,1)], # Khối bậc thang dọc
    [(0,1), (1,1), (1,0), (2,0)], # Khối bậc thang dọc ngược

    # --- KHỐI ĐƯỜNG TRƯỜNG DÀI (Bắt buộc phải có để map thông thoáng) ---
    [(0,0), (0,1), (0,2), (0,3)], # 1x4 Ngang cực dài
    [(0,0), (1,0), (2,0), (3,0)], # 4x1 Dọc cực dài
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
    """
    Xây dựng nửa map logic dựa trên chuỗi gien quyết định thứ tự ưu tiên hình khối.
    Đảm bảo 100% map đẹp nhờ việc bắt buộc sử dụng cấu trúc khối cố định từ SHAPES.
    """
    logical_half = [[0 for _ in range(15)] for _ in range(BOARD_ROWS)]
    
    # Tạo biên bao bọc cố định bên ngoài
    for r in range(BOARD_ROWS): logical_half[r][0] = 1
    for c in range(15):
        logical_half[0][c] = 1
        logical_half[BOARD_ROWS-1][c] = 1
    for r in range(BOARD_ROWS): logical_half[r][14] = 1

    grid = [[-1 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    shape_id = 0
    
    # Điền khối dựa theo chỉ thị trực tiếp từ chuỗi nhiễm sắc thể GA
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if grid[r][c] != -1: continue
            
            # Lấy chỉ số gene tương ứng với ô hiện tại
            gene_value = genes[r * GRID_COLS + c]
            shape = SHAPES[gene_value % len(SHAPES)]
            
            # Kiểm tra xem khối được gene chỉ định có đặt vừa tại đây không
            fits = True
            for dr, dc in shape:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < GRID_ROWS and 0 <= nc < GRID_COLS) or grid[nr][nc] != -1:
                    fits = False
                    break
            
            if fits:
                # Tránh can thiệp khu vực nhà ma hoặc chặn đường hầm
                in_ghost = any(is_ghost_area(r+dr, c+dc) for dr, dc in shape)
                has_4_5 = any(r+dr == 4 for dr, dc in shape) and any(r+dr == 5 for dr, dc in shape)
                if (in_ghost and len(shape) > 1) or has_4_5:
                    fits = False

            if fits:
                for dr, dc in shape:
                    grid[r+dr][c+dc] = shape_id
            else:
                # Nếu không vừa khối do gene chỉ định, ép đặt khối 1x1 để lấp đầy khoảng trống sạch sẽ
                grid[r][c] = shape_id
                
            shape_id += 1

    # Khai triển mảng khối lên lưới logical_half
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
                
            # 3. THAY ĐỔI CỐT LÕI: Ép các khối KHÁC ID dính liền vào nhau nếu gene chỉ định
            # Điều này giúp triệt tiêu các hành lang vụn 1 ô, gộp các khối rời rạc thành mảng lớn
            gene_glue = genes[r * GRID_COLS + c]
            if c + 1 < GRID_COLS and (gene_glue % 3 == 0): # 33% cơ hội gộp ngang với khối lân cận
                logical_half[sr][sc+2] = 1
                logical_half[sr+1][sc+2] = 1
            if r + 1 < GRID_ROWS and (gene_glue % 3 == 1): # 33% cơ hội gộp dọc với khối lân cận
                logical_half[sr+2][sc] = 1
                logical_half[sr+2][sc+1] = 1

    # Đục các lối thông cố định quan trọng
    #for row in [4, 10, 22, 28]: logical_half[row][14] = 0
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
    """Hàm Fitness tối ưu hóa cấu trúc đường đi thông minh."""
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

    # Tính toán tỷ lệ phần trăm kết nối liên thông đường đi
    connectivity = len(reachable) / total_walkable if total_walkable > 0 else 0
    playable = (connectivity == 1.0)
    
    # Đo lường mật độ phân bổ tường tối ưu của game (~35% - 43%)
    total_tiles = BOARD_ROWS * BOARD_COLS
    wall_ratio = wall_count / total_tiles
    wall_fitness = max(0, 1.0 - abs(wall_ratio - 0.39) * 4)

    # ĐIỂM THƯỞNG ĐƯỜNG ĐI DÀI (Khuyến khích các hành lang chạy mượt, liên kết tốt)
    path_flow_bonus = (total_walkable / total_tiles) * 50.0

    # Phạt nặng ngõ cụt để tránh kẹt ma
    dead_end_penalty = dead_ends * 15.0
    
    # Điểm phạt cực nặng nếu map không thể phá đảo (bị cô lập đường đi)
    unplayable_penalty = 0 if playable else 200.0

    fitness_score = (connectivity * 150.0) + (wall_fitness * 50.0) + path_flow_bonus - dead_end_penalty - unplayable_penalty
    return max(0.0, fitness_score), dead_ends, playable

class GeneticAlgorithm:
    """Bộ engine GA tiến hóa chuỗi định vị khối tường phối hợp bài bản."""
    def __init__(self, pop_size=30, generations=25, mutation_rate=0.1, rng=None):
        self.pop_size = pop_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.rng = rng if rng else random.Random()
        self.chromosome_len = GRID_ROWS * GRID_COLS

    def generate_individual(self) -> list[int]:
        # Mỗi gene lưu giá trị index cấu trúc hình khối từ 0 -> 99
        return [self.rng.randint(0, 99) for _ in range(self.chromosome_len)]

    def crossover(self, parent1: list[int], parent2: list[int]) -> list[int]:
        # Uniform Crossover (Trộn gien đồng đều): Giúp giữ lại các cụm tổ hợp khối tốt bất kể vị trí cắt
        child = []
        for g1, g2 in zip(parent1, parent2):
            child.append(g1 if self.rng.random() < 0.5 else g2)
        return child

    def mutate(self, individual: list[int]) -> list[int]:
        for i in range(self.chromosome_len):
            if self.rng.random() < self.mutation_rate:
                individual[i] = self.rng.randint(0, 99)
        return individual

    def evolve(self) -> list[int]:
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

            # Chọn lọc tự nhiên bằng Elitism (Top 4 cá thể tinh hoa đi tiếp)
            scored_pop.sort(key=lambda x: x[0], reverse=True)
            elites = [ind for fit, ind in scored_pop[:4]]

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
    
    # GA tối ưu hóa việc phân bổ tổ hợp khối đẹp
    ga = GeneticAlgorithm(pop_size=35, generations=30, mutation_rate=0.08, rng=rng)
    best_genes = ga.evolve()
    
    logical = build_logical_from_genes(best_genes)
    fitness, dead_ends, playable = evaluate_fitness(logical)
    
    LAST_GENERATION_INFO["seed"] = seed
    LAST_GENERATION_INFO["fitness"] = round(fitness, 2)
    LAST_GENERATION_INFO["playable"] = playable
    LAST_GENERATION_INFO["dead_ends"] = dead_ends

    # Render tài nguyên đồ họa gạch tường bo góc mượt mà lên màn hình
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
    
    for col in range(0, 5):
        board[16][col] = EMPTY_TILE
        board[16][BOARD_COLS - 1 - col] = EMPTY_TILE
        
    board[24][14] = EMPTY_TILE
    board[24][15] = EMPTY_TILE

    board[1][1] = POWER_DOT_TILE
    board[1][BOARD_COLS - 2] = POWER_DOT_TILE
    board[31][1] = POWER_DOT_TILE
    board[31][BOARD_COLS - 2] = POWER_DOT_TILE

    return board