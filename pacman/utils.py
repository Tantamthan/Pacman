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
    LIFE_IMAGE_SIZE,
    LIFE_SPACING,
    LIFE_START_X,
    LIFE_Y,
    MESSAGE_INNER_RECT,
    MESSAGE_OUTER_RECT,
    MESSAGE_POS,
    MESSAGE_RADIUS,
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
    """Draw score, lives, power marker, and end-game messages."""
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
    """Draw the board generation loading screen."""
    screen.fill(BLACK)
    loading_text = font.render("Generating board...", True, WHITE)
    seed_text = font.render(f"Seed: {seed}", True, WHITE)
    screen.blit(loading_text, (WIDTH // 2 - loading_text.get_width() // 2, HEIGHT // 2 - 20))
    screen.blit(seed_text, (WIDTH // 2 - seed_text.get_width() // 2, HEIGHT // 2 + 15))


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
            if tile == VERTICAL_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y),
                    (x + (ARC_HALF_RATIO * CELL_W), y + CELL_H),
                    WALL_WIDTH,
                )
            if tile == HORIZONTAL_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x, y + (ARC_HALF_RATIO * CELL_H)),
                    (x + CELL_W, y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
            if tile == TOP_RIGHT_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x, y + (ARC_HALF_RATIO * CELL_H)),
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    (x + (ARC_HALF_RATIO * CELL_W), y + CELL_H),
                    WALL_WIDTH,
                )
            if tile == TOP_LEFT_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    (x + CELL_W, y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    (x + (ARC_HALF_RATIO * CELL_W), y + CELL_H),
                    WALL_WIDTH,
                )
            if tile == BOTTOM_LEFT_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y),
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    (x + CELL_W, y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
            if tile == BOTTOM_RIGHT_WALL_TILE:
                pygame.draw.line(
                    screen,
                    color,
                    (x + (ARC_HALF_RATIO * CELL_W), y),
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
                pygame.draw.line(
                    screen,
                    color,
                    (x, y + (ARC_HALF_RATIO * CELL_H)),
                    (x + (ARC_HALF_RATIO * CELL_W), y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
            if tile == GATE_TILE:
                pygame.draw.line(
                    screen,
                    WHITE,
                    (x, y + (ARC_HALF_RATIO * CELL_H)),
                    (x + CELL_W, y + (ARC_HALF_RATIO * CELL_H)),
                    WALL_WIDTH,
                )
