import math

from hexshift.constants import (
    ABILITY_COLORS,
    ABILITY_OFFSETS,
    COLOR_SOLID,
    COLORS,
    DRAW_SIZE,
    HUMAN,
    LARGE_KINDS,
    MEGA_CENTER_SIZE,
    MEGA_ICON_SIZE,
    MEGA_INNER_SIZE,
    UNOWNED,
    UNOWNED_STROKE,
    boost_alpha,
)
from hexshift.game import Game, Job
from hexshift.hexmath import hex_bbox, hex_corners, hex_distance


def _set_rgba(cr, rgba):
    cr.set_source_rgba(*rgba)


def _fill_hex(cr, cx, cy, size, fill, stroke=None, width=1.2):
    pts = hex_corners(cx, cy, size)
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.close_path()
    _set_rgba(cr, fill)
    cr.fill_preserve()
    if stroke:
        _set_rgba(cr, stroke)
        cr.set_line_width(width)
        cr.stroke()
    else:
        cr.new_path()


def _progress_stroke(cr, cx, cy, size, frac, rgba, width=2.2):
    frac = max(0.0, min(1.0, frac))
    if frac <= 0:
        return
    pts = hex_corners(cx, cy, size)
    pts.append(pts[0])
    total = 0.0
    segs = []
    for i in range(6):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        length = math.hypot(x1 - x0, y1 - y0)
        segs.append((x0, y0, x1, y1, length))
        total += length
    remain = total * frac
    _set_rgba(cr, rgba)
    cr.set_line_width(width)
    cr.set_line_cap(1)  # ROUND
    cr.set_line_join(1)
    started = False
    for x0, y0, x1, y1, length in segs:
        if remain <= 0:
            break
        t = min(1.0, remain / length) if length else 1.0
        xe = x0 + (x1 - x0) * t
        ye = y0 + (y1 - y0) * t
        if not started:
            cr.move_to(x0, y0)
            started = True
        cr.line_to(xe, ye)
        remain -= length
    cr.stroke()


def _owner_fill(owner):
    if owner is None:
        return UNOWNED
    return COLORS[owner]


def _stroke_for(owner):
    if owner is None:
        return UNOWNED_STROKE
    r, g, b, _ = COLOR_SOLID[owner]
    return (r, g, b, boost_alpha(0.85))


def draw_icon(cr, kind, cx, cy, s, rgba=(1, 1, 1, boost_alpha(0.95))):
    _set_rgba(cr, rgba)
    cr.set_line_width(max(1.4, s * 0.14))
    cr.set_line_cap(1)
    cr.set_line_join(1)
    if kind == "eye":
        cr.arc(cx, cy, s * 0.32, 0, math.tau)
        cr.fill()
        cr.move_to(cx - s * 0.62, cy)
        cr.curve_to(cx - s * 0.18, cy - s * 0.5, cx + s * 0.18, cy - s * 0.5, cx + s * 0.62, cy)
        cr.curve_to(cx + s * 0.18, cy + s * 0.5, cx - s * 0.18, cy + s * 0.5, cx - s * 0.62, cy)
        cr.stroke()
    elif kind == "hourglass":
        cr.move_to(cx - s * 0.38, cy - s * 0.48)
        cr.line_to(cx + s * 0.38, cy - s * 0.48)
        cr.line_to(cx - s * 0.38, cy + s * 0.48)
        cr.line_to(cx + s * 0.38, cy + s * 0.48)
        cr.close_path()
        cr.stroke()
        cr.move_to(cx - s * 0.12, cy)
        cr.line_to(cx + s * 0.12, cy)
        cr.stroke()
    elif kind == "shield":
        cr.move_to(cx, cy - s * 0.52)
        cr.line_to(cx + s * 0.42, cy - s * 0.22)
        cr.line_to(cx + s * 0.34, cy + s * 0.22)
        cr.line_to(cx, cy + s * 0.52)
        cr.line_to(cx - s * 0.34, cy + s * 0.22)
        cr.line_to(cx - s * 0.42, cy - s * 0.22)
        cr.close_path()
        cr.stroke()
    elif kind == "blade":
        cr.move_to(cx - s * 0.42, cy + s * 0.38)
        cr.line_to(cx + s * 0.06, cy - s * 0.12)
        cr.line_to(cx + s * 0.42, cy - s * 0.48)
        cr.line_to(cx + s * 0.2, cy + s * 0.06)
        cr.close_path()
        cr.fill()
    elif kind == "shockwave":
        for rad in (0.24, 0.42, 0.6):
            cr.arc(cx, cy, s * rad, -2.2, 0.8)
            cr.stroke()
    elif kind == "forge":
        cr.rectangle(cx - s * 0.48, cy - s * 0.06, s * 0.96, s * 0.24)
        cr.fill()
        cr.rectangle(cx - s * 0.2, cy - s * 0.42, s * 0.4, s * 0.4)
        cr.fill()
        cr.rectangle(cx - s * 0.34, cy + s * 0.2, s * 0.68, s * 0.2)
        cr.fill()
    elif kind == "factory":
        cr.rectangle(cx - s * 0.52, cy + s * 0.06, s * 0.3, s * 0.42)
        cr.rectangle(cx - s * 0.2, cy - s * 0.12, s * 0.34, s * 0.58)
        cr.rectangle(cx + s * 0.18, cy - s * 0.38, s * 0.3, s * 0.84)
        cr.fill()
        cr.move_to(cx + s * 0.33, cy - s * 0.38)
        cr.line_to(cx + s * 0.33, cy - s * 0.58)
        cr.stroke()
    elif kind == "beacon":
        cr.move_to(cx, cy + s * 0.4)
        cr.line_to(cx, cy - s * 0.1)
        cr.stroke()
        cr.arc(cx, cy - s * 0.28, s * 0.22, 0, math.tau)
        cr.stroke()
    elif kind == "spring":
        cr.arc(cx, cy + s * 0.15, s * 0.28, 3.3, 6.1)
        cr.stroke()
        cr.arc(cx, cy - s * 0.1, s * 0.2, 3.3, 6.1)
        cr.stroke()
    elif kind == "bastion":
        cr.rectangle(cx - s * 0.35, cy - s * 0.15, s * 0.7, s * 0.5)
        cr.stroke()
        cr.move_to(cx - s * 0.35, cy - s * 0.15)
        cr.line_to(cx, cy - s * 0.5)
        cr.line_to(cx + s * 0.35, cy - s * 0.15)
        cr.stroke()
    elif kind == "spike":
        cr.move_to(cx, cy + s * 0.45)
        cr.line_to(cx, cy - s * 0.5)
        cr.move_to(cx - s * 0.22, cy - s * 0.05)
        cr.line_to(cx, cy - s * 0.5)
        cr.line_to(cx + s * 0.22, cy - s * 0.05)
        cr.stroke()
    elif kind == "ripple":
        cr.arc(cx, cy, s * 0.18, 0, math.tau)
        cr.stroke()
        cr.arc(cx, cy, s * 0.38, 0.4, 3.2)
        cr.stroke()
        cr.arc(cx, cy, s * 0.55, 3.5, 6.0)
        cr.stroke()
    elif kind == "anvil":
        cr.move_to(cx - s * 0.45, cy - s * 0.15)
        cr.line_to(cx + s * 0.45, cy - s * 0.15)
        cr.line_to(cx + s * 0.28, cy + s * 0.35)
        cr.line_to(cx - s * 0.28, cy + s * 0.35)
        cr.close_path()
        cr.stroke()
    elif kind == "workshop":
        cr.rectangle(cx - s * 0.4, cy - s * 0.1, s * 0.8, s * 0.45)
        cr.stroke()
        cr.move_to(cx - s * 0.15, cy - s * 0.1)
        cr.line_to(cx - s * 0.15, cy - s * 0.4)
        cr.line_to(cx + s * 0.15, cy - s * 0.4)
        cr.stroke()
    elif kind == "census":
        cr.move_to(cx - s * 0.35, cy + s * 0.35)
        cr.line_to(cx - s * 0.35, cy - s * 0.1)
        cr.line_to(cx, cy - s * 0.45)
        cr.line_to(cx + s * 0.35, cy - s * 0.1)
        cr.line_to(cx + s * 0.35, cy + s * 0.35)
        cr.stroke()
    elif kind == "grove":
        cr.arc(cx, cy - s * 0.05, s * 0.32, 0, math.tau)
        cr.stroke()
        cr.move_to(cx, cy + s * 0.25)
        cr.line_to(cx, cy + s * 0.48)
        cr.stroke()
    elif kind == "lantern":
        cr.rectangle(cx - s * 0.22, cy - s * 0.1, s * 0.44, s * 0.4)
        cr.stroke()
        cr.move_to(cx, cy - s * 0.1)
        cr.line_to(cx, cy - s * 0.4)
        cr.stroke()
        cr.arc(cx, cy - s * 0.1, s * 0.22, 3.14, 0)
        cr.stroke()
    elif kind == "keep":
        cr.rectangle(cx - s * 0.38, cy - s * 0.05, s * 0.76, s * 0.42)
        cr.stroke()
        for ox in (-0.38, 0, 0.38):
            cr.move_to(cx + s * ox, cy - s * 0.05)
            cr.line_to(cx + s * ox, cy - s * 0.38)
            cr.stroke()
    elif kind == "monument":
        cr.move_to(cx - s * 0.4, cy + s * 0.4)
        cr.line_to(cx, cy - s * 0.5)
        cr.line_to(cx + s * 0.4, cy + s * 0.4)
        cr.close_path()
        cr.stroke()
    else:
        cr.arc(cx, cy, s * 0.32, 0, math.tau)
        cr.stroke()


def _job_frac(job: Job):
    if job.duration <= 0:
        return 1.0
    return 1.0 - (job.remaining / job.duration)


def _mega_bbox(game: Game, mega):
    xs, ys = [], []
    for c in mega.cells:
        cx, cy = game.pixel(*c)
        size = game.mega_cell_size(mega, c)
        x, y, w, h = hex_bbox(cx, cy, size)
        xs.extend([x, x + w])
        ys.extend([y, y + h])
    if not xs:
        return 0, 0, 0, 0
    x0, y0 = min(xs), min(ys)
    return x0, y0, max(xs) - x0, max(ys) - y0


def collect_click_boxes(game: Game):
    boxes = []
    vis = game.visible_set(HUMAN)
    drawn_megas = set()
    for key in vis:
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn_megas:
                continue
            drawn_megas.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if not mega:
                continue
            boxes.append(_mega_bbox(game, mega))
            continue
        cx, cy = game.pixel(tile.q, tile.r)
        size = DRAW_SIZE
        if game.choice and key in game.choice.cells:
            if hex_distance(key, game.choice.center) <= 1:
                size = MEGA_INNER_SIZE
        boxes.append(hex_bbox(cx, cy, size))
    return boxes


def draw_world(cr, game: Game):
    draw_world_static(cr, game)
    draw_world_fx(cr, game)


def draw_world_static(cr, game: Game):
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
                _draw_mega_body(cr, game, mega)
            continue
        cx, cy = game.pixel(tile.q, tile.r)
        _fill_hex(cr, cx, cy, DRAW_SIZE, _owner_fill(tile.owner), _stroke_for(tile.owner), 1.0)
        if tile.shielded:
            _set_rgba(cr, (0.92, 0.95, 1.0, boost_alpha(0.9)))
            cr.set_line_width(1.3)
            cr.move_to(cx, cy - 3.2)
            cr.line_to(cx + 3.0, cy - 0.6)
            cr.line_to(cx, cy + 3.4)
            cr.line_to(cx - 3.0, cy - 0.6)
            cr.close_path()
            cr.stroke()
    if game.choice:
        _draw_choice(cr, game)


def draw_world_fx(cr, game: Game):
    vis = game.visible_set(HUMAN)
    active, queued = game.job_maps()
    drawn_megas = set()
    for key, job in active.items():
        if key not in vis:
            continue
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn_megas:
                continue
            drawn_megas.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if mega:
                _draw_mega_fx(cr, game, mega, job=job, queued=False)
            continue
        cx, cy = game.pixel(*key)
        _progress_stroke(cr, cx, cy, DRAW_SIZE, _job_frac(job), COLOR_SOLID[job.owner], 2.4)
    for key in queued:
        if key not in vis or key in active:
            continue
        tile = game.tiles.get(key)
        if not tile or not tile.land:
            continue
        if tile.mega_id is not None:
            if tile.mega_id in drawn_megas:
                continue
            drawn_megas.add(tile.mega_id)
            mega = game.megas.get(tile.mega_id)
            if mega:
                _draw_mega_fx(cr, game, mega, job=None, queued=True)
            continue
        cx, cy = game.pixel(*key)
        cr.set_dash((3, 2))
        _progress_stroke(cr, cx, cy, DRAW_SIZE, 1.0, COLOR_SOLID[HUMAN], 1.4)
        cr.set_dash([])
    for deco in game.deconstructs:
        mega = game.megas.get(deco.mega_id)
        if not mega or mega.center not in vis:
            continue
        if mega.id in drawn_megas:
            continue
        drawn_megas.add(mega.id)
        _draw_mega_fx(cr, game, mega, job=None, queued=False, deco=deco)


def _draw_choice(cr, game: Game):
    center = game.choice.center
    cells = sorted(
        game.choice.cells, key=lambda k: hex_distance(k, center), reverse=True
    )
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
                cr,
                cx,
                cy,
                size,
                (r, g, b, boost_alpha(0.72)),
                (r, g, b, boost_alpha(0.95)),
                1.8,
            )
            draw_icon(cr, kind, cx, cy, 11.5 if dist <= 1 else 8.5)
        else:
            _fill_hex(cr, cx, cy, size, _owner_fill(tile.owner), _stroke_for(tile.owner), 1.0)


def _draw_mega_body(cr, game: Game, mega):
    cell_pts = {c: game.pixel(*c) for c in mega.cells}
    cx0, cy0 = cell_pts[mega.center]
    r, g, b, _ = COLOR_SOLID[mega.owner]
    fill = _owner_fill(mega.owner)
    stroke = _stroke_for(mega.owner)
    ar, ag, ab = ABILITY_COLORS.get(mega.kind, (r, g, b))
    large = mega.kind in LARGE_KINDS or len(mega.cells) > 7
    center_fill = (ar, ag, ab, fill[3])
    center_stroke = (ar, ag, ab, boost_alpha(0.95))
    inner_fill = (ar * 0.65 + r * 0.35, ag * 0.65 + g * 0.35, ab * 0.65 + b * 0.35, fill[3])

    order = sorted(mega.cells, key=lambda c: hex_distance(c, mega.center), reverse=True)
    for c in order:
        cx, cy = cell_pts[c]
        size = game.mega_cell_size(mega, c)
        dist = hex_distance(c, mega.center)
        if dist == 0:
            _fill_hex(cr, cx, cy, size, center_fill, center_stroke, 1.5)
        elif large and dist == 1:
            _fill_hex(cr, cx, cy, size, inner_fill, center_stroke, 1.4)
        else:
            _fill_hex(cr, cx, cy, size, fill, stroke, 1.5)
    draw_icon(cr, mega.kind, cx0, cy0, MEGA_ICON_SIZE)
    return cell_pts


def _draw_mega_fx(cr, game: Game, mega, job=None, queued=False, deco=None):
    cell_pts = {c: game.pixel(*c) for c in mega.cells}

    def _ring_size(c):
        return game.mega_cell_size(mega, c)

    if deco:
        frac = 1.0 - deco.remaining / deco.duration if deco.duration else 1.0
        for c in mega.cells:
            cx, cy = cell_pts[c]
            _progress_stroke(cr, cx, cy, _ring_size(c), frac, (0.95, 0.55, 0.35, 1.0), 2.8)
    elif job:
        for c in mega.cells:
            cx, cy = cell_pts[c]
            _progress_stroke(cr, cx, cy, _ring_size(c), _job_frac(job), COLOR_SOLID[job.owner], 2.8)
    elif queued:
        cr.set_dash((4, 3))
        for c in mega.cells:
            cx, cy = cell_pts[c]
            _progress_stroke(cr, cx, cy, _ring_size(c), 1.0, COLOR_SOLID[HUMAN], 1.8)
        cr.set_dash([])


def _draw_mega(cr, game: Game, mega):
    _draw_mega_body(cr, game, mega)
    _draw_mega_fx(cr, game, mega)


def draw_merge_progress(cr, game: Game):
    vis = game.visible_set(HUMAN)
    for merge in game.merges:
        if merge.center not in vis and merge.owner != HUMAN:
            continue
        cx, cy = game.pixel(*merge.center)
        frac = 1.0 - merge.remaining / merge.duration if merge.duration else 1.0
        ar, ag, ab = ABILITY_COLORS.get(merge.kind, COLOR_SOLID[merge.owner][:3])
        tint = (ar, ag, ab, boost_alpha(0.55))
        ring = (ar, ag, ab, 1.0)
        large = merge.kind in LARGE_KINDS or len(merge.cells) > 7
        for c in sorted(merge.cells, key=lambda k: hex_distance(k, merge.center), reverse=True):
            px, py = game.pixel(*c)
            dist = hex_distance(c, merge.center)
            if large and dist <= 1:
                size = MEGA_INNER_SIZE
            elif not large and c == merge.center:
                size = MEGA_CENTER_SIZE
            else:
                size = DRAW_SIZE
            _fill_hex(cr, px, py, size, tint, None)
            _progress_stroke(cr, px, py, size, frac, ring, 2.6)
        draw_icon(cr, merge.kind, cx, cy, 12)


def _wrap_lines(text, max_chars=38):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) <= max_chars:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def draw_tooltip(cr, game: Game, x, y, width, height):
    info = game.hover_info(x, y)
    if not info:
        return
    lines = _wrap_lines(info)
    pad_x, pad_y = 10, 8
    line_h = 14
    cr.select_font_face("Sans")
    cr.set_font_size(11)
    max_w = max(cr.text_extents(line)[2] for line in lines)
    box_w = max_w + pad_x * 2
    box_h = pad_y * 2 + line_h * len(lines)
    tx = min(max(8, x + 14), width - box_w - 8)
    ty = min(max(8, y - box_h - 10), height - box_h - 8)
    cr.set_source_rgba(0.04, 0.05, 0.07, boost_alpha(0.92))
    cr.rectangle(tx, ty, box_w, box_h)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.95))
    for i, line in enumerate(lines):
        cr.move_to(tx + pad_x, ty + pad_y + (i + 1) * line_h - 3)
        cr.show_text(line)
