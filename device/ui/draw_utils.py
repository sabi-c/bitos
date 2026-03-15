import pygame


def draw_wifi(surf, x, y, w, h, color):
    cx = x + w // 2
    cy = y + h - 2
    widths = [max(1, w // 6), max(1, w // 5), max(1, w // 4)]
    heights = [max(1, h // 4), max(1, h // 3), max(1, h // 2)]
    for rw, rh in zip(widths, heights):
        rect = pygame.Rect(cx - rw, cy - rh, rw * 2, rh * 2)
        pygame.draw.arc(surf, color, rect, 3.5, 5.93, 1)
    pygame.draw.circle(surf, color, (cx, cy), 1)


def draw_battery(surf, x, y, w, h, color):
    body_w = max(4, w - 3)
    body_h = max(4, h)
    body = pygame.Rect(x, y, body_w, body_h)
    pygame.draw.rect(surf, color, body, 1)
    nub = pygame.Rect(x + body_w, y + body_h // 3, 3, max(2, body_h // 3))
    pygame.draw.rect(surf, color, nub)
    fill = pygame.Rect(x + 2, y + 2, int((body_w - 4) * 0.65), max(1, body_h - 4))
    pygame.draw.rect(surf, color, fill)


def draw_lock(surf, x, y, w, h, color):
    body = pygame.Rect(x + w // 5, y + h // 2, w - (2 * (w // 5)), h // 2)
    pygame.draw.rect(surf, color, body, 1)
    shackle = pygame.Rect(x + w // 4, y, w // 2, h // 2 + 2)
    pygame.draw.arc(surf, color, shackle, 3.14, 6.28, 1)
    keyhole = pygame.Rect(x + w // 2 - 1, y + (3 * h) // 4 - 2, 2, 4)
    pygame.draw.rect(surf, color, keyhole)


def draw_mail(surf, x, y, w, h, color):
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, color, rect, 1)
    pygame.draw.lines(
        surf,
        color,
        False,
        [(x + 1, y + 1), (x + w // 2, y + h // 2), (x + w - 1, y + 1)],
        1,
    )


def draw_settings(surf, x, y, w, h, color):
    cx = x + w // 2
    cy = y + h // 2
    r = min(w, h) // 4
    pygame.draw.circle(surf, color, (cx, cy), r, 1)
    tooth_r = min(w, h) // 2 - 1
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
        pygame.draw.circle(surf, color, (cx + dx * tooth_r // 2, cy + dy * tooth_r // 2), 1)


def draw_ai(surf, x, y, w, h, color):
    bubble = pygame.Rect(x, y, w, h - 3)
    pygame.draw.rect(surf, color, bubble, 1)
    for i in range(3):
        pygame.draw.circle(surf, color, (x + (w // 4) + (i * (w // 4)), y + h // 2 - 1), 1)
    pygame.draw.rect(surf, color, (x + w // 3, y + h - 3, 1, 3))
    pygame.draw.rect(surf, color, (x + (2 * w) // 3, y + h - 3, 1, 3))
