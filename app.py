#!/usr/bin/env python3
"""Shared shell: the window, the font, the message log and the state stack.

State stack after steelx/py-rpg-01: every state renders, only the top one updates
and takes input, and a state pops itself by setting `done`. A state is any object
with `update(dt)`, `draw()`, `on_key(key)` and `done`.
"""
import textwrap

import pygame

import castle
import interior
import npc
import sounds
import sprites
import tileset
import village

NAME = "The Last Slayer: Project 2026"
WHITE, BLACK, RED = (255, 255, 255), (0, 0, 0), (200, 40, 40)
SIZE = (640, 480)
STATUS = pygame.Rect(16, 16, 180, 154)
MENU_AT = (16, 178)
LOGWIN = pygame.Rect(16, 340, 608, 124)


def rect(x, y, w, h):
    return pygame.Rect(int(x), int(y), int(w), int(h))


def window(surf, r):
    pygame.draw.rect(surf, BLACK, r)
    pygame.draw.rect(surf, WHITE, r, 3)


class MessageLog:
    """Letters appear one by one, the window scrolls when it fills."""

    TOTAL_LINES = 4
    SPEED = 55.0            # letters per second
    PAUSE = 0.45            # beat between messages

    def __init__(self, chars_per_line=44):
        self.chars_per_line = chars_per_line
        self.lines = []
        self.pending = []
        self.revealed = 0.0
        self.typing = False
        self.last_of_msg = True
        self.delay = 0.0

    def clear(self):
        self.__init__(self.chars_per_line)

    def push(self, text):
        wrapped = textwrap.wrap(text, self.chars_per_line) or [""]
        for i, line in enumerate(wrapped):
            self.pending.append((line, i == len(wrapped) - 1))

    @property
    def idle(self):
        return not (self.pending or self.typing) and self.delay <= 0

    def skip(self):
        if self.typing:
            self.revealed = len(self.lines[-1])
            self.typing = False
            self.delay = self.PAUSE if self.last_of_msg else 0.0
        else:
            self.delay = 0.0

    def update(self, dt):
        if self.typing:
            self.revealed += self.SPEED * dt
            if self.revealed >= len(self.lines[-1]):
                self.skip()
            return
        if self.delay > 0:
            self.delay = max(0.0, self.delay - dt)
            return
        if self.pending:
            line, self.last_of_msg = self.pending.pop(0)
            self.lines.append(line)
            if len(self.lines) > self.TOTAL_LINES:
                self.lines.pop(0)
            self.revealed, self.typing = 0.0, True


class App:
    def __init__(self, title=NAME):
        pygame.init()
        sounds.init()
        self.screen = pygame.display.set_mode(SIZE)
        sprites.load()                           # these need the display for
        tileset.load()                           # convert_alpha, so load them here
        interior.load()
        village.load()
        castle.load()
        npc.load()
        pygame.display.set_caption(title)
        self.font = pygame.font.SysFont("couriernew,menlo,dejavusansmono,monospace", 18, bold=True)
        self.clock = pygame.time.Clock()
        self.log = MessageLog((LOGWIN.w - 28) // self.font.size("M")[0])
        self.states = []

    @property
    def top(self):
        return self.states[-1]

    def push(self, state):
        self.states.append(state)

    def text(self, s, x, y, color=WHITE):
        self.screen.blit(self.font.render(s, True, color), (x, y))

    def draw_status(self, hero):
        window(self.screen, STATUS)
        for i, line in enumerate([hero.name, f"LV:{hero.level:>4}", f"HP:{hero.hp:>4}",
                                  f"MP:{hero.mp:>4}", f"G: {hero.gold:>4}",
                                  f"E: {hero.exp:>4}", f"HERB:{hero.herbs:>2}"]):
            self.text(line, STATUS.x + 14, STATUS.y + 10 + i * 20)

    def draw_log(self):
        window(self.screen, LOGWIN)
        for i, line in enumerate(self.log.lines):
            shown = line if i < len(self.log.lines) - 1 else line[:int(self.log.revealed)]
            self.text(shown, LOGWIN.x + 14, LOGWIN.y + 12 + i * 22)

    def run(self):
        while self.states:
            dt = self.clock.tick(60) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_q and e.mod & pygame.KMOD_META:
                        return
                    self.top.on_key(e.key)
            self.log.update(dt)
            self.top.update(dt)
            self.screen.fill(BLACK)
            for state in self.states:
                state.draw()
            pygame.display.flip()
            if self.top.done:
                self.states.pop()
