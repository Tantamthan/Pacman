"""Rendering helpers for the Pac-Man game."""

from __future__ import annotations

import pygame

from pacman.constants import (
    ARC_HALF_RATIO,
    BLACK,
    BOTTOM_LEFT_WALL_TILE,
    BOTTOM_RIGHT_WALL_TILE,
    BLUE,
    CELL_H,
    CELL_W,
    DARK_GRAY,
    DOT_RADIUS,
    DOT_TILE,
    GREEN,
    GHOST_CENTER_OFFSET,
    LIFE_IMAGE_SIZE,
    LIFE_SPACING,
    LIFE_START_X,
    LIFE_Y,
    MESSAGE_INNER_RECT,
    MESSAGE_OUTER_RECT,
    MESSAGE_POS,
    MESSAGE_RADIUS,
    PLAYER_CENTER_OFFSET_X,
    PLAYER_CENTER_OFFSET_Y,
    POWER_DOT_RADIUS,
    POWER_DOT_TILE,
    POWERUP_INDICATOR_POS,
    POWERUP_INDICATOR_RADIUS,
    RED,
    SCORE_POS,
    GATE_TILE,
    HORIZONTAL_WALL_TILE,
    TOP_LEFT_WALL_TILE,
    TOP_RIGHT_WALL_TILE,
    VERTICAL_WALL_TILE,
    WALL_WIDTH,
    WHITE,
    WIDTH,
    HEIGHT,
)
from pacman.player import Player

# Per-ghost colors and names used by the debug overlay.
_GHOST_PATH_COLORS: tuple[tuple[int, int, int], ...] = (
    (255, 80, 80),    # Blinky – red
    (80, 200, 255),   # Inky   – cyan
    (255, 130, 200),  # Pinky  – pink
    (255, 165, 0),    # Clyde  – orange
)
_GHOST_NAMES: tuple[str, ...] = ("Blinky", "Inky", "Pinky", "Clyde")

Level = list[list[int]]


def draw_score(screen: pygame.Surface, font: pygame.font.Font, player: Player) -> None:
    """Draw the current score."""
    score_text = font.render(f"Score: {player.score}", True, WHITE)
    screen.blit(score_text, SCORE_POS)


def draw_misc(
    screen: pygame.Surface,
    font: pygame.font.Font,
    player: Player,
    player_images: list[pygame.Surface],
    game_over: bool,
    game_won: bool,
) -> None:

    draw_score(screen, font, player)
    if player.powerup:
        pygame.draw.circle(screen, BLUE, POWERUP_INDICATOR_POS, POWERUP_INDICATOR_RADIUS)
    for i in range(player.lives):
        life_image = pygame.transform.scale(player_images[0], LIFE_IMAGE_SIZE)
        screen.blit(life_image, (LIFE_START_X + i * LIFE_SPACING, LIFE_Y))
    if game_over:
        pygame.draw.rect(screen, WHITE, MESSAGE_OUTER_RECT, 0, MESSAGE_RADIUS)
        pygame.draw.rect(screen, DARK_GRAY, MESSAGE_INNER_RECT, 0, MESSAGE_RADIUS)
        gameover_text = font.render("Game over! Space bar to restart!", True, RED)
        screen.blit(gameover_text, MESSAGE_POS)
    if game_won:
        pygame.draw.rect(screen, WHITE, MESSAGE_OUTER_RECT, 0, MESSAGE_RADIUS)
        pygame.draw.rect(screen, DARK_GRAY, MESSAGE_INNER_RECT, 0, MESSAGE_RADIUS)
        gameover_text = font.render("Victory! Space bar to restart!", True, GREEN)
        screen.blit(gameover_text, MESSAGE_POS)


def draw_loading(screen: pygame.Surface, font: pygame.font.Font, seed: int) -> None:

    screen.fill(BLACK)
    loading_text = font.render("Generating board...", True, WHITE)
    seed_text = font.render(f"Seed: {seed}", True, WHITE)
    screen.blit(loading_text, (WIDTH // 2 - loading_text.get_width() // 2, HEIGHT // 2 - 20))
    screen.blit(seed_text, (WIDTH // 2 - seed_text.get_width() // 2, HEIGHT // 2 + 15))


def build_wall_surface(level: Level, color: str) -> pygame.Surface:
    """Pre-render all static wall/gate tiles to a Surface for fast blitting each frame."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    for row_idx, row in enumerate(level):
        for col_idx, tile in enumerate(row):
            if tile in (DOT_TILE, POWER_DOT_TILE, 0):
                continue
            x = col_idx * CELL_W
            y = row_idx * CELL_H
            
            if tile >= 3 and tile != GATE_TILE and tile != 10:
                rows = len(level)
                cols = len(level[0])
                
                # Check for neighbors (Consider VOID_TILE 10 as a wall for connectivity)
                is_wall_up = row_idx > 0 and level[row_idx - 1][col_idx] >= 3 and level[row_idx - 1][col_idx] != GATE_TILE
                is_wall_down = row_idx < rows - 1 and level[row_idx + 1][col_idx] >= 3 and level[row_idx + 1][col_idx] != GATE_TILE
                is_wall_left = col_idx > 0 and level[row_idx][col_idx - 1] >= 3 and level[row_idx][col_idx - 1] != GATE_TILE
                is_wall_right = col_idx < cols - 1 and level[row_idx][col_idx + 1] >= 3 and level[row_idx][col_idx + 1] != GATE_TILE
                
                # Tunnel wrap logic
                if row_idx == 16:
                    if col_idx == 0 and level[row_idx][cols - 1] >= 3: is_wall_left = True
                    if col_idx == cols - 1 and level[row_idx][0] >= 3: is_wall_right = True

                # Thêm offset để các đường kẻ đè lên nhau ở góc, tạo thành góc vuông liền mạch
                offset = WALL_WIDTH // 2 + 1

                # Draw edges ONLY if there is no wall neighbor in that direction
                if not is_wall_up:
                    pygame.draw.line(surf, color, (x - offset, y), (x + CELL_W + offset, y), WALL_WIDTH)
                if not is_wall_down:
                    pygame.draw.line(surf, color, (x - offset, y + CELL_H), (x + CELL_W + offset, y + CELL_H), WALL_WIDTH)
                if not is_wall_left:
                    pygame.draw.line(surf, color, (x, y - offset), (x, y + CELL_H + offset), WALL_WIDTH)
                if not is_wall_right:
                    pygame.draw.line(surf, color, (x + CELL_W, y - offset), (x + CELL_W, y + CELL_H + offset), WALL_WIDTH)
            elif tile == GATE_TILE:
                cy = y + ARC_HALF_RATIO * CELL_H
                pygame.draw.line(surf, WHITE, (x, cy), (x + CELL_W, cy), WALL_WIDTH)
    return surf


def draw_dots(screen: pygame.Surface, level: Level, flicker: bool) -> None:
    """Draw only dots and power-dots (changes each frame as they are eaten)."""
    for row_idx, row in enumerate(level):
        for col_idx, tile in enumerate(row):
            if tile == DOT_TILE:
                x = col_idx * CELL_W
                y = row_idx * CELL_H
                center = (x + ARC_HALF_RATIO * CELL_W, y + ARC_HALF_RATIO * CELL_H)
                pygame.draw.circle(screen, WHITE, center, DOT_RADIUS)
            elif tile == POWER_DOT_TILE and not flicker:
                x = col_idx * CELL_W
                y = row_idx * CELL_H
                center = (x + ARC_HALF_RATIO * CELL_W, y + ARC_HALF_RATIO * CELL_H)
                pygame.draw.circle(screen, WHITE, center, POWER_DOT_RADIUS)


def draw_board(screen: pygame.Surface, level: Level, flicker: bool, color: str) -> None:
    """Draw the board walls, dots, power dots, and gate."""
    for row_idx, row in enumerate(level):
        for col_idx, tile in enumerate(row):
            x = col_idx * CELL_W
            y = row_idx * CELL_H
            center = (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H))
            if tile == DOT_TILE:
                pygame.draw.circle(screen, WHITE, center, DOT_RADIUS)
            if tile == POWER_DOT_TILE and not flicker:
                pygame.draw.circle(screen, WHITE, center, POWER_DOT_RADIUS)
            if tile >= 3 and tile != GATE_TILE and tile != 10:
                rows = len(level)
                cols = len(level[0])
                
                is_wall_up = row_idx > 0 and level[row_idx - 1][col_idx] >= 3 and level[row_idx - 1][col_idx] != GATE_TILE
                is_wall_down = row_idx < rows - 1 and level[row_idx + 1][col_idx] >= 3 and level[row_idx + 1][col_idx] != GATE_TILE
                is_wall_left = col_idx > 0 and level[row_idx][col_idx - 1] >= 3 and level[row_idx][col_idx - 1] != GATE_TILE
                is_wall_right = col_idx < cols - 1 and level[row_idx][col_idx + 1] >= 3 and level[row_idx][col_idx + 1] != GATE_TILE
                
                if row_idx == 16:
                    if col_idx == 0 and level[row_idx][cols - 1] >= 3: is_wall_left = True
                    if col_idx == cols - 1 and level[row_idx][0] >= 3: is_wall_right = True

                offset = WALL_WIDTH // 2 + 1

                if not is_wall_up:
                    pygame.draw.line(screen, color, (x - offset, y), (x + CELL_W + offset, y), WALL_WIDTH)
                if not is_wall_down:
                    pygame.draw.line(screen, color, (x - offset, y + CELL_H), (x + CELL_W + offset, y + CELL_H), WALL_WIDTH)
                if not is_wall_left:
                    pygame.draw.line(screen, color, (x, y - offset), (x, y + CELL_H + offset), WALL_WIDTH)
                if not is_wall_right:
                    pygame.draw.line(screen, color, (x + CELL_W, y - offset), (x + CELL_W, y + CELL_H + offset), WALL_WIDTH)
            elif tile == GATE_TILE:
                cy = y + (ARC_HALF_RATIO * CELL_H)
                pygame.draw.line(
                    screen,
                    WHITE,
                    (x, cy),
                    (x + CELL_W, cy),
                    WALL_WIDTH,
                )


# Pixel deltas (row_delta, col_delta) per direction constant (RIGHT=0,LEFT=1,UP=2,DOWN=3).
_DIR_PIXEL: tuple[tuple[int, int], ...] = ((0, 30), (0, -30), (-30, 0), (30, 0))


def _ghost_mode_label(ghost: object, player: Player) -> tuple[str, bool]:
    """Return (mode_string, using_astar) for a ghost."""
    ghost_id = getattr(ghost, "id", -1)
    eaten = getattr(player, "eaten_ghost", [])
    dead = getattr(ghost, "dead", False)
    in_box = getattr(ghost, "in_box", False)
    is_patrolling = getattr(ghost, "is_patrolling", False)

    if dead:
        return "Return", True
    if in_box:
        return "Exit Box", True
    if player.powerup and (ghost_id < 0 or not eaten[ghost_id]):
        return "Flee", True
    if is_patrolling:
        return "Patrol", True
    # Inky (id=1) and Clyde (id=3) use old pursuit in chase mode.
    if ghost_id in (1, 3):
        return "Chase", False
    return "Chase", True


def _draw_dashed_line(
    screen: pygame.Surface,
    color: tuple[int, int, int],
    start: tuple[int, int],
    end: tuple[int, int],
    width: int = 1,
    dash: int = 7,
    gap: int = 5,
) -> None:
    """Draw a dashed straight line between two pixel coordinates."""
    import math

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    total = math.hypot(dx, dy)
    if total == 0:
        return
    ux, uy = dx / total, dy / total
    pos = 0.0
    drawing = True
    while pos < total:
        seg = dash if drawing else gap
        end_pos = min(pos + seg, total)
        if drawing:
            x1 = int(start[0] + ux * pos)
            y1 = int(start[1] + uy * pos)
            x2 = int(start[0] + ux * end_pos)
            y2 = int(start[1] + uy * end_pos)
            pygame.draw.line(screen, color, (x1, y1), (x2, y2), width)
        pos = end_pos + (gap if drawing else 0)
        drawing = not drawing


def _draw_arrow(
    screen: pygame.Surface,
    color: tuple[int, int, int],
    cx: int,
    cy: int,
    direction: int,
    length: int = 26,
) -> None:
    """Draw a directional arrow centred at (cx, cy)."""
    import math

    # direction: RIGHT=0, LEFT=1, UP=2, DOWN=3
    angles = {0: 0, 1: math.pi, 2: -math.pi / 2, 3: math.pi / 2}
    angle = angles.get(direction, 0)
    ex = cx + int(math.cos(angle) * length)
    ey = cy + int(math.sin(angle) * length)
    pygame.draw.line(screen, color, (cx, cy), (ex, ey), 3)
    # Arrowhead
    head_len = 8
    for side in (math.pi * 0.75, -math.pi * 0.75):
        hx = ex + int(math.cos(angle + side) * head_len)
        hy = ey + int(math.sin(angle + side) * head_len)
        pygame.draw.line(screen, color, (ex, ey), (hx, hy), 3)


def _blit_label(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    x: int,
    y: int,
) -> None:
    """Render text with a black backing rectangle."""
    surf = font.render(text, True, color)
    lx = max(0, min(WIDTH - surf.get_width(), x))
    ly = max(0, y)
    pygame.draw.rect(screen, (0, 0, 0), (lx - 2, ly - 1, surf.get_width() + 4, surf.get_height() + 2))
    screen.blit(surf, (lx, ly))


def draw_debug_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    ghosts: list,
    player: Player,
    targets: list,
    agent: object = None,
) -> None:
    """Overlay A* paths, targets, and mode labels for all ghosts and the Pacman AI.

    Toggle with the V key in main.py.

    Ghost solid line  = A* path (list of queued cells).
    Ghost dashed line = Old pursuit algorithm (Inky/Clyde chase mode, no A* path).
    Ghost X mark      = current pixel target.
    Yellow path       = BFS route from Pacman to the Expectimax strategic target.
    Green arrow       = direction Expectimax actually chose this frame.
    """
    # ---- Ghost paths, targets, mode labels ----
    for i, ghost in enumerate(ghosts):
        color = _GHOST_PATH_COLORS[i % len(_GHOST_PATH_COLORS)]
        name = _GHOST_NAMES[i] if i < len(_GHOST_NAMES) else f"Ghost{i}"
        path: list = getattr(ghost, "_path", [])
        gx = getattr(ghost, "x_pos", 0)
        gy = getattr(ghost, "y_pos", 0)
        gcx = gx + GHOST_CENTER_OFFSET
        gcy = gy + GHOST_CENTER_OFFSET

        mode_str, using_astar = _ghost_mode_label(ghost, player)
        algo_tag = "[A*]" if using_astar else "[Pursuit]"

        if path:
            # Solid line + dots for A* path.
            prev_x, prev_y = gcx, gcy
            for row, col in path:
                cx = col * CELL_W + CELL_W // 2
                cy = row * CELL_H + CELL_H // 2
                pygame.draw.line(screen, color, (prev_x, prev_y), (cx, cy), 2)
                pygame.draw.circle(screen, color, (cx, cy), 4)
                prev_x, prev_y = cx, cy
        elif i < len(targets) and not getattr(ghost, "dead", False):
            # Dashed line to target when using old pursuit (no queued A* path).
            tx, ty = int(targets[i][0]), int(targets[i][1])
            _draw_dashed_line(screen, color, (gcx, gcy), (tx, ty), width=2)

        # Target X mark.
        if i < len(targets):
            tx, ty = int(targets[i][0]), int(targets[i][1])
            s = 9
            pygame.draw.line(screen, color, (tx - s, ty - s), (tx + s, ty + s), 3)
            pygame.draw.line(screen, color, (tx + s, ty - s), (tx - s, ty + s), 3)
            pygame.draw.circle(screen, color, (tx, ty), s + 2, 1)

        # Mode + algorithm label above ghost.
        label_text = f"{name}: {mode_str} {algo_tag}"
        _blit_label(screen, font, label_text, color, gx - 5, gy - font.get_height() - 2)

    # ---- Pacman AI: strategic A* target + BFS path + Expectimax arrow ----
    if agent is not None:
        pcx = player.x_pos + PLAYER_CENTER_OFFSET_X
        pcy = player.y_pos + PLAYER_CENTER_OFFSET_Y

        # Draw the BFS path from Pacman to the strategic target.
        target_cell = getattr(agent, "_astar_target", None)
        if target_cell is not None:
            tr, tc = target_cell
            tx = tc * CELL_W + CELL_W // 2
            ty = tr * CELL_H + CELL_H // 2

            parents: dict = getattr(agent, "_last_parents", {})
            pacman_cell = getattr(agent, "_last_pacman_cell", None)
            if parents and pacman_cell is not None and target_cell in parents:
                path_cells: list = []
                cur = target_cell
                while cur in parents and parents[cur] is not None:
                    path_cells.append(cur)
                    cur = parents[cur]
                path_cells.reverse()  # [first_step, ..., target_cell]

                px = pacman_cell[1] * CELL_W + CELL_W // 2
                py = pacman_cell[0] * CELL_H + CELL_H // 2
                for row, col in path_cells:
                    cx = col * CELL_W + CELL_W // 2
                    cy = row * CELL_H + CELL_H // 2
                    pygame.draw.line(screen, (255, 255, 0), (px, py), (cx, cy), 2)
                    pygame.draw.circle(screen, (255, 255, 0), (cx, cy), 3)
                    px, py = cx, cy

            # Diamond at the strategic target.
            s = 11
            diamond = [(tx, ty - s), (tx + s, ty), (tx, ty + s), (tx - s, ty)]
            pygame.draw.polygon(screen, (255, 255, 0), diamond, 2)
            pygame.draw.circle(screen, (255, 255, 0), (tx, ty), 4)
            _blit_label(screen, font, "AI Target (A*)", (255, 255, 0),
                        tx - 45, ty - font.get_height() - 4)

        # Green arrow: direction Expectimax actually chose.
        cached_action = getattr(agent, "_cached_action", None)
        if cached_action is not None:
            _draw_arrow(screen, (0, 255, 100), pcx, pcy, cached_action)
            _blit_label(screen, font, "Expectimax choice", (0, 255, 100),
                        player.x_pos - 20, player.y_pos - font.get_height() * 2 - 4)

    # ---- Corner hint ----
    hint = font.render("[V] Debug ON  [B] BFS Map", True, (180, 180, 180))
    screen.blit(hint, (WIDTH - hint.get_width() - 5, 4))


def draw_bfs_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    player: Player,
    dist_field: dict,
) -> None:

    if not dist_field:
        return

    max_dist = max(dist_field.values(), default=1)

    # Build semi-transparent heatmap surface.
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for (row, col), dist in dist_field.items():
        ratio = min(1.0, dist / max(max_dist, 1))
        r = int(255 * max(0.0, 1.0 - ratio * 1.4))
        g = int(220 * max(0.0, 1.0 - abs(ratio - 0.4) * 2.0))
        b = int(230 * ratio)
        alpha = max(25, int(110 - ratio * 55))
        cx = col * CELL_W
        cy = row * CELL_H
        pygame.draw.rect(overlay, (r, g, b, alpha), (cx, cy, CELL_W, CELL_H))
    screen.blit(overlay, (0, 0))

    # White outline on Pacman's own cell.
    pcell_r = (player.y_pos + PLAYER_CENTER_OFFSET_Y) // CELL_H
    pcell_c = (player.x_pos + PLAYER_CENTER_OFFSET_X) // CELL_W
    pygame.draw.rect(
        screen, (255, 255, 255),
        (pcell_c * CELL_W, pcell_r * CELL_H, CELL_W, CELL_H), 2,
    )

    # Legal-move arrows: green = allowed, red = wall/blocked.
    pcx = player.x_pos + PLAYER_CENTER_OFFSET_X
    pcy = player.y_pos + PLAYER_CENTER_OFFSET_Y
    # direction index: RIGHT=0, LEFT=1, UP=2, DOWN=3
    for d in range(4):
        allowed = player.turns_allowed[d]
        color = (0, 230, 80) if allowed else (220, 40, 40)
        if allowed:
            _draw_arrow(screen, color, pcx, pcy, d, length=26)
        else:
            # Short red stub showing the blocked side.
            deltas = [(26, 0), (-26, 0), (0, -26), (0, 26)]
            dx, dy = deltas[d]
            end_x, end_y = pcx + dx, pcy + dy
            pygame.draw.line(screen, color, (pcx, pcy), (end_x, end_y), 2)
            # Draw a small X at the end to mark "blocked".
            s = 5
            pygame.draw.line(screen, color, (end_x - s, end_y - s), (end_x + s, end_y + s), 2)
            pygame.draw.line(screen, color, (end_x + s, end_y - s), (end_x - s, end_y + s), 2)

    # Legend bar at top.
    legend = font.render(
        "[B] BFS Scan  yellow=gần  green=xa  blue=di duoc  red X=bi chan",
        True, (220, 220, 220),
    )
    pygame.draw.rect(screen, (0, 0, 0), (3, 3, legend.get_width() + 4, legend.get_height() + 2))
    screen.blit(legend, (5, 4))
