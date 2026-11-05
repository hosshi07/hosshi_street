# -*- coding: utf-8 -*-
"""
STACK GAME - blocks drop from above; stack them as high as you can
without crossing the TOP LINE. Overhanging parts get sliced off!

Controls:
  SPACE  = drop the swinging block
  R      = retry after game over
  Q      = quit
"""
import pygame
import math
import json
import os
import sys

# ---------- constants ----------
W, H = 640, 820
BLOCK_H = 34
DANGER_Y = 130          # do not stack above this line
BASE_Y = H - 46         # top surface of the ground platform
BASE_W = 260
PERFECT_TOL = 6         # snap tolerance for a "perfect" landing
MIN_OVERLAP = 10        # overlap smaller than this = miss
SWING_SPEED = 1.9       # how fast the block swings (rad/s, grows with level)
FALL_SPEED = 1150       # px/s when the block is dropping

BEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "stack_best.json")

MARGIN = 10


def load_best():
    try:
        with open(BEST_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("best", 0))
    except Exception:
        return 0


def save_best(best):
    try:
        with open(BEST_FILE, "w", encoding="utf-8") as f:
            json.dump({"best": int(best)}, f)
    except Exception:
        pass


def block_color(i):
    """Rotate hue per level -> colorful tower."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((i * 0.073) % 1.0, 0.50, 0.95)
    return (int(r * 255), int(g * 255), int(b * 255))


class Game:
    def __init__(self):
        # stack[i] = (x, w); i=0 is the base platform block
        self.stack = [((W - BASE_W) / 2.0, BASE_W)]
        self.score = 0
        self.streak = 0
        self.level = 0
        self.cur = None          # (x, w, state, y, phase)
        self.debris = []         # falling sliced-off pieces
        self.spawn()
        self.msg = ""
        self.msg_timer = 0
        self.state = "play"
        self.best = load_best()

    def top_y(self):
        """Top surface y of the current tower."""
        return BASE_Y - len(self.stack) * BLOCK_H

    def spawn(self):
        w = self.stack[-1][1]
        self.cur = {"x": None, "w": w, "state": "swing",
                    "y": self.top_y() - 130, "phase": 0.0, "dropping": False}

    def update_swing(self, dt):
        t = self.level * 0.06
        speed = SWING_SPEED + t
        self.cur["phase"] += dt * speed
        p = self.cur["phase"]
        w = self.cur["w"]
        a, b = MARGIN, W - MARGIN - w          # left-edge range
        self.cur["x"] = a + (b - a) * (0.5 + 0.5 * math.sin(p))
        # auto-drop if the player waits too long (after 1.25 swings)
        if p > 2.5 * math.pi:
            self.cur["dropping"] = True

    def drop(self):
        if self.cur["x"] is None:
            self.update_swing(0.0)
        self.cur["dropping"] = True

    def update_fall(self, dt):
        if self.cur["x"] is None:      # dropped before any swing frame
            self.update_swing(0.0)
        self.cur["y"] -= FALL_SPEED * dt
        if self.cur["y"] <= self.top_y() - BLOCK_H:
            self.cur["y"] = self.top_y() - BLOCK_H
            self.land()

    def land(self):
        tx, tw = self.stack[-1]
        x, w = self.cur["x"], self.cur["w"]
        left = max(x, tx)
        right = min(x + w, tx + tw)
        overlap = right - left

        if overlap < MIN_OVERLAP:
            # total miss -> whole block falls away
            self.debris.append([x, self.top_y() - BLOCK_H, w, BLOCK_H, 0, 60])
            self.game_over("MISSED!")
            return

        perfect = abs(x - tx) <= PERFECT_TOL
        if perfect:
            nx, nw = tx, tw
        else:
            nx, nw = left, overlap
            # slice off overhanging pieces as debris
            if x < tx:
                self.debris.append([x, self.top_y() - BLOCK_H, tx - x,
                                    BLOCK_H, -90, 0])
            if x + w > tx + tw:
                self.debris.append([tx + tw, self.top_y() - BLOCK_H,
                                    x + w - (tx + tw), BLOCK_H, 90, 0])

        idx = len(self.stack)
        color = block_color(idx)
        self.cur["debris_color"] = color

        self.score += 1
        if perfect:
            self.streak += 1
            bonus = min(self.streak, 5)
            self.score += bonus
            self.msg = f"PERFECT!  +{bonus + 1}"
        else:
            self.streak = 0
            self.msg = ""
        self.msg_timer = 1.2

        self.stack.append((nx, nw))

        # reached the line?
        if self.top_y() < DANGER_Y:
            self.game_over("TOP LINE REACHED!")
            return

        self.level += 1
        self.spawn()

    def game_over(self, reason):
        self.state = "over"
        self.msg = reason
        if self.score > self.best:
            self.best = self.score
            save_best(self.best)

    def update_debris(self, dt):
        for d in self.debris:
            d[1] += d[5] * dt          # y
            d[5] += 900 * dt           # gravity accel
            d[0] += d[4] * dt          # sideways drift
        self.debris = [d for d in self.debris if d[1] < H + 60]


# ---------- rendering ----------
def draw_block(surf, x, y, w, color):
    rect = pygame.Rect(int(x), int(y), int(w), BLOCK_H)
    pygame.draw.rect(surf, color, rect)
    dark = tuple(max(0, c - 55) for c in color)
    pygame.draw.rect(surf, dark, rect, 2)
    # soft highlight
    light = tuple(min(255, c + 40) for c in color)
    pygame.draw.line(surf, light, (rect.x + 3, rect.y + 3),
                     (rect.right - 4, rect.y + 3), 2)


def render(screen, game, font_big, font_small):
    screen.fill((24, 26, 38))
    # danger line (dashed)
    x = 0
    while x < W:
        pygame.draw.line(screen, (220, 70, 70), (x, DANGER_Y),
                         (min(x + 18, W), DANGER_Y), 2)
        x += 30
    screen.blit(font_small.render("TOP LINE", True, (230, 90, 90)),
                (W - 78, DANGER_Y - 22))

    # tower
    for i, (bx, bw) in enumerate(game.stack):
        by = BASE_Y - (i + 1) * BLOCK_H
        draw_block(screen, bx, by, bw, block_color(i))
    # ground
    pygame.draw.rect(screen, (44, 48, 60), (0, BASE_Y, W, H - BASE_Y))

    # current swinging/falling block
    if game.state == "play" and game.cur and game.cur["x"] is not None:
        c = game.cur
        col = block_color(len(game.stack))
        draw_block(screen, c["x"], c["y"], c["w"], col)
        # guide line under the swinging block
        if c["state"] == "swing" and not c["dropping"]:
            pygame.draw.line(screen, (70, 74, 92),
                             (int(c["x"] + c["w"] / 2), int(c["y"] + BLOCK_H)),
                             (int(c["x"] + c["w"] / 2), game.top_y()), 1)

    # debris
    for d in game.debris:
        draw_block(screen, d[0], d[1], d[2], (150, 155, 170))

    # HUD
    screen.blit(font_small.render(f"SCORE {game.score}", True,
                                  (235, 235, 245)), (12, 8))
    screen.blit(font_small.render(f"BEST {game.best}", True,
                                  (160, 165, 185)), (12, 30))
    if game.msg and game.msg_timer > 0:
        screen.blit(font_small.render(game.msg, True, (255, 230, 120)),
                    (W // 2 - 90, DANGER_Y + 40))


def title_screen(screen, font_big, font_small, best):
    screen.fill((24, 26, 38))
    t1 = font_big.render("STACK GAME", True, (240, 240, 250))
    t2 = font_small.render("Drop the swinging block to build a tower.",
                           True, (190, 195, 215))
    t3 = font_small.render("Overhang gets sliced off - aim carefully!",
                           True, (190, 195, 215))
    t4 = font_small.render("Press SPACE to start", True, (255, 230, 120))
    t4b = font_small.render("SPACE = drop block   Q = quit", True, (190, 195, 215))
    t5 = font_small.render(f"BEST: {best}", True, (160, 165, 185))
    y = H // 2 - 140
    for t in (t1,):
        screen.blit(t, (W // 2 - t.get_width() // 2, y)); y += 70
    for t in (t4, t2, t3, t4b, t5):
        screen.blit(t, (W // 2 - t.get_width() // 2, y)); y += 34


def over_screen(screen, font_small, score, best):
    t1 = font_small.render(f"SCORE  {score}", True, (240, 240, 250))
    t2 = font_small.render(f"BEST   {best}", True, (160, 165, 185))
    t3 = font_small.render("R = retry    Q = quit", True, (190, 195, 215))
    y = H // 2 - 60
    for t in (t1, t2, t3):
        screen.blit(t, (W // 2 - t.get_width() // 2, y)); y += 40


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Stack Game")
    clock = pygame.time.Clock()
    font_big = pygame.font.Font(None, 64)
    font_small = pygame.font.Font(None, 26)

    best = load_best()
    state = "title"
    game = None

    while True:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_q:
                    pygame.quit(); sys.exit()
                if ev.key == pygame.K_SPACE:
                    if state == "title":
                        game = Game()
                        state = "play"
                    elif state == "play" and game and not game.cur["dropping"]:
                        game.drop()
                if ev.key == pygame.K_r and state == "over":
                    game = Game()
                    state = "play"

        if state == "title":
            title_screen(screen, font_big, font_small, best)
            pygame.display.update()
            continue

        if state == "play":
            if game.cur["state"] == "swing" and not game.cur["dropping"]:
                game.update_swing(dt)
            else:
                game.update_fall(dt)
            game.update_debris(dt)
            if game.msg_timer > 0:
                game.msg_timer -= dt
            if game.state == "over":
                state = "over"
        elif state == "over":
            game.update_debris(dt)

        render(screen, game, font_big, font_small)
        if state == "over":
            over_screen(screen, font_small, game.score, game.best)
        pygame.display.update()


if __name__ == "__main__":
    main()
