"""Main loop and event handling for Pac-Man."""

from __future__ import annotations

import copy
import random
import time

import pygame

from pacman.board import boards
from pacman.board_generator import LAST_GENERATION_INFO, generate_board
from pacman.constants import (
    ANIMATION_MAX,
    ASSET_DIR,
    BLACK,
    BLINKY_ID,
    BLINKY_START,
    BLUE,
    CLYDE_ID,
    CLYDE_START,
    DOWN,
    FLICKER_THRESHOLD,
    FONT_SIZE,
    FPS,
    GHOST_COUNT,
    GHOST_DEAD_SPEED,
    GHOST_IMAGE_SIZE,
    GHOST_NORMAL_SPEED,
    GHOST_POWER_SPEED,
    HEIGHT,
    INKY_ID,
    INKY_START,
    LEFT,
    PINKY_ID,
    PINKY_START,
    PLAYER_IMAGE_SIZE,
    PLAYER_ANIMATION_FRAMES,
    PLAYER_LIVES,
    POWERUP_DURATION,
    POWER_DOT_TILE,
    RIGHT,
    STARTUP_DELAY,
    DOT_TILE,
    UP,
    WIDTH,
    GHOST_EAT_SCORE_BASE,
    GHOST_EAT_SCORE_UNIT,
)
from pacman.ghost import Ghost, get_targets
from pacman.player import Player
from pacman.utils import draw_board, draw_loading, draw_misc

Level = list[list[int]]
ImageMap = dict[str, pygame.Surface]


def load_images() -> tuple[list[pygame.Surface], ImageMap]:
    """Load and scale all sprite images."""
    player_images = [
        pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/player_images/{i}.png"),
            PLAYER_IMAGE_SIZE,
        )
        for i in range(1, PLAYER_ANIMATION_FRAMES + 1)
    ]
    ghost_images = {
        "blinky": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/red.png"),
            GHOST_IMAGE_SIZE,
        ),
        "pinky": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/pink.png"),
            GHOST_IMAGE_SIZE,
        ),
        "inky": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/blue.png"),
            GHOST_IMAGE_SIZE,
        ),
        "clyde": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/orange.png"),
            GHOST_IMAGE_SIZE,
        ),
        "spooked": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/powerup.png"),
            GHOST_IMAGE_SIZE,
        ),
        "dead": pygame.transform.scale(
            pygame.image.load(f"{ASSET_DIR}/ghost_images/dead.png"),
            GHOST_IMAGE_SIZE,
        ),
    }
    return player_images, ghost_images


def create_ghosts(ghost_images: ImageMap, targets: list[tuple[int, int]]) -> list[Ghost]:
    """Create ghosts in the original order used by target logic."""
    return [
        Ghost(*BLINKY_START[:2], targets[BLINKY_ID], GHOST_NORMAL_SPEED, ghost_images["blinky"], BLINKY_START[2], False, False, BLINKY_ID),
        Ghost(*INKY_START[:2], targets[INKY_ID], GHOST_NORMAL_SPEED, ghost_images["inky"], INKY_START[2], False, False, INKY_ID),
        Ghost(*PINKY_START[:2], targets[PINKY_ID], GHOST_NORMAL_SPEED, ghost_images["pinky"], PINKY_START[2], False, False, PINKY_ID),
        Ghost(*CLYDE_START[:2], targets[CLYDE_ID], GHOST_NORMAL_SPEED, ghost_images["clyde"], CLYDE_START[2], False, False, CLYDE_ID),
    ]


def reset_game(player: Player, ghosts: list[Ghost]) -> None:
    """Reset player and ghost positions after a life reset."""
    player.reset()
    ghosts[BLINKY_ID].reset(*BLINKY_START)
    ghosts[INKY_ID].reset(*INKY_START)
    ghosts[PINKY_ID].reset(*PINKY_START)
    ghosts[CLYDE_ID].reset(*CLYDE_START)


def update_ghost_speeds(player: Player, ghosts: list[Ghost]) -> None:
    """Apply the original speed rules for normal, power, eaten, and dead states."""
    if player.powerup:
        speeds = [GHOST_POWER_SPEED] * GHOST_COUNT
    else:
        speeds = [GHOST_NORMAL_SPEED] * GHOST_COUNT
    for ghost_id, eaten in enumerate(player.eaten_ghost):
        if eaten:
            speeds[ghost_id] = GHOST_NORMAL_SPEED
    for ghost in ghosts:
        if ghost.dead:
            speeds[ghost.id] = GHOST_DEAD_SPEED
    for ghost in ghosts:
        ghost.speed = speeds[ghost.id]


def board_has_pellets(level: Level) -> bool:
    """Return whether any dots remain on the board."""
    return any(DOT_TILE in row or POWER_DOT_TILE in row for row in level)


def generate_level(screen: pygame.Surface, font: pygame.font.Font) -> Level:
    """Generate a random board with loading feedback and fallback."""
    seed = random.randrange(1_000_000_000)
    draw_loading(screen, font, seed)
    pygame.display.flip()
    pygame.event.pump()
    started = time.time()
    try:
        level = generate_board(seed=seed)
        duration = time.time() - started
        fitness = LAST_GENERATION_INFO["fitness"]
        playable = LAST_GENERATION_INFO["playable"]
        print(
            f"Generated board seed: {seed}, fitness: {fitness}, "
            f"playable: {playable}, duration: {duration:.2f}s"
        )
        if not playable:
            print("Warning: GA did not find a playable board; using default board fallback.")
        return level
    except Exception as exc:
        duration = time.time() - started
        print(f"Warning: board generation failed for seed {seed} after {duration:.2f}s: {exc}")
        return copy.deepcopy(boards)


def lose_life_or_end(player: Player, ghosts: list[Ghost]) -> bool:
    """Lose one life with original timing, or signal game over."""
    if player.lives > 0:
        player.lives -= 1
        reset_game(player, ghosts)
        return False
    return True


def handle_keydown(event: pygame.event.Event, player: Player, game_over: bool, game_won: bool) -> bool:
    """Update the queued direction and return whether restart was requested."""
    if event.key == pygame.K_RIGHT:
        player.direction_command = RIGHT
    if event.key == pygame.K_LEFT:
        player.direction_command = LEFT
    if event.key == pygame.K_UP:
        player.direction_command = UP
    if event.key == pygame.K_DOWN:
        player.direction_command = DOWN
    return event.key == pygame.K_SPACE and (game_over or game_won)


def handle_keyup(event: pygame.event.Event, player: Player) -> None:
    """Restore the active direction when the queued key is released."""
    if event.key == pygame.K_RIGHT and player.direction_command == RIGHT:
        player.direction_command = player.direction
    if event.key == pygame.K_LEFT and player.direction_command == LEFT:
        player.direction_command = player.direction
    if event.key == pygame.K_UP and player.direction_command == UP:
        player.direction_command = player.direction
    if event.key == pygame.K_DOWN and player.direction_command == DOWN:
        player.direction_command = player.direction


def apply_direction_command(player: Player) -> None:
    """Commit the queued direction if that turn is allowed."""
    if player.direction_command == RIGHT and player.turns_allowed[RIGHT]:
        player.set_direction(RIGHT)
    if player.direction_command == LEFT and player.turns_allowed[LEFT]:
        player.set_direction(LEFT)
    if player.direction_command == UP and player.turns_allowed[UP]:
        player.set_direction(UP)
    if player.direction_command == DOWN and player.turns_allowed[DOWN]:
        player.set_direction(DOWN)


def move_ghosts(ghosts: list[Ghost], level: Level) -> None:
    """Move all ghosts in the same order as the original loop."""
    blinky, inky, pinky, clyde = ghosts
    blinky.move_astar(level, blinky.target)
    pinky.move_astar(level, pinky.target)
    if inky.is_patrolling:
        inky.move_astar(level, inky.target)
    elif not inky.dead and not inky.in_box:
        inky.move_inky()
    else:
        inky.move_clyde()
    if clyde.is_patrolling:
        clyde.move_astar(level, clyde.target)
    else:
        clyde.move_clyde()


def handle_ghost_collisions(
    player: Player,
    ghosts: list[Ghost],
    player_rect: pygame.Rect,
) -> bool:
    """Handle player-ghost collisions and return whether game over started."""
    if not player.powerup:
        if any(player_rect.colliderect(ghost.rect) and not ghost.dead for ghost in ghosts):
            return lose_life_or_end(player, ghosts)

    for ghost in ghosts:
        if player.powerup and player_rect.colliderect(ghost.rect) and player.eaten_ghost[ghost.id] and not ghost.dead:
            return lose_life_or_end(player, ghosts)

    for ghost in ghosts:
        if player.powerup and player_rect.colliderect(ghost.rect) and not ghost.dead and not player.eaten_ghost[ghost.id]:
            ghost.dead = True
            player.eaten_ghost[ghost.id] = True
            player.score += (GHOST_EAT_SCORE_BASE ** player.eaten_ghost.count(True)) * GHOST_EAT_SCORE_UNIT
    return False


def main() -> None:
    """Run the Pac-Man game."""
    pygame.init()
    screen = pygame.display.set_mode([WIDTH, HEIGHT])
    timer = pygame.time.Clock()
    font = pygame.font.Font("freesansbold.ttf", FONT_SIZE)
    player_images, ghost_images = load_images()
    level: Level = generate_level(screen, font)
    player = Player()
    targets = [(player.x_pos, player.y_pos)] * GHOST_COUNT
    ghosts = create_ghosts(ghost_images, targets)

    counter = 0
    flicker = False
    startup_counter = 0
    moving = False
    game_over = False
    game_won = False
    run = True

    while run:
        timer.tick(FPS)
        if counter < ANIMATION_MAX:
            counter += 1
            if counter > FLICKER_THRESHOLD:
                flicker = False
        else:
            counter = 0
            flicker = True

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

        screen.fill(BLACK)
        draw_board(screen, level, flicker, BLUE)
        center_x = player.center_x
        center_y = player.center_y
        update_ghost_speeds(player, ghosts)
        game_won = not board_has_pellets(level)

        player_rect = player.draw(screen, player_images, counter, flicker)
        for ghost, target in zip(ghosts, targets):
            ghost.target = target
            ghost.check_collisions(level)
            ghost.draw(screen, player, ghost_images["spooked"], ghost_images["dead"])
        draw_misc(screen, font, player, player_images, game_over, game_won)
        targets = get_targets(player, ghosts, level)

        player.check_collisions(level)
        if moving:
            player.move(level)
            move_ghosts(ghosts, level)
        player.eat_tile_at(level, center_x, center_y)

        if handle_ghost_collisions(player, ghosts, player_rect):
            game_over = True
            moving = False
            startup_counter = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if handle_keydown(event, player, game_over, game_won):
                    level = generate_level(screen, font)
                    reset_game(player, ghosts)
                    player.score = 0
                    player.lives = PLAYER_LIVES
                    startup_counter = 0
                    game_over = False
                    game_won = False
            if event.type == pygame.KEYUP:
                handle_keyup(event, player)

        apply_direction_command(player)
        player.wrap_tunnel()

        for ghost in ghosts:
            if ghost.in_box and ghost.dead:
                ghost.dead = False

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
