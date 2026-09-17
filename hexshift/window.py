"""Cross-platform windowed Hexshift client (pygame-ce)."""

from __future__ import annotations

import math
import time

from hexshift.ai import tick_ais
from hexshift.constants import (
    ABILITY_COLORS,
    ABILITY_OFFSETS,
    AI_PERIOD,
    COLOR_SOLID,
    DRAW_SIZE,
    HUD_MARGIN,
    HUMAN,
    LARGE_KINDS,
    MEGA_CENTER_SIZE,
    MEGA_ICON_SIZE,
    MEGA_INNER_SIZE,
    PLAYER_NAMES,
    PLAYERS,
    RULES_TEXT,
    SAVE_PERIOD,
    boost_alpha,
)
from hexshift.draw import _job_frac, _owner_fill, _stroke_for
from hexshift.game import Game
from hexshift.hexmath import hex_corners, hex_distance
from hexshift.hud import apply_hud_action, hit_hud, layout_hud
from hexshift.save import load_game, save_game

BG = (18, 20, 24)
DEFAULT_W, DEFAULT_H = 1280, 720


def _rgb(rgba, alpha=None):
    r, g, b = rgba[0], rgba[1], rgba[2]
    a = rgba[3] if len(rgba) > 3 else 1.0
    if alpha is not None:
        a = alpha
    return (
        max(0, min(255, int(r * 255))),
        max(0, min(255, int(g * 255))),
        max(0, min(255, int(b * 255))),
        max(0, min(255, int(a * 255))),
    )


def _fill_hex(surf, cx, cy, size, fill, stroke=None, width=1):
    import pygame

    pts = [(int(x), int(y)) for x, y in hex_corners(cx, cy, size)]
    pygame.draw.polygon(surf, _rgb(fill), pts)
    if stroke:
        pygame.draw.polygon(surf, _rgb(stroke), pts, max(1, int(width)))


def _progress_stroke(surf, cx, cy, size, frac, rgba, width=2):
    import pygame

    frac = max(0.0, min(1.0, frac))
    if frac <= 0:
        return
    pts = hex_corners(cx, cy, size)
    pts.append(pts[0])
    segs = []
    total = 0.0
    for i in range(6):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        length = math.hypot(x1 - x0, y1 - y0)
        segs.append((x0, y0, x1, y1, length))
        total += length
    remain = total * frac
    drawn = []
    for x0, y0, x1, y1, length in segs:
        if remain <= 0:
            break
        t = min(1.0, remain / length) if length else 1.0
        xe = x0 + (x1 - x0) * t
        ye = y0 + (y1 - y0) * t
        if not drawn:
            drawn.append((x0, y0))
        drawn.append((xe, ye))
        remain -= length
    if len(drawn) >= 2:
        pygame.draw.lines(surf, _rgb(rgba), False, drawn, max(1, int(width)))


def _icon(surf, kind, cx, cy, s, color=(255, 255, 255)):
    import pygame

    w = max(1, int(s * 0.12))
    if kind == "eye":
        pygame.draw.circle(surf, color, (int(cx), int(cy)), int(s * 0.22))
        pygame.draw.ellipse(
            surf, color, pygame.Rect(cx - s * 0.55, cy - s * 0.28, s * 1.1, s * 0.56), w
        )
    elif kind == "hourglass":
        pygame.draw.polygon(
            surf,
            color,
            [
                (cx - s * 0.32, cy - s * 0.4),
                (cx + s * 0.32, cy - s * 0.4),
                (cx - s * 0.32, cy + s * 0.4),
                (cx + s * 0.32, cy + s * 0.4),
            ],
            w,
        )
    elif kind == "shield":
        pygame.draw.polygon(
            surf,
            color,
            [
                (cx, cy - s * 0.45),
                (cx + s * 0.34, cy - s * 0.18),
                (cx + s * 0.26, cy + s * 0.18),
                (cx, cy + s * 0.44),
                (cx - s * 0.26, cy + s * 0.18),
                (cx - s * 0.34, cy - s * 0.18),
            ],
            w,
        )
    elif kind == "blade":
        pygame.draw.polygon(
            surf,
            color,
            [
                (cx - s * 0.34, cy + s * 0.32),
                (cx + s * 0.36, cy - s * 0.42),
                (cx + s * 0.16, cy + s * 0.05),
            ],
        )
    elif kind == "shockwave":
        for rad in (0.22, 0.38, 0.52):
            pygame.draw.arc(
                surf,
                color,
                pygame.Rect(cx - s * rad, cy - s * rad, s * rad * 2, s * rad * 2),
                -2.2,
                0.8,
                w,
            )
    elif kind == "forge":
        pygame.draw.rect(surf, color, pygame.Rect(cx - s * 0.42, cy - s * 0.06, s * 0.84, s * 0.2))
        pygame.draw.rect(surf, color, pygame.Rect(cx - s * 0.16, cy - s * 0.36, s * 0.32, s * 0.34))
    elif kind == "factory":
        pygame.draw.rect(surf, color, pygame.Rect(cx - s * 0.46, cy + s * 0.04, s * 0.26, s * 0.36))
        pygame.draw.rect(surf, color, pygame.Rect(cx - s * 0.16, cy - s * 0.1, s * 0.3, s * 0.5))
        pygame.draw.rect(surf, color, pygame.Rect(cx + s * 0.16, cy - s * 0.32, s * 0.26, s * 0.72))
    else:
        pygame.draw.circle(surf, color, (int(cx), int(cy)), int(s * 0.28), w)


def _draw_choice(surf, game: Game):
    center = game.choice.center
    cells = sorted(game.choice.cells, key=lambda k: hex_distance(k, center), reverse=True)
    for key in cells:
        tile = game.tiles.get(key)
        if not tile:
            continue
        cx, cy = game.pixel(*key)
        dq, dr = key[0] - center[0], key[1] - center[1]
        kind = ABILITY_OFFSETS.get((dq, dr))
        dist = hex_distance(key, center)
        size = MEGA_INNER_SIZE if dist <= 1 else DRAW_SIZE
        if kind:
            r, g, b = ABILITY_COLORS.get(kind, (0.8, 0.8, 0.8))
            _fill_hex(
                surf,
                cx,
                cy,
                size,
                (r, g, b, boost_alpha(0.72)),
                (r, g, b, boost_alpha(0.95)),
                2,
            )
            _icon(surf, kind, cx, cy, 11.5 if dist <= 1 else 8.5)
        else:
            _fill_hex(surf, cx, cy, size, _owner_fill(tile.owner), _stroke_for(tile.owner))


def _draw_mega_body(surf, game: Game, mega):
    cell_pts = {c: game.pixel(*c) for c in mega.cells}
    cx0, cy0 = cell_pts[mega.center]
    r, g, b, _ = COLOR_SOLID[mega.owner]
    fill = _owner_fill(mega.owner)
    stroke = _stroke_for(mega.owner)
    ar, ag, ab = ABILITY_COLORS.get(mega.kind, (r, g, b))
    large = mega.kind in LARGE_KINDS or len(mega.cells) > 7
    center_fill = (ar, ag, ab, fill[3])
    center_stroke = (ar, ag, ab, boost_alpha(0.95))
    inner_fill = (
        ar * 0.65 + r * 0.35,
        ag * 0.65 + g * 0.35,
        ab * 0.65 + b * 0.35,
        fill[3],
    )
    order = sorted(mega.cells, key=lambda c: hex_distance(c, mega.center), reverse=True)
    for c in order:
        cx, cy = cell_pts[c]
        size = game.mega_cell_size(mega, c)
        dist = hex_distance(c, mega.center)
        if dist == 0:
            _fill_hex(surf, cx, cy, size, center_fill, center_stroke, 2)
        elif large and dist == 1:
            _fill_hex(surf, cx, cy, size, inner_fill, center_stroke, 2)
        else:
            _fill_hex(surf, cx, cy, size, fill, stroke, 2)
    _icon(surf, mega.kind, cx0, cy0, MEGA_ICON_SIZE)
    return cell_pts


def draw_world_static(surf, game: Game):
    vis = game.visible_set(HUMAN)
    choice_cells = set(game.choice.cells) if game.choice else set()
    drawn_megas = set()
    for key in vis:
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if key in choice_cells:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn_megas:
                continue
            drawn_megas.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if mega:
                _draw_mega_body(surf, game, mega)
            continue
        cx, cy = game.pixel(tile.q, tile.r)
        _fill_hex(surf, cx, cy, DRAW_SIZE, _owner_fill(tile.owner), _stroke_for(tile.owner))
        if tile.shielded:
            import pygame

            pygame.draw.polygon(
                surf,
                _rgb((0.92, 0.95, 1.0, boost_alpha(0.9))),
                [
                    (cx, cy - 3.2),
                    (cx + 3.0, cy - 0.6),
                    (cx, cy + 3.4),
                    (cx - 3.0, cy - 0.6),
                ],
                1,
            )
    if game.choice:
        _draw_choice(surf, game)


def draw_world_fx(surf, game: Game):
    vis = game.visible_set(HUMAN)
    active, queued = game.job_maps()
    drawn = set()
    for key, job in active.items():
        if key not in vis:
            continue
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn:
                continue
            drawn.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if mega:
                for c in mega.cells:
                    px, py = game.pixel(*c)
                    _progress_stroke(
                        surf,
                        px,
                        py,
                        game.mega_cell_size(mega, c),
                        _job_frac(job),
                        COLOR_SOLID[job.owner],
                        3,
                    )
            continue
        cx, cy = game.pixel(*key)
        _progress_stroke(surf, cx, cy, DRAW_SIZE, _job_frac(job), COLOR_SOLID[job.owner], 2)
    for key in queued:
        if key not in vis or key in active:
            continue
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn:
                continue
            drawn.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if mega:
                for c in mega.cells:
                    px, py = game.pixel(*c)
                    _progress_stroke(
                        surf, px, py, game.mega_cell_size(mega, c), 1.0, COLOR_SOLID[HUMAN], 2
                    )
            continue
        cx, cy = game.pixel(*key)
        _progress_stroke(surf, cx, cy, DRAW_SIZE, 1.0, COLOR_SOLID[HUMAN], 1)
    for merge in game.merges:
        if merge.center not in vis and merge.owner != HUMAN:
            continue
        frac = 1.0 - merge.remaining / merge.duration if merge.duration else 1.0
        ar, ag, ab = ABILITY_COLORS.get(merge.kind, COLOR_SOLID[merge.owner][:3])
        tint = (ar, ag, ab, boost_alpha(0.55))
        ring = (ar, ag, ab, 1.0)
        large = merge.kind in LARGE_KINDS or len(merge.cells) > 7
        for c in merge.cells:
            px, py = game.pixel(*c)
            dist = hex_distance(c, merge.center)
            if large and dist <= 1:
                size = MEGA_INNER_SIZE
            elif not large and c == merge.center:
                size = MEGA_CENTER_SIZE
            else:
                size = DRAW_SIZE
            _fill_hex(surf, px, py, size, tint)
            _progress_stroke(surf, px, py, size, frac, ring, 2)
        cx, cy = game.pixel(*merge.center)
        _icon(surf, merge.kind, cx, cy, 12)
    for deco in game.deconstructs:
        mega = game.megas.get(deco.mega_id)
        if not mega or mega.center not in vis or mega.id in drawn:
            continue
        frac = 1.0 - deco.remaining / deco.duration if deco.duration else 1.0
        for c in mega.cells:
            px, py = game.pixel(*c)
            _progress_stroke(
                surf, px, py, game.mega_cell_size(mega, c), frac, (0.95, 0.55, 0.35, 1.0), 3
            )


def _round_rect(surf, rect, color, radius=8):
    import pygame

    pygame.draw.rect(surf, color, rect, border_radius=radius)


def draw_hud(surf, game, banners, score, chrome, fonts, help_open=False):
    import pygame

    font, small = fonts
    tab = chrome.get("tab")
    if tab:
        tx, ty, tw, th = tab
        _round_rect(surf, pygame.Rect(tx, ty, tw, th), (22, 24, 28, 220), 7)
        surf.blit(font.render("HUD", True, (255, 255, 255)), (tx + 10, ty + 6))
        return
    sx, sy, sw, sh = score
    _round_rect(surf, pygame.Rect(sx, sy, sw, sh), (16, 18, 22, 210), 8)
    surf.blit(font.render("Score", True, (230, 230, 230)), (sx + 10, sy + 4))
    info = chrome.get("info")
    if info:
        ix, iy, iw, ih = info
        pygame.draw.circle(surf, (255, 255, 255), (int(ix + iw / 2), int(iy + ih / 2)), 7, 1)
        surf.blit(small.render("i", True, (255, 255, 255)), (ix + 5, iy + 1))
    collapse = chrome.get("collapse")
    if collapse:
        x, y, w, h = collapse
        pygame.draw.lines(
            surf,
            (220, 220, 220),
            False,
            [(x + 4, y + 6), (x + w / 2, y + h - 5), (x + w - 4, y + 6)],
            2,
        )
    for i, pid in enumerate(PLAYERS):
        yy = sy + 18 + i * 22
        r, g, b, _ = COLOR_SOLID[pid]
        pygame.draw.rect(surf, _rgb((r, g, b, 1)), pygame.Rect(sx + 10, yy + 4, 10, 10))
        label = font.render(f"{PLAYER_NAMES[pid]}  {game.tile_count(pid)} tiles", True, (255, 255, 255))
        surf.blit(label, (sx + 26, yy + 2))
    meta_y = sy + 18 + len(PLAYERS) * 22 + 6
    cap_used = len(game.active[HUMAN])
    cap_max = game.capture_slots(HUMAN)
    build_used = sum(1 for m in game.merges if m.owner == HUMAN)
    build_max = game.merge_slots(HUMAN)
    surf.blit(font.render(f"Tiles left  {game.tiles_left()}", True, (220, 220, 220)), (sx + 10, meta_y))
    surf.blit(
        font.render(f"Capture {cap_used}/{cap_max}   Build {build_used}/{build_max}", True, (220, 220, 220)),
        (sx + 10, meta_y + 16),
    )
    if game.finished:
        msg = f"{PLAYER_NAMES[game.winners[0]]} wins" if len(game.winners) == 1 else "Draw"
        surf.blit(font.render(msg, True, (240, 210, 90)), (sx + 10, meta_y + 32))
    hint = small.render("P pause   N new   F11 full   Esc quit", True, (160, 160, 160))
    surf.blit(hint, (sx + 10, sy + sh - 16))
    for b in banners:
        r, g, bl = b.color
        rect = pygame.Rect(b.x, b.y, b.w, b.h)
        if b.progress is None:
            _round_rect(surf, rect, _rgb((r, g, bl, boost_alpha(0.78))), 7)
        else:
            _round_rect(surf, rect, (20, 22, 26, 210), 7)
            fill_w = max(0, min(b.w, int(b.w * b.progress)))
            if fill_w > 1:
                bar = pygame.Surface((b.w, b.h), pygame.SRCALPHA)
                _round_rect(bar, pygame.Rect(0, 0, b.w, b.h), _rgb((r, g, bl, boost_alpha(0.88))), 7)
                surf.blit(bar, (b.x, b.y), pygame.Rect(0, 0, fill_w, b.h))
        surf.blit(font.render(b.title[:28], True, (255, 255, 255)), (b.x + 10, b.y + 4))
        surf.blit(small.render(b.subtitle[:42], True, (230, 235, 240)), (b.x + 10, b.y + 18))
        if b.cancellable and b.close:
            cx, cy, cw, ch = b.close
            pygame.draw.line(surf, (255, 255, 255), (cx + 3, cy + 3), (cx + cw - 3, cy + ch - 3), 2)
            pygame.draw.line(surf, (255, 255, 255), (cx + cw - 3, cy + 3), (cx + 3, cy + ch - 3), 2)
    if help_open:
        panel = pygame.Rect(HUD_MARGIN, HUD_MARGIN, min(520, surf.get_width() - 40), min(560, surf.get_height() - 40))
        _round_rect(surf, panel, (12, 14, 18, 240), 10)
        y = panel.y + 12
        surf.blit(font.render("How to play  (press I or Esc)", True, (255, 255, 255)), (panel.x + 14, y))
        y += 22
        for line in RULES_TEXT.splitlines():
            if y > panel.bottom - 20:
                break
            surf.blit(small.render(line[:72], True, (220, 220, 220)), (panel.x + 14, y))
            y += 15


def draw_tooltip(surf, font, text, x, y, width, height):
    import pygame

    if not text:
        return
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) <= 38:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    imgs = [font.render(line, True, (255, 255, 255)) for line in lines]
    box_w = max(im.get_width() for im in imgs) + 20
    box_h = 16 * len(imgs) + 16
    tx = min(max(8, x + 14), width - box_w - 8)
    ty = min(max(8, y - box_h - 10), height - box_h - 8)
    _round_rect(surf, pygame.Rect(tx, ty, box_w, box_h), (12, 14, 18, 235), 6)
    for i, im in enumerate(imgs):
        surf.blit(im, (tx + 10, ty + 8 + i * 16))


def run(fast=False, new_game=False):
    import pygame

    pygame.init()
    pygame.display.set_caption("Hexshift")
    screen = pygame.display.set_mode((DEFAULT_W, DEFAULT_H), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    try:
        fonts = (pygame.font.SysFont("sans", 14), pygame.font.SysFont("sans", 12))
    except Exception:
        fonts = (pygame.font.Font(None, 18), pygame.font.Font(None, 16))

    game = None if new_game else load_game(fast=fast)
    if game is None:
        game = Game(fast=fast)
        game.generate(DEFAULT_W, DEFAULT_H)
    else:
        game.fast = fast
        game._times()
        game.set_size(DEFAULT_W, DEFAULT_H)

    ai_accum = [0.0, 0.0, 0.0, 0.0]
    save_accum = 0.0
    last = time.monotonic()
    hud_collapsed = False
    help_open = False
    pending_new = 0.0
    last_click = 0.0
    last_pos = (0, 0)
    hover = None
    cache = None
    cache_key = None
    fullscreen = False
    running = True

    def persist():
        try:
            save_game(game)
        except OSError:
            pass

    def rebuild_cache():
        nonlocal cache, cache_key
        w, h = screen.get_size()
        key = (w, h, game.world_rev)
        if cache is not None and cache_key == key:
            return cache
        cache = pygame.Surface((w, h), pygame.SRCALPHA)
        cache.fill((0, 0, 0, 0))
        draw_world_static(cache, game)
        cache_key = key
        return cache

    while running:
        now = time.monotonic()
        dt = min(1.0, now - last)
        last = now
        game.update(dt)
        tick_ais(game, ai_accum, dt, AI_PERIOD)
        if game.need_save:
            save_accum += dt
            if save_accum >= SAVE_PERIOD:
                persist()
                save_accum = 0.0
        else:
            save_accum = 0.0

        w, h = screen.get_size()
        moved = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                game.set_size(event.w, event.h)
                cache_key = None
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    if help_open:
                        help_open = False
                    else:
                        running = False
                elif event.key == pygame.K_p:
                    game.paused = not game.paused
                    game.need_save = True
                    game.dirty = True
                elif event.key == pygame.K_i:
                    help_open = not help_open
                    game.dirty = True
                elif event.key == pygame.K_h:
                    hud_collapsed = not hud_collapsed
                    game.dirty = True
                elif event.key == pygame.K_n:
                    if now - pending_new < 2.0:
                        game.fast = fast
                        game.generate(w, h)
                        persist()
                        pending_new = 0.0
                        cache_key = None
                    else:
                        pending_new = now
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
                    screen = pygame.display.set_mode((0, 0) if fullscreen else (DEFAULT_W, DEFAULT_H), flags)
                    game.set_size(*screen.get_size())
                    cache_key = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                x, y = event.pos
                double = (now - last_click) < 0.4 and math.hypot(x - last_pos[0], y - last_pos[1]) < 8
                last_click, last_pos = now, (x, y)
                if help_open:
                    help_open = False
                    continue
                banners, score, chrome = layout_hud(game, w, h, collapsed=hud_collapsed)
                hit = hit_hud(banners, score, chrome, x, y)
                if hit:
                    kind, payload = hit if isinstance(hit, tuple) else (hit, None)
                    if kind == "info":
                        help_open = True
                    elif kind in ("collapse", "tab"):
                        hud_collapsed = not hud_collapsed
                    elif kind != "hud":
                        apply_hud_action(game, hit)
                    game.dirty = True
                else:
                    game.click(x, y, double=double)
                    game.dirty = True
            elif event.type == pygame.MOUSEMOTION:
                hover = event.pos
                moved = True

        need = (
            game.dirty
            or game.animating()
            or help_open
            or moved
            or (pending_new and now - pending_new < 2.0)
        )
        if need:
            screen.fill(BG)
            screen.blit(rebuild_cache(), (0, 0))
            fx = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            draw_world_fx(fx, game)
            screen.blit(fx, (0, 0))
            banners, score, chrome = layout_hud(game, w, h, collapsed=hud_collapsed)
            hud = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            draw_hud(hud, game, banners, score, chrome, fonts, help_open=help_open)
            if pending_new and now - pending_new < 2.0:
                msg = fonts[0].render("Press N again to start a new map", True, (255, 220, 120))
                screen.blit(msg, (HUD_MARGIN, HUD_MARGIN))
            screen.blit(hud, (0, 0))
            if hover and not help_open:
                info = game.hover_info(*hover)
                if info:
                    draw_tooltip(screen, fonts[1], info, hover[0], hover[1], w, h)
            pygame.display.flip()
            game.dirty = False

        clock.tick(30)

    persist()
    pygame.quit()
    return 0
