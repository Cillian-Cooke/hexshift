from hexshift.constants import (
    ABILITY_COLORS,
    ABILITY_LABELS,
    BANNER_H,
    COLOR_SOLID,
    HIDE_HINT,
    HUD_MARGIN,
    HUD_TAB_H,
    HUD_TAB_W,
    HUD_WIDTH,
    HUMAN,
    PLAYER_NAMES,
    PLAYERS,
    RULES_TEXT,
    SCORE_EXTRA_H,
    SCORE_HINT_H,
    SCORE_ROW,
    STACK_DX,
    STACK_DY,
    STACK_MAX_PEEK,
    TIMED_ABILITIES,
    boost_alpha,
)
from hexshift.game import Game


def _fmt(seconds):
    seconds = max(0, int(seconds + 0.5))
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _player_rgb():
    r, g, b, _ = COLOR_SOLID[HUMAN]
    return (r, g, b)


def _ability_rgb(kind):
    return ABILITY_COLORS.get(kind, _player_rgb())


class Banner:
    __slots__ = (
        "kind",
        "title",
        "subtitle",
        "cancellable",
        "payload",
        "x",
        "y",
        "w",
        "h",
        "close",
        "color",
        "progress",
        "z",
    )

    def __init__(
        self,
        kind,
        title,
        subtitle,
        cancellable=False,
        payload=None,
        color=None,
        progress=None,
        z=0,
    ):
        self.kind = kind
        self.title = title
        self.subtitle = subtitle
        self.cancellable = cancellable
        self.payload = payload
        self.x = self.y = 0
        self.w = HUD_WIDTH
        self.h = BANNER_H
        self.close = None
        self.color = color or _player_rgb()
        self.progress = progress
        self.z = z


def _mega_subtitle(mega):
    if mega.kind == "shockwave":
        return f"Next pulse {_fmt(mega.remaining)} · ring {mega.shock_radius}"
    if mega.kind == "shield":
        return f"Next in {_fmt(mega.remaining)}"
    return "Active"


def _job_progress(job):
    if not job.duration:
        return 1.0
    return max(0.0, min(1.0, 1.0 - job.remaining / job.duration))


def build_banners(game: Game):
    front = []
    queues = []
    rest = []
    rgb = _player_rgb()

    if game.finished:
        if len(game.winners) == 1:
            name = PLAYER_NAMES[game.winners[0]]
            title = f"{name} wins"
        else:
            names = ", ".join(PLAYER_NAMES[p] for p in game.winners)
            title = f"Draw — {names}"
        rest.append(
            Banner("win", title, "All land captured", False, None, (0.92, 0.78, 0.28), None, 50)
        )

    for j in game.active[HUMAN]:
        if j.mega_id is not None:
            mega = game.megas.get(j.mega_id)
            label = ABILITY_LABELS.get(mega.kind, "megatile") if mega else "megatile"
            title = f"Stealing {label}"
            color = _ability_rgb(mega.kind) if mega else rgb
        else:
            title = "Capturing tile"
            color = rgb
        front.append(
            Banner(
                "capture",
                title,
                _fmt(j.remaining),
                True,
                ("cancel_job", j),
                color,
                _job_progress(j),
                20,
            )
        )
    for i, j in enumerate(game.queues[HUMAN]):
        if j.mega_id is not None:
            mega = game.megas.get(j.mega_id)
            title = f"Queued steal {i + 1}"
            color = _ability_rgb(mega.kind) if mega else (0.5, 0.55, 0.6)
        else:
            title = f"Queued hex {i + 1}"
            color = (0.5, 0.55, 0.6)
        queues.append(
            Banner("queue", title, "waiting", True, ("cancel_job", j), color, None, 5 - i * 0.01)
        )
    for merge in game.merges:
        if merge.owner != HUMAN:
            continue
        frac = 1.0 - merge.remaining / merge.duration if merge.duration else 1.0
        rest.append(
            Banner(
                "merge",
                f"Building {ABILITY_LABELS.get(merge.kind, merge.kind)}",
                _fmt(merge.remaining),
                True,
                ("cancel_merge", merge),
                _ability_rgb(merge.kind),
                frac,
                18,
            )
        )
    for deco in game.deconstructs:
        if deco.owner != HUMAN:
            continue
        mega = game.megas.get(deco.mega_id)
        label = ABILITY_LABELS.get(mega.kind, "megatile") if mega else "megatile"
        frac = 1.0 - deco.remaining / deco.duration if deco.duration else 1.0
        rest.append(
            Banner(
                "deconstruct",
                f"Deconstructing {label}",
                _fmt(deco.remaining),
                True,
                ("cancel_deconstruct", deco),
                (0.95, 0.55, 0.35),
                frac,
                18,
            )
        )
    for mega in sorted(game.megas.values(), key=lambda m: (m.kind, m.id)):
        if mega.owner != HUMAN:
            continue
        if any(d.mega_id == mega.id for d in game.deconstructs):
            continue
        timed = mega.kind in TIMED_ABILITIES
        interval = game.ability_interval(mega.kind) if timed else 0.0
        progress = None
        if timed and interval:
            progress = max(0.0, min(1.0, 1.0 - mega.remaining / interval))
        rest.append(
            Banner(
                "mega",
                ABILITY_LABELS.get(mega.kind, mega.kind),
                _mega_subtitle(mega),
                False,
                ("deconstruct_mega", mega),
                _ability_rgb(mega.kind),
                progress,
                10,
            )
        )
    return front, queues, rest


def layout_hud(game: Game, width, height, collapsed=False):
    chrome = {"info": None, "collapse": None, "tab": None}
    if collapsed:
        tab = (
            int(width - HUD_MARGIN - HUD_TAB_W),
            int(height - HUD_MARGIN - HUD_TAB_H),
            HUD_TAB_W,
            HUD_TAB_H,
        )
        chrome["tab"] = tab
        return [], (0, 0, 0, 0), chrome

    front, queues, rest = build_banners(game)
    score_h = 16 + SCORE_ROW * len(PLAYERS) + SCORE_HINT_H + SCORE_EXTRA_H
    if game.finished:
        score_h += 18
    x = width - HUD_MARGIN - HUD_WIDTH
    y = height - HUD_MARGIN - score_h
    score = (x, y, HUD_WIDTH, score_h)
    chrome["info"] = (x + HUD_WIDTH - 44, y + 6, 16, 16)
    chrome["collapse"] = (x + HUD_WIDTH - 24, y + 6, 16, 16)

    laid = []
    by = y
    host = None
    for b in front:
        by -= BANNER_H + 6
        if by < HUD_MARGIN:
            break
        b.x, b.y = x, by
        if b.cancellable:
            b.close = (x + HUD_WIDTH - 22, by + 9, 16, 16)
        laid.append(b)
        if host is None:
            host = b

    extra = 0
    peek = queues
    if len(queues) > STACK_MAX_PEEK:
        peek = queues[:STACK_MAX_PEEK]
        extra = len(queues) - STACK_MAX_PEEK
    if host is None and peek:
        by -= BANNER_H + 6
        if by >= HUD_MARGIN:
            host = peek[0]
            host.x, host.y = x, by
            host.close = (x + HUD_WIDTH - 22, by + 9, 16, 16)
            laid.append(host)
            peek = peek[1:]
    if host and extra:
        host.subtitle = f"{host.subtitle}  +{extra} queued"
    if host:
        for i, q in enumerate(peek):
            depth = i + 1
            q.x = host.x - STACK_DX * depth
            q.y = host.y - STACK_DY * depth
            q.z = host.z - depth
            q.close = (q.x + 2, q.y + 9, 12, 12)
            laid.append(q)

    for b in rest:
        by -= BANNER_H + 6
        if by < HUD_MARGIN:
            break
        b.x, b.y = x, by
        if b.cancellable:
            b.close = (x + HUD_WIDTH - 22, by + 9, 16, 16)
        laid.append(b)
    laid.sort(key=lambda b: b.z)
    return laid, score, chrome


def hit_hud(banners, score, chrome, x, y):
    tab = chrome.get("tab")
    if tab:
        tx, ty, tw, th = tab
        if tx <= x <= tx + tw and ty <= y <= ty + th:
            return ("tab", None)
        return None
    for key in ("info", "collapse"):
        rect = chrome.get(key)
        if not rect:
            continue
        cx, cy, cw, ch = rect
        if cx <= x <= cx + cw and cy <= y <= cy + ch:
            return (key, None)
    # Front-most banners first (higher z)
    for b in sorted(banners, key=lambda b: -b.z):
        if b.close:
            cx, cy, cw, ch = b.close
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                return b.payload
        if b.x <= x <= b.x + b.w and b.y <= y <= b.y + b.h:
            if b.payload and b.kind == "mega":
                return b.payload
            return ("hud", None)
    sx, sy, sw, sh = score
    if sw and sh and sx <= x <= sx + sw and sy <= y <= sy + sh:
        return ("hud", None)
    return None


def apply_hud_action(game: Game, payload):
    if not payload or game.finished:
        return
    kind, obj = payload
    if kind == "cancel_job":
        game.cancel_target(HUMAN, (obj.q, obj.r), obj.mega_id)
    elif kind == "cancel_merge":
        game.cancel_merge(obj)
    elif kind == "cancel_deconstruct":
        game.cancel_deconstruct(obj)
    elif kind == "deconstruct_mega":
        existing = game.deconstruct_for(obj.id)
        if existing:
            game.cancel_deconstruct(existing)
        else:
            game.start_deconstruct(obj.id)


def show_help_dialog(parent):
    from gi.repository import Gtk
    dialog = Gtk.Dialog(title="How to play", transient_for=parent, flags=0)
    dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    dialog.set_default_size(420, 480)
    dialog.set_modal(True)
    label = Gtk.Label(label=RULES_TEXT, xalign=0, yalign=0)
    label.set_line_wrap(True)
    label.set_selectable(True)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.add(label)
    box = dialog.get_content_area()
    box.set_margin_top(10)
    box.set_margin_bottom(10)
    box.set_margin_start(12)
    box.set_margin_end(12)
    box.pack_start(scroll, True, True, 0)
    dialog.show_all()
    dialog.run()
    dialog.destroy()


def draw_hud(cr, game: Game, banners, score, chrome):
    tab = chrome.get("tab")
    if tab:
        tx, ty, tw, th = tab
        cr.set_source_rgba(0.07, 0.08, 0.1, boost_alpha(0.82))
        _round_rect(cr, tx, ty, tw, th, 7)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, boost_alpha(0.9))
        cr.select_font_face("Sans")
        cr.set_font_size(12)
        cr.move_to(tx + 10, ty + 19)
        cr.show_text("HUD")
        return

    sx, sy, sw, sh = score
    cr.set_source_rgba(0.06, 0.07, 0.08, boost_alpha(0.72))
    _round_rect(cr, sx, sy, sw, sh, 8)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.88))
    cr.select_font_face("Sans")
    cr.set_font_size(11)
    cr.move_to(sx + 10, sy + 14)
    cr.show_text("Score")
    _draw_info_button(cr, chrome["info"])
    _draw_collapse(cr, chrome["collapse"])
    for i, pid in enumerate(PLAYERS):
        yy = sy + 18 + i * SCORE_ROW
        r, g, b, _ = COLOR_SOLID[pid]
        cr.set_source_rgba(r, g, b, 1)
        cr.rectangle(sx + 10, yy + 4, 10, 10)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, boost_alpha(0.9))
        cr.set_font_size(11)
        cr.move_to(sx + 26, yy + 13)
        cr.show_text(f"{PLAYER_NAMES[pid]}  {game.tile_count(pid)} tiles")
    meta_y = sy + 18 + len(PLAYERS) * SCORE_ROW + 6
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.8))
    cr.set_font_size(11)
    cr.move_to(sx + 10, meta_y + 12)
    cr.show_text(f"Tiles left  {game.tiles_left()}")
    cap_used = len(game.active[HUMAN])
    cap_max = game.capture_slots(HUMAN)
    build_used = sum(1 for m in game.merges if m.owner == HUMAN)
    build_max = game.merge_slots(HUMAN)
    cr.move_to(sx + 10, meta_y + 28)
    cr.show_text(f"Capture {cap_used}/{cap_max}   Build {build_used}/{build_max}")
    if game.finished:
        cr.set_source_rgba(0.95, 0.85, 0.4, boost_alpha(0.95))
        if len(game.winners) == 1:
            msg = f"{PLAYER_NAMES[game.winners[0]]} wins"
        else:
            msg = "Draw"
        cr.move_to(sx + 10, meta_y + 44)
        cr.show_text(msg)
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.45))
    cr.set_font_size(10)
    cr.move_to(sx + 10, sy + sh - 6)
    cr.show_text(HIDE_HINT)

    for b in banners:
        _draw_banner(cr, b)


def _draw_banner(cr, b):
    r, g, bl = b.color
    dark = (0.08, 0.09, 0.11)
    if b.progress is None:
        cr.set_source_rgba(r, g, bl, boost_alpha(0.78))
        _round_rect(cr, b.x, b.y, b.w, b.h, 7)
        cr.fill()
    else:
        cr.set_source_rgba(*dark, boost_alpha(0.82))
        _round_rect(cr, b.x, b.y, b.w, b.h, 7)
        cr.fill()
        fill_w = max(0.0, min(b.w, b.w * b.progress))
        if fill_w > 1:
            cr.save()
            _round_rect(cr, b.x, b.y, b.w, b.h, 7)
            cr.clip()
            cr.set_source_rgba(r, g, bl, boost_alpha(0.88))
            cr.rectangle(b.x, b.y, fill_w, b.h)
            cr.fill()
            cr.restore()
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.92))
    cr.select_font_face("Sans")
    cr.set_font_size(11)
    cr.move_to(b.x + 10, b.y + 15)
    cr.show_text(b.title[:28])
    cr.set_source_rgba(0.92, 0.95, 0.96, boost_alpha(0.85))
    cr.set_font_size(10)
    cr.move_to(b.x + 10, b.y + 28)
    cr.show_text(b.subtitle[:42])
    if b.cancellable and b.close:
        cx, cy, cw, ch = b.close
        cr.set_source_rgba(1, 1, 1, boost_alpha(0.7))
        cr.set_line_width(1.4)
        cr.move_to(cx + 3, cy + 3)
        cr.line_to(cx + cw - 3, cy + ch - 3)
        cr.move_to(cx + cw - 3, cy + 3)
        cr.line_to(cx + 3, cy + ch - 3)
        cr.stroke()


def _draw_info_button(cr, rect):
    if not rect:
        return
    x, y, w, h = rect
    cx, cy, rad = x + w / 2, y + h / 2, 7
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.22))
    cr.arc(cx, cy, rad, 0, 6.283)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.9))
    cr.select_font_face("Sans")
    cr.set_font_size(11)
    cr.move_to(cx - 2.5, cy + 4)
    cr.show_text("i")


def _draw_collapse(cr, rect):
    if not rect:
        return
    x, y, w, h = rect
    cr.set_source_rgba(1, 1, 1, boost_alpha(0.75))
    cr.set_line_width(1.4)
    cr.move_to(x + 4, y + 6)
    cr.line_to(x + w / 2, y + h - 5)
    cr.line_to(x + w - 4, y + 6)
    cr.stroke()


def _round_rect(cr, x, y, w, h, r):
    cr.new_path()
    cr.arc(x + w - r, y + r, r, -1.57, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.57)
    cr.arc(x + r, y + h - r, r, 1.57, 3.14)
    cr.arc(x + r, y + r, r, 3.14, 4.71)
    cr.close_path()


def hud_boxes(banners, score, chrome):
    boxes = []
    tab = chrome.get("tab")
    if tab:
        boxes.append(tab)
        return boxes
    sx, sy, sw, sh = score
    if sw and sh:
        boxes.append(score)
    for b in banners:
        boxes.append((int(b.x), int(b.y), int(b.w), int(b.h)))
    return boxes
