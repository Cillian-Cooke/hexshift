import math

OPACITY_BOOST = 0.20


def boost_alpha(a):
    return min(1.0, a + OPACITY_BOOST)


HUMAN = 0
PLAYERS = (0, 1, 2, 3)
PLAYER_NAMES = ("You", "Coral", "Amber", "Violet")

# RGBA 0-1
COLORS = {
    0: (0.24, 0.81, 0.70, 0.70),
    1: (0.91, 0.36, 0.30, 0.70),
    2: (0.90, 0.72, 0.30, 0.70),
    3: (0.61, 0.49, 0.92, 0.70),
}
COLOR_SOLID = {
    0: (0.24, 0.81, 0.70, 1.0),
    1: (0.91, 0.36, 0.30, 1.0),
    2: (0.90, 0.72, 0.30, 1.0),
    3: (0.61, 0.49, 0.92, 1.0),
}
UNOWNED = (0.16, 0.16, 0.18, 0.62)
UNOWNED_STROKE = (0.08, 0.08, 0.09, 0.75)

LAYOUT_SIZE = 14.0
DRAW_SIZE = 12.0
SQRT3 = math.sqrt(3.0)
MEGA_CENTER_SIZE = SQRT3 * (LAYOUT_SIZE - DRAW_SIZE / 2)  # small-mega centre
MEGA_INNER_SIZE = 2.0 * LAYOUT_SIZE - DRAW_SIZE  # inner 7 grow to touch outer ring
MEGA_ICON_SIZE = 16.0

DIRS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

# Offset from cluster center -> ability (inner 7 + outer 12)
INNER_KINDS = ("eye", "hourglass", "shield", "blade", "shockwave", "forge", "factory")
OUTER_KINDS = (
    "beacon",
    "spring",
    "bastion",
    "spike",
    "ripple",
    "anvil",
    "workshop",
    "census",
    "grove",
    "lantern",
    "keep",
    "monument",
)
ABILITY_OFFSETS = {
    (0, 0): "eye",
    (1, 0): "hourglass",
    (1, -1): "shield",
    (0, -1): "blade",
    (-1, 0): "shockwave",
    (-1, 1): "forge",
    (0, 1): "factory",
    # ring 2, clockwise from hex_ring(0,0,2)
    (-2, 2): "beacon",
    (-1, 2): "spring",
    (0, 2): "bastion",
    (1, 1): "spike",
    (2, 0): "ripple",
    (2, -1): "anvil",
    (2, -2): "workshop",
    (1, -2): "census",
    (0, -2): "grove",
    (-1, -1): "lantern",
    (-2, 0): "keep",
    (-2, 1): "monument",
}
LARGE_KINDS = set(OUTER_KINDS)
ABILITY_LABELS = {
    "eye": "Eye",
    "hourglass": "Hourglass",
    "shield": "Shield",
    "blade": "Blade",
    "shockwave": "Shockwave",
    "forge": "Forge",
    "factory": "Factory",
    "beacon": "Beacon",
    "spring": "Spring",
    "bastion": "Bastion",
    "spike": "Spike",
    "ripple": "Ripple",
    "anvil": "Anvil",
    "workshop": "Workshop",
    "census": "Census",
    "grove": "Grove",
    "lantern": "Lantern",
    "keep": "Keep",
    "monument": "Monument",
}
ABILITY_DESCRIPTIONS = {
    "eye": "Eye: +3 vision range. Stacks with other Eyes.",
    "hourglass": "Hourglass: capture empty tiles 20% faster. Stacks.",
    "shield": "Shield: shields a random owned tile every 4 minutes.",
    "blade": "Blade: capture enemy tiles 40% faster. Stacks.",
    "shockwave": "Shockwave: pulses every 15 min, one ring further each time.",
    "forge": "Forge: +1 simultaneous capture slot. Stacks with no cap.",
    "factory": "Factory: +1 simultaneous megatile-build slot. Stacks with no cap.",
    "beacon": "Beacon (prototype, large): extra vision outpost. Occupies the full 19-cell megatile.",
    "spring": "Spring (prototype, large): occupies the full 19-cell megatile.",
    "bastion": "Bastion (prototype, large): occupies the full 19-cell megatile.",
    "spike": "Spike (prototype, large): occupies the full 19-cell megatile.",
    "ripple": "Ripple (prototype, large): occupies the full 19-cell megatile.",
    "anvil": "Anvil (prototype, large): occupies the full 19-cell megatile.",
    "workshop": "Workshop (prototype, large): occupies the full 19-cell megatile.",
    "census": "Census (prototype, large): occupies the full 19-cell megatile.",
    "grove": "Grove (prototype, large): occupies the full 19-cell megatile.",
    "lantern": "Lantern (prototype, large): occupies the full 19-cell megatile.",
    "keep": "Keep (prototype, large): occupies the full 19-cell megatile.",
    "monument": "Monument (prototype, large): occupies the full 19-cell megatile.",
}
ABILITY_COLORS = {
    "eye": (0.35, 0.85, 0.95),
    "hourglass": (0.95, 0.78, 0.35),
    "shield": (0.55, 0.72, 0.98),
    "blade": (0.95, 0.45, 0.45),
    "shockwave": (0.75, 0.55, 0.98),
    "forge": (0.85, 0.62, 0.35),
    "factory": (0.45, 0.82, 0.55),
    "beacon": (0.98, 0.92, 0.55),
    "spring": (0.45, 0.92, 0.78),
    "bastion": (0.62, 0.58, 0.52),
    "spike": (0.95, 0.35, 0.62),
    "ripple": (0.45, 0.62, 0.98),
    "anvil": (0.72, 0.72, 0.78),
    "workshop": (0.82, 0.52, 0.28),
    "census": (0.55, 0.88, 0.42),
    "grove": (0.32, 0.72, 0.38),
    "lantern": (1.0, 0.82, 0.42),
    "keep": (0.48, 0.42, 0.58),
    "monument": (0.88, 0.72, 0.62),
}
TIMED_ABILITIES = ("shield", "shockwave")
RULES_TEXT = """Hexshift

Capture
Click a hex next to land you already own (or next to your queue path). Empty land takes 5 minutes; enemy land and enemy megatiles take 10 minutes. Only as many captures can run as you have capture slots (1, plus 1 per Forge).

Queue
Click further hexes to premove. They wait behind the current capture. A second click on a hex, or the X on its banner, cancels it and anything that depended on that link.

Supply
Everything you own must stay connected to your home (the land you spawned on). If another player captures the link and severs a branch, that whole branch returns to empty land — shields and megatiles included. If your home is taken, your largest remaining connected blob becomes the new home.

Megatiles
Double-click a finished hex whose six neighbours you also own. The inner seven hexes are the original abilities (small megatile). If you also own the outer ring, twelve prototype options appear around it — picking one builds a large 19-cell megatile. All megatile builds take 15 minutes. Inner hexes grow to touch the outer ring while you choose.

Abilities
Eye — +3 vision, stacks.
Hourglass — empty captures 20% faster, stacks.
Shield — every 4 minutes, a random owned small tile becomes uncapturable. Shielded tiles can still merge into megatiles. A cut-off branch still collapses, shields and all.
Blade — enemy captures 40% faster, stacks.
Shockwave — every 15 minutes, instantly takes the next ring of unshielded land. Steals enemy megatiles it touches.
Forge — +1 capture slot, no cap.
Factory — +1 megatile-build slot, no cap.

Win
The game ends when every land tile is owned. Most tiles wins (a small megatile counts as 7, a large one as its full footprint). A tie is a draw.

Shortcuts
Ctrl+Alt+H hides the whole overlay. The chevron on the scoreboard hides only the HUD. The i button opens this help.
"""

BASE_VISION = 3
EYE_BONUS = 3
EMPTY_CAPTURE = 5 * 60
ENEMY_CAPTURE = 10 * 60
MERGE_TIME = 15 * 60
DECONSTRUCT_TIME = 10 * 60
SHIELD_INTERVAL = 4 * 60
SHOCKWAVE_INTERVAL = 15 * 60
MIN_CAPTURE = 60
HOURGLASS_FACTOR = 0.8
BLADE_FACTOR = 0.6

TICK_MS = 500
AI_PERIOD = 4.0
SAVE_PERIOD = 45.0
ANIM_PERIOD = 1.0

HUD_WIDTH = 248
HUD_MARGIN = 14
BANNER_H = 34
SCORE_ROW = 22
SCORE_HINT_H = 16
SCORE_EXTRA_H = 44
HIDE_ACCEL = "<Ctrl><Alt>h"
HIDE_HINT = "Ctrl+Alt+H hide overlay"
STACK_DX = 10
STACK_DY = 6
STACK_MAX_PEEK = 3
HUD_TAB_W = 44
HUD_TAB_H = 28

# Map generation: higher threshold + scatter = more gaps
LAND_THRESHOLD = 0.50
GAP_SCATTER_CHANCE = 0.10
GAP_CLUSTER_CHANCE = 0.30
