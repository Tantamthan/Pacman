"""Headless benchmark for the Expectimax Pac-Man AI.

Run:  python benchmark_ai.py [--games N]
Default: 5 games on the default (fixed) board.
"""

from __future__ import annotations

import copy
import os
import sys
import time
import argparse

# Must be set BEFORE pygame is imported.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from pacman.board import boards
from pacman.constants import (
    ANIMATION_MAX,
    BLINKY_ID, BLINKY_START,
    CLYDE_ID, CLYDE_START,
    DOT_TILE, POWER_DOT_TILE,
    FLICKER_THRESHOLD,
    FONT_SIZE,
    GHOST_COUNT,
    GHOST_DEAD_SPEED, GHOST_NORMAL_SPEED, GHOST_POWER_SPEED,
    GHOST_IMAGE_SIZE, PLAYER_IMAGE_SIZE, PLAYER_ANIMATION_FRAMES,
    HEIGHT, WIDTH,
    INKY_ID, INKY_START,
    PINKY_ID, PINKY_START,
    PLAYER_LIVES,
    POWERUP_DURATION,
    STARTUP_DELAY,
    ASSET_DIR,
)
from pacman.ghost import Ghost, get_targets
from pacman.main import (
    apply_direction_command,
    board_has_pellets,
    handle_ghost_collisions,
    move_ghosts,
    reset_game,
    update_ghost_speeds,
)
from pacman.player import Player
from pacman.player_ai import ExpectimaxAgent


Level = list[list[int]]


def count_pellets(level: Level) -> int:
    return sum(
        1
        for row in level
        for tile in row
        if tile in (DOT_TILE, POWER_DOT_TILE)
    )


def load_images() -> tuple[list[pygame.Surface], dict[str, pygame.Surface]]:
    player_images = [
        pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/player_images/{i}.png"),
            PLAYER_IMAGE_SIZE,
        )
        for i in range(1, PLAYER_ANIMATION_FRAMES + 1)
    ]
    ghost_images = {
        name: pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/{fname}.png"),
            GHOST_IMAGE_SIZE,
        )
        for name, fname in [
            ("blinky", "red"), ("pinky", "pink"), ("inky", "blue"),
            ("clyde", "orange"), ("spooked", "powerup"), ("dead", "dead"),
        ]
    }
    return player_images, ghost_images


def run_one_game(
    player_images: list[pygame.Surface],
    ghost_images: dict[str, pygame.Surface],
    screen: pygame.Surface,
    agent: ExpectimaxAgent,
    max_frames: int = 36_000,  # 10 min at 60 fps
) -> dict:
    """Simulate one full game and return a result dict."""
    level: Level = copy.deepcopy(boards)
    total_pellets = count_pellets(level)

    player = Player()
    targets = [(player.x_pos, player.y_pos)] * GHOST_COUNT
    ghosts = [
        Ghost(*BLINKY_START[:2], targets[BLINKY_ID], GHOST_NORMAL_SPEED, ghost_images["blinky"], BLINKY_START[2], False, False, BLINKY_ID),
        Ghost(*INKY_START[:2],   targets[INKY_ID],   GHOST_NORMAL_SPEED, ghost_images["inky"],   INKY_START[2],   False, False, INKY_ID),
        Ghost(*PINKY_START[:2],  targets[PINKY_ID],  GHOST_NORMAL_SPEED, ghost_images["pinky"],  PINKY_START[2],  False, False, PINKY_ID),
        Ghost(*CLYDE_START[:2],  targets[CLYDE_ID],  GHOST_NORMAL_SPEED, ghost_images["clyde"],  CLYDE_START[2],  False, False, CLYDE_ID),
    ]
    agent._cached_action = None
    agent._frame_counter = 0
    agent._visit_frame = {}
    agent._last_score = 0
    agent._last_score_change_frame = 0
    agent._astar_target = None
    agent._dist_from_target = {}
    agent._last_target_frame = -60

    counter = 0
    startup_counter = 0
    moving = False
    game_over = False
    game_won = False
    frames = 0

    while frames < max_frames:
        frames += 1

        # Animation counter (needed for player.draw)
        if counter < ANIMATION_MAX:
            counter += 1
        else:
            counter = 0
        flicker = counter <= FLICKER_THRESHOLD

        # Powerup timer
        if player.powerup and player.power_counter < POWERUP_DURATION:
            player.power_counter += 1
        elif player.powerup and player.power_counter >= POWERUP_DURATION:
            player.power_counter = 0
            player.powerup = False
            player.eaten_ghost = [False, False, False, False]

        if startup_counter < STARTUP_DELAY and not game_over and not game_won:
            moving = False
            startup_counter += 1
        else:
            moving = True

        update_ghost_speeds(player, ghosts)
        game_won = not board_has_pellets(level)
        if game_won:
            break

        center_x = player.center_x
        center_y = player.center_y

        # Draw calls needed for rect/side-effects
        player_rect = player.draw(screen, player_images, counter, flicker)
        targets = get_targets(player, ghosts, level)
        for ghost, target in zip(ghosts, targets):
            ghost.target = target
            ghost.check_collisions(level)
            ghost.draw(screen, player, ghost_images["spooked"], ghost_images["dead"])

        player.check_collisions(level)
        if moving:
            player.move(level)
            move_ghosts(ghosts, level)
        player.eat_tile_at(level, center_x, center_y)

        if handle_ghost_collisions(player, ghosts, player_rect):
            if player.lives <= 0:
                game_over = True
                break
            # life lost but continuing — reset positions
            startup_counter = 0
            moving = False

        if moving and not game_over and not game_won:
            player.direction_command = agent.get_action(player, ghosts, level)
        apply_direction_command(player)
        player.wrap_tunnel()

        for ghost in ghosts:
            if ghost.in_box and ghost.dead:
                ghost.dead = False

    remaining = count_pellets(level)
    eaten = total_pellets - remaining
    # Collect remaining dot positions for diagnostics
    remaining_cells = [
        (r, c)
        for r in range(len(level))
        for c in range(len(level[r]))
        if level[r][c] in (1, 2)
    ]
    return {
        "score": player.score,
        "lives_left": player.lives,
        "pellets_eaten": eaten,
        "total_pellets": total_pellets,
        "pct_eaten": eaten / total_pellets * 100 if total_pellets else 0,
        "won": game_won,
        "frames": frames,
        "remaining_cells": remaining_cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Pac-Man Expectimax AI")
    parser.add_argument("--games", type=int, default=5, help="Number of games to run")
    parser.add_argument("--depth", type=int, default=2, help="Expectimax search depth")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode([WIDTH, HEIGHT])
    font = pygame.font.Font("freesansbold.ttf", FONT_SIZE)
    del font

    print(f"Loading assets...")
    player_images, ghost_images = load_images()
    agent = ExpectimaxAgent(depth=args.depth)

    print(f"Running {args.games} game(s) with Expectimax depth={args.depth}...\n")
    print(f"{'Game':>5}  {'Score':>7}  {'Pellets':>10}  {'%Eaten':>8}  {'Lives':>6}  {'Result':>8}  {'Frames':>8}")
    print("-" * 70)

    results = []
    t0 = time.time()
    for i in range(args.games):
        r = run_one_game(player_images, ghost_images, screen, agent)
        results.append(r)
        outcome = "WIN" if r["won"] else "LOSS"
        print(
            f"{i+1:>5}  {r['score']:>7}  "
            f"{r['pellets_eaten']:>4}/{r['total_pellets']:<4}  "
            f"{r['pct_eaten']:>7.1f}%  "
            f"{r['lives_left']:>6}  "
            f"{outcome:>8}  "
            f"{r['frames']:>8}"
        )

    elapsed = time.time() - t0
    wins = sum(1 for r in results if r["won"])
    avg_score = sum(r["score"] for r in results) / len(results)
    avg_pct = sum(r["pct_eaten"] for r in results) / len(results)
    avg_lives = sum(r["lives_left"] for r in results) / len(results)

    print("-" * 70)
    print(f"\nSummary over {args.games} game(s)  [{elapsed:.1f}s wall time]")
    print(f"  Win rate       : {wins}/{args.games} ({wins/args.games*100:.0f}%)")
    print(f"  Avg score      : {avg_score:.0f}")
    print(f"  Avg % cleared  : {avg_pct:.1f}%")
    print(f"  Avg lives left : {avg_lives:.1f}")

    # Show which cells are most often uneaten (from first game)
    if results and not results[0]["won"]:
        cells = results[0]["remaining_cells"]
        print(f"\n  Remaining dots in game 1 (row, col):")
        # Group by row for readability
        from collections import defaultdict
        by_row: dict = defaultdict(list)
        for r, c in sorted(cells):
            by_row[r].append(c)
        for row in sorted(by_row):
            print(f"    row {row:>2}: cols {by_row[row]}")

    pygame.quit()


if __name__ == "__main__":
    main()
