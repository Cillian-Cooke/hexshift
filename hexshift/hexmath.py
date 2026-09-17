import math

from hexshift.constants import DIRS, LAYOUT_SIZE, SQRT3


def hex_distance(a, b):
    aq, ar = a
    bq, br = b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


def neighbors(q, r):
    for dq, dr in DIRS:
        yield q + dq, r + dr


def cluster(q, r):
    return [(q, r)] + list(neighbors(q, r))


def hex_ring(q, r, radius):
    if radius == 0:
        return [(q, r)]
    results = []
    cq = q + DIRS[4][0] * radius
    cr = r + DIRS[4][1] * radius
    for i in range(6):
        dq, dr = DIRS[i]
        for _ in range(radius):
            results.append((cq, cr))
            cq += dq
            cr += dr
    return results


def hex_disk(q, r, radius):
    cells = [(q, r)]
    for rad in range(1, radius + 1):
        cells.extend(hex_ring(q, r, rad))
    return cells


def cube_round(x, y, z):
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, rz


def axial_to_pixel(q, r, ox, oy, size=LAYOUT_SIZE):
    x = size * (SQRT3 * q + SQRT3 / 2.0 * r)
    y = size * (1.5 * r)
    return ox + x, oy + y


def pixel_to_axial(x, y, ox, oy, size=LAYOUT_SIZE):
    px = (x - ox) / size
    py = (y - oy) / size
    q = (SQRT3 / 3.0) * px - (1.0 / 3.0) * py
    r = (2.0 / 3.0) * py
    cq, cr = cube_round(q, -q - r, r)
    return int(cq), int(cr)


_HEX_UNIT = tuple(
    (math.cos(math.radians(30 + 60 * i)), math.sin(math.radians(30 + 60 * i)))
    for i in range(6)
)


def hex_corners(cx, cy, size):
    return [(cx + size * ux, cy + size * uy) for ux, uy in _HEX_UNIT]


def hex_bbox(cx, cy, size):
    hw = size * SQRT3 / 2.0
    return int(cx - hw - 1), int(cy - size - 1), int(2 * hw + 2), int(2 * size + 2)


def keys_for_screen(width, height, size=LAYOUT_SIZE, pad=48):
    keys = []
    rmin = int(-(height / 2 + pad) / (1.5 * size)) - 2
    rmax = int((height / 2 + pad) / (1.5 * size)) + 2
    qmin = int(-(width / 2 + pad) / (SQRT3 * size)) - 2
    qmax = int((width / 2 + pad) / (SQRT3 * size)) + 2
    ox, oy = width / 2.0, height / 2.0
    for r in range(rmin, rmax + 1):
        for q in range(qmin, qmax + 1):
            x, y = axial_to_pixel(q, r, ox, oy, size)
            if -pad <= x <= width + pad and -pad <= y <= height + pad:
                keys.append((q, r))
    return keys

def point_in_hex(px, py, cx, cy, size):
    corners = hex_corners(cx, cy, size)
    inside = False
    j = len(corners) - 1
    for i in range(len(corners)):
        xi, yi = corners[i]
        xj, yj = corners[j]
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside

