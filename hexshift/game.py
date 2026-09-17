import math
import random
from collections import deque
from dataclasses import dataclass, field

from hexshift.constants import (
    ABILITY_DESCRIPTIONS,
    ABILITY_OFFSETS,
    BASE_VISION,
    BLADE_FACTOR,
    DECONSTRUCT_TIME,
    DIRS,
    EMPTY_CAPTURE,
    ENEMY_CAPTURE,
    EYE_BONUS,
    GAP_CLUSTER_CHANCE,
    GAP_SCATTER_CHANCE,
    HOURGLASS_FACTOR,
    HUMAN,
    LAND_THRESHOLD,
    LARGE_KINDS,
    LAYOUT_SIZE,
    MERGE_TIME,
    MIN_CAPTURE,
    PLAYERS,
    SHIELD_INTERVAL,
    SHOCKWAVE_INTERVAL,
    TIMED_ABILITIES,
)
from hexshift.hexmath import (
    axial_to_pixel,
    cluster,
    hex_distance,
    hex_ring,
    keys_for_screen,
    neighbors,
    pixel_to_axial,
)


class ValueNoise:
    def __init__(self, seed):
        rng = random.Random(seed)
        self.p = [rng.random() * 2.0 - 1.0 for _ in range(256)]

    def _h(self, ix, iy):
        return self.p[(ix * 1619 + iy * 31337) & 255]

    def noise(self, x, y):
        x0 = math.floor(x)
        y0 = math.floor(y)
        fx, fy = x - x0, y - y0
        u = fx * fx * (3.0 - 2.0 * fx)
        v = fy * fy * (3.0 - 2.0 * fy)
        n00 = self._h(x0, y0)
        n10 = self._h(x0 + 1, y0)
        n01 = self._h(x0, y0 + 1)
        n11 = self._h(x0 + 1, y0 + 1)
        nx0 = n00 + (n10 - n00) * u
        nx1 = n01 + (n11 - n01) * u
        return nx0 + (nx1 - nx0) * v

    def fbm(self, x, y):
        total = 0.0
        norm = 0.0
        amp = 1.0
        freq = 1.0
        for _ in range(4):
            total += amp * self.noise(x * freq, y * freq)
            norm += amp
            amp *= 0.5
            freq *= 2.0
        return total / norm


@dataclass
class Tile:
    q: int
    r: int
    land: bool = False
    owner: int | None = None
    shielded: bool = False
    mega_id: int | None = None


@dataclass
class Job:
    q: int
    r: int
    owner: int
    mega_id: int | None = None
    remaining: float = 0.0
    duration: float = 1.0


@dataclass
class Mega:
    id: int
    center: tuple
    cells: tuple
    owner: int
    kind: str
    remaining: float = 0.0
    shock_radius: int = 2


@dataclass
class Merge:
    owner: int
    center: tuple
    cells: list
    kind: str
    remaining: float = 0.0
    duration: float = 1.0


@dataclass
class Deconstruct:
    mega_id: int
    owner: int
    center: tuple
    cells: list
    remaining: float = 0.0
    duration: float = 1.0


@dataclass
class Choice:
    center: tuple
    cells: list


@dataclass
class Game:
    seed: int = 0
    fast: bool = False
    width: int = 1920
    height: int = 1080
    tiles: dict = field(default_factory=dict)
    megas: dict = field(default_factory=dict)
    next_mega_id: int = 1
    queues: list = field(default_factory=list)
    active: list = field(default_factory=list)
    merges: list = field(default_factory=list)
    deconstructs: list = field(default_factory=list)
    choice: Choice | None = None
    factory_points: list = field(default_factory=lambda: [0, 0, 0, 0])
    paused: bool = False
    finished: bool = False
    winners: list = field(default_factory=list)
    spawns: list = field(default_factory=list)
    dirty: bool = True
    need_save: bool = False
    world_rev: int = 0
    _vis: set | None = field(default=None, repr=False)
    _px: dict = field(default_factory=dict, repr=False)
    _owned: list = field(default_factory=list, repr=False)
    _unowned_land: int = 0
    _legal: bool | None = field(default=None, repr=False)

    def __post_init__(self):
        if not self.queues:
            self.queues = [[] for _ in PLAYERS]
        if not self.active:
            self.active = [[] for _ in PLAYERS]
        if not self._owned:
            self._owned = [set() for _ in PLAYERS]
        if not self.spawns:
            self.spawns = [None for _ in PLAYERS]
        self._times()

    def _bump_world(self, save=False):
        self._vis = None
        self._legal = None
        self.world_rev += 1
        self.dirty = True
        if save:
            self.need_save = True

    def _rebuild_indexes(self):
        self._owned = [set() for _ in PLAYERS]
        self._unowned_land = 0
        for key, t in self.tiles.items():
            if not t.land:
                continue
            if t.owner is None:
                self._unowned_land += 1
            else:
                self._owned[t.owner].add(key)

    def _set_owner(self, tile, owner):
        old = tile.owner
        if old == owner:
            return
        key = (tile.q, tile.r)
        if tile.land:
            if old is None:
                self._unowned_land -= 1
            else:
                self._owned[old].discard(key)
            if owner is None:
                self._unowned_land += 1
            else:
                self._owned[owner].add(key)
        tile.owner = owner

    def _flood_owned(self, pid, start):
        owned = self._owned[pid]
        if start not in owned:
            return set()
        seen = {start}
        dq = deque([start])
        while dq:
            cur = dq.popleft()
            for n in neighbors(*cur):
                if n in owned and n not in seen:
                    seen.add(n)
                    dq.append(n)
        return seen

    def _owned_components(self, pid):
        leftover = set(self._owned[pid])
        comps = []
        while leftover:
            start = next(iter(leftover))
            comp = self._flood_owned(pid, start)
            leftover -= comp
            comps.append(comp)
        return comps

    def _infer_spawn(self, pid):
        comps = self._owned_components(pid)
        if not comps:
            return None
        main = max(comps, key=lambda c: (len(c), -min(c)[0], -min(c)[1]))
        return min(main)

    def _destroy_cells(self, cells):
        megas = set()
        for key in cells:
            t = self.tiles.get(key)
            if t and t.mega_id is not None:
                megas.add(t.mega_id)
        for mid in megas:
            m = self.megas.pop(mid, None)
            if not m:
                continue
            for c in m.cells:
                t = self.tiles.get(c)
                if t:
                    t.mega_id = None
                    t.shielded = False
                    self._set_owner(t, None)
            gone = set(m.cells)
            self.merges = [mg for mg in self.merges if gone.isdisjoint(mg.cells)]
            if self.choice and gone.intersection(self.choice.cells):
                self.choice = None
        for key in cells:
            t = self.tiles.get(key)
            if not t or t.owner is None:
                continue
            t.shielded = False
            t.mega_id = None
            self._set_owner(t, None)

    def _cut_off_branches(self, pid):
        owned = self._owned[pid]
        if not owned:
            self.spawns[pid] = None
            return False
        home = self.spawns[pid] if pid < len(self.spawns) else None
        if home in owned:
            main = self._flood_owned(pid, home)
        else:
            comps = self._owned_components(pid)
            main = max(comps, key=lambda c: (len(c), -min(c)[0], -min(c)[1]))
            self.spawns[pid] = (
                min(main, key=lambda k: hex_distance(k, home)) if home else min(main)
            )
        to_kill = owned - main
        if not to_kill:
            return False
        self._destroy_cells(to_kill)
        return True

    def prune_disconnected(self):
        self._maybe_rebuild_indexes()
        killed = False
        for pid in PLAYERS:
            if self._cut_off_branches(pid):
                killed = True
        if killed:
            self.deconstructs = [
                d for d in self.deconstructs if d.mega_id in self.megas
            ]
            self._bump_world(save=True)
        return killed

    def _apply_spawns(self, raw):
        out = list(self.spawns) if self.spawns else [None for _ in PLAYERS]
        if len(out) < len(PLAYERS):
            out.extend([None] * (len(PLAYERS) - len(out)))
        if raw:
            for i, item in enumerate(raw):
                if i >= len(PLAYERS):
                    break
                if item:
                    out[i] = (int(item[0]), int(item[1]))
                else:
                    out[i] = None
        for pid in PLAYERS:
            if out[pid] not in self._owned[pid]:
                out[pid] = self._infer_spawn(pid)
        self.spawns = out

    def _times(self):
        scale = 1.0 / 60.0 if self.fast else 1.0
        self.t_empty = EMPTY_CAPTURE * scale
        self.t_enemy = ENEMY_CAPTURE * scale
        self.t_merge = MERGE_TIME * scale
        self.t_shield = SHIELD_INTERVAL * scale
        self.t_shock = SHOCKWAVE_INTERVAL * scale
        self.t_deconstruct = DECONSTRUCT_TIME * scale
        self.t_min = (1.0 if self.fast else MIN_CAPTURE)

    @property
    def ox(self):
        return self.width / 2.0

    @property
    def oy(self):
        return self.height / 2.0

    def pixel(self, q, r):
        cached = self._px.get((q, r))
        if cached is None:
            cached = axial_to_pixel(q, r, self.ox, self.oy, LAYOUT_SIZE)
            self._px[(q, r)] = cached
        return cached

    def mega_cell_size(self, mega, cell):
        from hexshift.constants import DRAW_SIZE, MEGA_CENTER_SIZE, MEGA_INNER_SIZE

        large = mega.kind in LARGE_KINDS or len(mega.cells) > 7
        dist = hex_distance(cell, mega.center)
        if large and dist <= 1:
            return MEGA_INNER_SIZE
        if not large and cell == mega.center:
            return MEGA_CENTER_SIZE
        return DRAW_SIZE


    def mega_at(self, x, y):
        from hexshift.constants import HUMAN
        from hexshift.hexmath import point_in_hex

        vis = self.visible_set(HUMAN)
        seen = set()
        best = None
        best_key = None
        for tile in self.tiles.values():
            if not tile.land or tile.mega_id is None:
                continue
            if tile.mega_id in seen:
                continue
            seen.add(tile.mega_id)
            mega = self.megas.get(tile.mega_id)
            if not mega:
                continue
            for c in mega.cells:
                if c not in vis:
                    continue
                cx, cy = self.pixel(*c)
                size = self.mega_cell_size(mega, c)
                if point_in_hex(x, y, cx, cy, size):
                    if best is None or mega.id >= best.id:
                        best = mega
                        best_key = c
        if best is not None:
            return best, best_key
        return None, None

    def hex_at(self, x, y):
        return pixel_to_axial(x, y, self.ox, self.oy, LAYOUT_SIZE)

    def set_size(self, width, height):
        if width <= 0 or height <= 0:
            return
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        self._px.clear()
        self._ensure_keys()
        self._bump_world()

    def _ensure_keys(self):
        noise = ValueNoise(self.seed)
        added = False
        existing_land = {k for k, t in self.tiles.items() if t.land}
        candidates = set()
        for key in keys_for_screen(self.width, self.height):
            if key in self.tiles:
                continue
            q, r = key
            n = 0.6 * noise.fbm(q * 0.12, r * 0.12) + 0.4 * noise.fbm(q * 0.045 + 9, r * 0.045)
            want_land = ((n + 1.0) * 0.5) > LAND_THRESHOLD
            self.tiles[key] = Tile(q, r, land=False)
            if want_land:
                candidates.add(key)
            added = True
        if candidates:
            if existing_land:
                attach = set()
                seen = set(existing_land)
                dq = deque(existing_land)
                while dq:
                    cur = dq.popleft()
                    for nkey in neighbors(*cur):
                        if nkey in seen:
                            continue
                        if nkey in candidates:
                            seen.add(nkey)
                            attach.add(nkey)
                            dq.append(nkey)
                candidates = attach
            else:
                candidates = self._largest_component(candidates)
            for key in candidates:
                self.tiles[key].land = True
                self._unowned_land += 1
        if added:
            self._legal = None


    def _smooth_noise(self, raw, passes=3):
        for _ in range(passes):
            nxt = {}
            for key, val in raw.items():
                acc = val * 1.4
                w = 1.4
                for nkey in neighbors(*key):
                    if nkey in raw:
                        acc += raw[nkey]
                        w += 1.0
                nxt[key] = acc / w
            raw = nxt
        return raw

    def _build_land_map(self, raw, rng):
        land = {key: val > LAND_THRESHOLD for key, val in raw.items()}
        for key, val in raw.items():
            if not land[key]:
                continue
            margin = val - LAND_THRESHOLD
            if margin < 0.06:
                chance = GAP_SCATTER_CHANCE * 1.4
            elif margin < 0.12:
                chance = GAP_SCATTER_CHANCE * 0.7
            else:
                chance = GAP_SCATTER_CHANCE * 0.2
            if rng.random() < chance:
                land[key] = False
        to_gap = []
        for key in land:
            if not land[key]:
                continue
            gn = sum(1 for n in neighbors(*key) if n in land and not land[n])
            val = raw[key]
            if gn >= 2 and val < LAND_THRESHOLD + 0.08:
                chance = GAP_CLUSTER_CHANCE
            elif gn >= 3 and val < LAND_THRESHOLD + 0.14:
                chance = GAP_CLUSTER_CHANCE * 0.55
            else:
                continue
            if rng.random() < chance:
                to_gap.append(key)
        for key in to_gap:
            land[key] = False
        return self._keep_main_continent(land)

    def _hex_components(self, cells):
        leftover = set(cells)
        comps = []
        while leftover:
            start = leftover.pop()
            seen = {start}
            dq = deque([start])
            while dq:
                cur = dq.popleft()
                for nkey in neighbors(*cur):
                    if nkey in leftover:
                        leftover.discard(nkey)
                        seen.add(nkey)
                        dq.append(nkey)
            comps.append(seen)
        return comps

    def _largest_component(self, cells):
        cells = set(cells)
        if not cells:
            return set()
        comps = self._hex_components(cells)
        return max(comps, key=lambda c: (len(c), -min(c)[0], -min(c)[1]))

    def _keep_main_continent(self, land):
        main = self._largest_component(k for k, is_land in land.items() if is_land)
        return {key: key in main for key in land}

    def _strip_tile_islands(self):
        land_keys = {k for k, t in self.tiles.items() if t.land}
        main = self._largest_component(land_keys)
        for key in land_keys - main:
            t = self.tiles[key]
            t.land = False
            t.owner = None
            t.shielded = False
            t.mega_id = None

    # --- generation ---

    def generate(self, width, height, seed=None):
        self.fast = self.fast
        self._times()
        self.seed = random.randrange(1, 2**31) if seed is None else seed
        self.width = width
        self.height = height
        self.tiles = {}
        self.megas = {}
        self.next_mega_id = 1
        self.queues = [[] for _ in PLAYERS]
        self.active = [[] for _ in PLAYERS]
        self.merges = []
        self.deconstructs = []
        self.choice = None
        self.factory_points = [0, 0, 0, 0]
        self.paused = False
        self.finished = False
        self.winners = []
        self._px.clear()
        keys = keys_for_screen(width, height)
        noise = ValueNoise(self.seed)
        raw = {}
        for q, r in keys:
            n = 0.6 * noise.fbm(q * 0.12, r * 0.12) + 0.4 * noise.fbm(q * 0.045 + 9, r * 0.045)
            raw[(q, r)] = (n + 1.0) * 0.5
        raw = self._smooth_noise(raw, passes=3)
        land_map = self._build_land_map(raw, random.Random(self.seed + 991))
        if not any(land_map.values()):
            origin = (0, 0)
            if origin not in land_map:
                land_map[origin] = True
            for key in list(land_map):
                if hex_distance(key, origin) <= 4:
                    land_map[key] = True
            land_map = self._keep_main_continent(land_map)
        for (q, r), land in land_map.items():
            self.tiles[(q, r)] = Tile(q, r, land=land)
        spawn = self._nearest_land((0, 0)) or (0, 0)
        self._force_blob(spawn, 4)
        self._strip_tile_islands()
        spawns = [spawn]
        land = [k for k, t in self.tiles.items() if t.land]
        for _ in range(3):
            best, best_d = spawn, -1
            for k in land:
                d = min(hex_distance(k, s) for s in spawns)
                if d > best_d:
                    best, best_d = k, d
            spawns.append(best)
            self._force_blob(best, 3)
        self._strip_tile_islands()
        for pid, pos in enumerate(spawns):
            if not self.tiles.get(pos) or not self.tiles[pos].land:
                pos = self._nearest_land(pos) or self._nearest_land((0, 0)) or (0, 0)
                spawns[pid] = pos
            t = self.tiles.get(pos)
            if t is None:
                t = Tile(pos[0], pos[1], land=True)
                self.tiles[pos] = t
            t.land = True
            t.owner = pid
            t.shielded = False
            t.mega_id = None
        self.spawns = list(spawns)
        self._px.clear()
        self._rebuild_indexes()
        self._bump_world(save=True)
        return spawn

    def _nearest_land(self, target):
        best = None
        best_d = 10**9
        for k, t in self.tiles.items():
            if not t.land:
                continue
            d = hex_distance(k, target)
            if d < best_d:
                best, best_d = k, d
        return best

    def _force_blob(self, center, radius):
        for key, t in self.tiles.items():
            if hex_distance(key, center) <= radius:
                t.land = True

    # --- queries ---

    def _count_kind(self, pid, kind):
        return sum(1 for m in self.megas.values() if m.owner == pid and m.kind == kind)

    def vision_range(self, pid):
        return BASE_VISION + EYE_BONUS * self._count_kind(pid, "eye")

    def capture_slots(self, pid):
        return 1 + self._count_kind(pid, "forge")

    def merge_slots(self, pid):
        return 1 + self._count_kind(pid, "factory")

    def tiles_left(self):
        self._maybe_rebuild_indexes()
        return self._unowned_land

    def empty_duration(self, pid):
        n = self._count_kind(pid, "hourglass")
        return max(self.t_min, self.t_empty * (HOURGLASS_FACTOR ** n))

    def enemy_duration(self, pid):
        n = self._count_kind(pid, "blade")
        return max(self.t_min, self.t_enemy * (BLADE_FACTOR ** n))

    def owned_cells(self, pid):
        return list(self._owned[pid])

    def tile_count(self, pid):
        self._maybe_rebuild_indexes()
        return len(self._owned[pid])

    def visible_set(self, pid=HUMAN):
        if pid == HUMAN and self._vis is not None:
            return self._vis
        self._maybe_rebuild_indexes()
        vr = self.vision_range(pid)
        seen = {}
        dq = deque()
        for key in self._owned[pid]:
            seen[key] = 0
            dq.append(key)
        vis = set(seen)
        while dq:
            cur = dq.popleft()
            d = seen[cur]
            if d >= vr:
                continue
            for n in neighbors(*cur):
                if n in self.tiles and n not in seen:
                    seen[n] = d + 1
                    vis.add(n)
                    dq.append(n)
        if pid == HUMAN:
            self._vis = vis
        return vis

    def job_maps(self):
        active = {}
        queued = set()
        for pid in PLAYERS:
            for j in self.active[pid]:
                for c in self._job_cells(j):
                    active[c] = j
        for j in self.queues[HUMAN]:
            for c in self._job_cells(j):
                queued.add(c)
        return active, queued

    def job_progress(self, q, r):
        key = (q, r)
        for pid in PLAYERS:
            for j in self.active[pid]:
                if key in self._job_cells(j):
                    return j
        return None

    def human_job_at(self, q, r):
        for j in self.active[HUMAN] + self.queues[HUMAN]:
            if j.mega_id is not None:
                m = self.megas.get(j.mega_id)
                if m and (q, r) in m.cells:
                    return j
            elif j.q == q and j.r == r:
                return j
        return None

    def queued_by(self, pid, q, r):
        for j in self.queues[pid]:
            if j.mega_id is not None:
                m = self.megas.get(j.mega_id)
                if m and (q, r) in m.cells:
                    return True
            elif j.q == q and j.r == r:
                return True
        return False

    def deconstruct_for(self, mega_id):
        for d in self.deconstructs:
            if d.mega_id == mega_id:
                return d
        return None

    def hover_info(self, x, y):
        key = self.hex_at(x, y)
        if key not in self.visible_set(HUMAN):
            return None
        tile = self.tiles.get(key)
        if not tile or not tile.land:
            return None
        if self.choice and key in self.choice.cells:
            dq = key[0] - self.choice.center[0]
            dr = key[1] - self.choice.center[1]
            kind = ABILITY_OFFSETS.get((dq, dr))
            if kind:
                return ABILITY_DESCRIPTIONS.get(kind)
        if tile.mega_id is not None:
            mega = self.megas.get(tile.mega_id)
            if mega and mega.owner == HUMAN:
                return ABILITY_DESCRIPTIONS.get(mega.kind)
        return None

    def start_deconstruct(self, mega_id):
        mega = self.megas.get(mega_id)
        if not mega or mega.owner != HUMAN:
            return False
        if self.deconstruct_for(mega_id):
            return False
        for m in self.merges:
            if m.owner == HUMAN and set(m.cells) == set(mega.cells):
                return False
        self.deconstructs.append(
            Deconstruct(
                mega_id=mega_id,
                owner=HUMAN,
                center=mega.center,
                cells=list(mega.cells),
                remaining=self.t_deconstruct,
                duration=self.t_deconstruct,
            )
        )
        self.dirty = True
        self.need_save = True
        return True

    def cancel_deconstruct(self, deco):
        if deco in self.deconstructs:
            self.deconstructs.remove(deco)
            self.dirty = True
            self.need_save = True

    def complete_deconstruct(self, deco):
        self.megas.pop(deco.mega_id, None)
        for c in deco.cells:
            t = self.tiles.get(c)
            if t:
                t.mega_id = None
        self._bump_world(save=True)

    # --- reach / queue ---

    def _maybe_rebuild_indexes(self):
        if self.tiles and self._unowned_land == 0 and not any(self._owned):
            self._rebuild_indexes()

    def _reach_cells(self, pid, include_queue=False, include_active=True):
        self._maybe_rebuild_indexes()
        cells = set(self._owned[pid])
        if include_active:
            for j in self.active[pid]:
                self._add_job_cells(j, cells)
        if include_queue:
            for j in self.queues[pid]:
                self._add_job_cells(j, cells)
        return cells

    def _add_job_cells(self, j, cells):
        if j.mega_id is not None:
            m = self.megas.get(j.mega_id)
            if m:
                cells.update(m.cells)
        else:
            cells.add((j.q, j.r))

    def _adjacent_to_reach(
        self, pid, key, mega_id=None, include_queue=False, include_active=True
    ):
        reach = self._reach_cells(
            pid, include_queue=include_queue, include_active=include_active
        )
        if mega_id is not None:
            mega = self.megas.get(mega_id)
            if not mega:
                return False
            for c in mega.cells:
                for n in neighbors(*c):
                    if n in reach:
                        return True
            return False
        for n in neighbors(*key):
            if n in reach:
                return True
        return False

    def _job_cells(self, j):
        cells = set()
        self._add_job_cells(j, cells)
        return cells

    def _jobs_rooted_in_empire(self, pid, jobs):
        """Jobs that still touch owned land, walking only through this job set."""
        owned = self._owned[pid]
        cell_to_job = {}
        for j in jobs:
            for c in self._job_cells(j):
                cell_to_job[c] = j
        seen = set(owned)
        dq = deque(owned)
        rooted = []
        claimed = set()
        while dq:
            cur = dq.popleft()
            for n in neighbors(*cur):
                if n in seen:
                    continue
                j = cell_to_job.get(n)
                if j is None:
                    continue
                seen.add(n)
                dq.append(n)
                jid = id(j)
                if jid in claimed:
                    continue
                claimed.add(jid)
                rooted.append(j)
                for c in self._job_cells(j):
                    if c not in seen:
                        seen.add(c)
                        dq.append(c)
        return rooted

    def reconnect_jobs(self, pid):
        jobs = self.active[pid] + self.queues[pid]
        if not jobs:
            return
        rooted = {id(j) for j in self._jobs_rooted_in_empire(pid, jobs)}
        self.active[pid] = [j for j in self.active[pid] if id(j) in rooted]
        self.queues[pid] = [j for j in self.queues[pid] if id(j) in rooted]

    def _job_valid(self, j):
        if j.mega_id is not None:
            m = self.megas.get(j.mega_id)
            return bool(m and m.owner != j.owner)
        t = self.tiles.get((j.q, j.r))
        if not t or not t.land:
            return False
        if t.owner == j.owner:
            return False
        if t.mega_id is not None:
            return False
        if t.owner is not None and t.shielded:
            return False
        return True

    def _same_job(self, j, key, mega_id=None):
        if mega_id is not None:
            return j.mega_id == mega_id
        if j.mega_id is not None:
            m = self.megas.get(j.mega_id)
            return bool(m and key in m.cells)
        return (j.q, j.r) == key

    def _has_job(self, pid, key, mega_id=None):
        for j in self.active[pid] + self.queues[pid]:
            if self._same_job(j, key, mega_id):
                return True
        return False

    def _start_job(self, job):
        if job.mega_id is not None:
            job.duration = self.enemy_duration(job.owner)
        else:
            t = self.tiles.get((job.q, job.r))
            if t and t.owner is None:
                job.duration = self.empty_duration(job.owner)
            else:
                job.duration = self.enemy_duration(job.owner)
        job.remaining = job.duration

    def enqueue(self, pid, key, mega_id=None):
        if self._has_job(pid, key, mega_id):
            return False
        job = Job(q=key[0], r=key[1], owner=pid, mega_id=mega_id)
        if not self._job_valid(job):
            return False
        include_q = len(self.active[pid]) >= self.capture_slots(pid)
        if not self._adjacent_to_reach(pid, key, mega_id, include_queue=include_q):
            return False
        if len(self.active[pid]) < self.capture_slots(pid):
            self._start_job(job)
            self.active[pid].append(job)
        else:
            self.queues[pid].append(job)
        self.dirty = True
        self.need_save = True
        self._legal = None
        return True

    def cancel_target(self, pid, key, mega_id=None):
        self.active[pid] = [
            j for j in self.active[pid] if not self._same_job(j, key, mega_id)
        ]
        self.queues[pid] = [
            j for j in self.queues[pid] if not self._same_job(j, key, mega_id)
        ]
        self.reconnect_jobs(pid)
        self.pump_queues(pid)
        self.dirty = True
        self.need_save = True
        self._legal = None

    def cancel_merge(self, merge):
        if merge in self.merges:
            self.merges.remove(merge)
            self.dirty = True
            self.need_save = True

    def prune_all(self):
        for pid in PLAYERS:
            self.active[pid] = [j for j in self.active[pid] if self._job_valid(j)]
            self.queues[pid] = [j for j in self.queues[pid] if self._job_valid(j)]
            self.reconnect_jobs(pid)
            self.pump_queues(pid)
        self.merges = [
            m for m in self.merges if self.footprint_ready(m.center, m.owner, m.kind in LARGE_KINDS)
        ]
        if self.choice and self.cluster_ready(self.choice.center, HUMAN) is None:
            self.choice = None
            self._bump_world()

    def pump_queues(self, pid):
        while len(self.active[pid]) < self.capture_slots(pid) and self.queues[pid]:
            j = self.queues[pid].pop(0)
            if not self._job_valid(j) or not self._adjacent_to_reach(
                pid, (j.q, j.r), j.mega_id, include_queue=False
            ):
                continue
            self._start_job(j)
            self.active[pid].append(j)

    def complete_capture(self, job):
        if not self._adjacent_to_reach(
            job.owner,
            (job.q, job.r),
            job.mega_id,
            include_queue=False,
            include_active=False,
        ):
            return
        if job.mega_id is not None:
            self.steal_mega(job.mega_id, job.owner)
        else:
            t = self.tiles.get((job.q, job.r))
            if t and self._job_valid(job):
                self._set_owner(t, job.owner)
                t.shielded = False
                t.mega_id = None
        for pid in PLAYERS:
            if pid == job.owner:
                continue
            self.active[pid] = [
                j for j in self.active[pid] if not self._same_job(j, (job.q, job.r), job.mega_id)
            ]
            self.queues[pid] = [
                j for j in self.queues[pid] if not self._same_job(j, (job.q, job.r), job.mega_id)
            ]
        self._bump_world(save=True)
        self.prune_disconnected()
        self.prune_all()

    def steal_mega(self, mega_id, pid):
        m = self.megas.get(mega_id)
        if not m or m.owner == pid:
            return
        m.owner = pid
        for c in m.cells:
            t = self.tiles.get(c)
            if t:
                self._set_owner(t, pid)
                t.mega_id = mega_id
                t.shielded = False
        cellset = set(m.cells)
        self.merges = [mg for mg in self.merges if cellset.isdisjoint(mg.cells)]
        if self.choice and cellset.intersection(self.choice.cells):
            self.choice = None
        self._bump_world(save=True)

    # --- merge / abilities ---

    def cluster_ready(self, center, pid):
        cells = cluster(*center)
        for c in cells:
            t = self.tiles.get(c)
            if not t or not t.land or t.owner != pid or t.mega_id is not None:
                return None
        return cells

    def footprint_ready(self, center, pid, large):
        if not large:
            return self.cluster_ready(center, pid)
        inner = self.cluster_ready(center, pid)
        if inner is None:
            return None
        cells = list(inner)
        for c in hex_ring(*center, 2):
            t = self.tiles.get(c)
            if t is None or not t.land:
                continue
            if t.owner != pid or t.mega_id is not None:
                return None
            cells.append(c)
        return cells

    def ready_clusters(self, pid):
        found = []
        seen = set()
        for key in self._owned[pid]:
            t = self.tiles.get(key)
            if not t or t.mega_id is not None:
                continue
            cells = self.cluster_ready(key, pid)
            if not cells:
                continue
            sig = tuple(sorted(cells))
            if sig in seen:
                continue
            seen.add(sig)
            found.append(key)
        return found

    def try_open_choice(self, center):
        inner = self.cluster_ready(center, HUMAN)
        if not inner:
            return False
        cells = list(inner)
        if self.footprint_ready(center, HUMAN, large=True) is not None:
            for c in hex_ring(*center, 2):
                t = self.tiles.get(c)
                if t and t.land:
                    cells.append(c)
        self.choice = Choice(center=center, cells=cells)
        self._bump_world()
        return True

    def start_merge(self, pid, cells, kind, center=None):
        if sum(1 for m in self.merges if m.owner == pid) >= self.merge_slots(pid):
            return False
        center = center or (cells[0] if cells else None)
        if center is None:
            return False
        large = kind in LARGE_KINDS
        ready = self.footprint_ready(center, pid, large)
        if ready is None:
            return False
        self.merges.append(
            Merge(
                owner=pid,
                center=center,
                cells=list(ready),
                kind=kind,
                remaining=self.t_merge,
                duration=self.t_merge,
            )
        )
        self.dirty = True
        self.need_save = True
        return True

    def complete_merge(self, merge):
        large = merge.kind in LARGE_KINDS
        ready = self.footprint_ready(merge.center, merge.owner, large)
        if ready is None:
            return
        mid = self.next_mega_id
        self.next_mega_id += 1
        cells = tuple(ready)
        interval = {
            "shield": self.t_shield,
            "shockwave": self.t_shock,
        }.get(merge.kind, 0.0)
        self.megas[mid] = Mega(
            id=mid,
            center=merge.center,
            cells=cells,
            owner=merge.owner,
            kind=merge.kind,
            remaining=interval,
            shock_radius=2,
        )
        for c in cells:
            t = self.tiles.get(c)
            if t:
                self._set_owner(t, merge.owner)
                t.mega_id = mid
                t.shielded = False
        self._bump_world(save=True)

    def shield_tick(self, mega):
        candidates = []
        for key in self._owned[mega.owner]:
            t = self.tiles.get(key)
            if t and t.mega_id is None and not t.shielded:
                candidates.append(t)
        if candidates:
            random.choice(candidates).shielded = True
            self._bump_world(save=True)
        mega.remaining = self.t_shield
        self.need_save = True

    def shockwave_pulse(self, mega):
        pid = mega.owner
        radius = mega.shock_radius
        stolen = set()
        for key in hex_ring(*mega.center, radius):
            t = self.tiles.get(key)
            if not t or not t.land:
                continue
            if t.owner == pid:
                continue
            if t.mega_id is not None:
                om = self.megas.get(t.mega_id)
                if om and om.owner != pid and om.id not in stolen:
                    self.steal_mega(om.id, pid)
                    stolen.add(om.id)
                continue
            if t.owner is not None and t.shielded:
                continue
            self._set_owner(t, pid)
            t.shielded = False
        mega.shock_radius += 1
        mega.remaining = self.t_shock
        self._bump_world(save=True)
        self.prune_disconnected()
        self.prune_all()

    # --- clicks ---

    def click(self, x, y, double=False):
        mega, mega_key = self.mega_at(x, y)
        if mega is not None:
            self.click_hex(mega_key, double=double)
            return
        key = self.hex_at(x, y)
        if key not in self.tiles:
            return
        self.click_hex(key, double=double)

    def click_hex(self, key, double=False):
        if self.paused or self.finished:
            return
        q, r = key
        vis = self.visible_set(HUMAN)
        if key not in vis:
            return
        tile = self.tiles.get(key)
        if not tile or not tile.land:
            return

        if self.choice:
            if key in self.choice.cells:
                dq, dr = q - self.choice.center[0], r - self.choice.center[1]
                kind = ABILITY_OFFSETS.get((dq, dr))
                if kind:
                    self.start_merge(
                        HUMAN, self.choice.cells, kind, center=self.choice.center
                    )
                self.choice = None
                self.dirty = True
                return
            self.choice = None
            self.dirty = True
            return

        if double:
            if tile.owner == HUMAN and tile.mega_id is None:
                self.try_open_choice(key)
            elif tile.mega_id is not None:
                mega = self.megas.get(tile.mega_id)
                if mega and mega.owner == HUMAN:
                    existing = self.deconstruct_for(mega.id)
                    if existing:
                        self.cancel_deconstruct(existing)
                    else:
                        self.start_deconstruct(mega.id)
            return

        if self.human_job_at(q, r):
            j = self.human_job_at(q, r)
            self.cancel_target(HUMAN, key, j.mega_id)
            return

        mega = self.megas.get(tile.mega_id) if tile.mega_id is not None else None
        if mega and mega.owner == HUMAN:
            existing = self.deconstruct_for(mega.id)
            if existing:
                self.cancel_deconstruct(existing)
            else:
                self.start_deconstruct(mega.id)
            return
        if mega and mega.owner != HUMAN:
            self.enqueue(HUMAN, mega.center, mega_id=mega.id)
            return

        if tile.owner == HUMAN:
            return
        if tile.mega_id is not None:
            return
        if tile.owner is not None and tile.shielded:
            return
        self.enqueue(HUMAN, key)

    def legal_human_moves(self):
        if self.finished:
            return False
        if self._legal is not None:
            return self._legal
        vis = self.visible_set(HUMAN)
        reach = self._reach_cells(HUMAN, include_queue=True)
        ok = False
        for cell in reach:
            for n in neighbors(*cell):
                if n not in vis:
                    continue
                t = self.tiles.get(n)
                if not t or not t.land or t.owner == HUMAN:
                    continue
                if t.mega_id is not None:
                    m = self.megas.get(t.mega_id)
                    if m and m.owner != HUMAN:
                        ok = True
                        break
                    continue
                if t.owner is None or not t.shielded:
                    ok = True
                    break
            if ok:
                break
        self._legal = ok
        return ok

    def human_busy(self):
        return bool(
            self.active[HUMAN]
            or self.queues[HUMAN]
            or any(m.owner == HUMAN for m in self.merges)
            or any(d.owner == HUMAN for d in self.deconstructs)
        )

    def animating(self):
        if self.finished:
            return False
        if self.choice:
            return True
        if any(self.active[p] for p in PLAYERS):
            return True
        if self.merges:
            return True
        if self.deconstructs:
            return True
        return any(
            m.kind in TIMED_ABILITIES for m in self.megas.values()
        )

    def check_win(self):
        if self.finished:
            return
        self._maybe_rebuild_indexes()
        if self._unowned_land or not self.tiles:
            return
        self.finished = True
        counts = [self.tile_count(p) for p in PLAYERS]
        best = max(counts)
        self.winners = [p for p in PLAYERS if counts[p] == best]
        self.dirty = True
        self.need_save = True

    def ability_interval(self, kind):
        if kind == "shield":
            return self.t_shield
        if kind == "shockwave":
            return self.t_shock
        return 0.0

    def update(self, dt):
        if self.paused or self.finished or dt <= 0:
            return
        for pid in PLAYERS:
            for j in self.active[pid]:
                j.remaining -= dt
                if j.remaining <= 0:
                    j.remaining = 0
            while True:
                finishing = [j for j in self.active[pid] if j.remaining <= 0]
                completable = self._jobs_rooted_in_empire(pid, finishing)
                if not completable:
                    break
                self.active[pid].remove(completable[0])
                self.complete_capture(completable[0])
            if self.queues[pid] and len(self.active[pid]) < self.capture_slots(pid):
                self.pump_queues(pid)
        for merge in list(self.merges):
            merge.remaining -= dt
            if merge.remaining <= 0:
                self.merges.remove(merge)
                self.complete_merge(merge)
        for mega in list(self.megas.values()):
            if mega.kind not in TIMED_ABILITIES:
                continue
            mega.remaining -= dt
            if mega.remaining <= 0:
                if mega.kind == "shield":
                    self.shield_tick(mega)
                else:
                    self.shockwave_pulse(mega)
        for deco in list(self.deconstructs):
            deco.remaining -= dt
            if deco.remaining <= 0:
                self.deconstructs.remove(deco)
                self.complete_deconstruct(deco)
        self.check_win()

    def to_dict(self):
        owned = []
        for t in self.tiles.values():
            if not t.land or (t.owner is None and not t.shielded and t.mega_id is None):
                continue
            owned.append((t.q, t.r, t.owner, int(t.shielded), t.mega_id))
        return {
            "v": 2,
            "seed": self.seed,
            "fast": self.fast,
            "width": self.width,
            "height": self.height,
            "next_mega_id": self.next_mega_id,
            "paused": self.paused,
            "finished": self.finished,
            "winners": self.winners,
            "spawns": [list(s) if s else None for s in self.spawns],
            "owned": owned,
            "megas": [
                {
                    "id": m.id,
                    "center": list(m.center),
                    "cells": [list(c) for c in m.cells],
                    "owner": m.owner,
                    "kind": m.kind,
                    "remaining": m.remaining,
                    "shock_radius": m.shock_radius,
                }
                for m in self.megas.values()
            ],
            "queues": [
                [
                    {
                        "q": j.q,
                        "r": j.r,
                        "mega_id": j.mega_id,
                        "remaining": j.remaining,
                        "duration": j.duration,
                    }
                    for j in qs
                ]
                for qs in self.queues
            ],
            "active": [
                [
                    {
                        "q": j.q,
                        "r": j.r,
                        "mega_id": j.mega_id,
                        "remaining": j.remaining,
                        "duration": j.duration,
                    }
                    for j in qs
                ]
                for qs in self.active
            ],
            "merges": [
                {
                    "owner": m.owner,
                    "center": list(m.center),
                    "cells": [list(c) for c in m.cells],
                    "kind": m.kind,
                    "remaining": m.remaining,
                    "duration": m.duration,
                }
                for m in self.merges
            ],
            "deconstructs": [
                {
                    "mega_id": d.mega_id,
                    "owner": d.owner,
                    "center": list(d.center),
                    "cells": [list(c) for c in d.cells],
                    "remaining": d.remaining,
                    "duration": d.duration,
                }
                for d in self.deconstructs
            ],
            "choice": None
            if self.choice is None
            else {
                "center": list(self.choice.center),
                "cells": [list(c) for c in self.choice.cells],
            },
        }

    @classmethod
    def from_dict(cls, data, fast=None):
        g = cls(
            seed=data.get("seed", 1),
            fast=data.get("fast", False) if fast is None else fast,
            width=data.get("width", 1920),
            height=data.get("height", 1080),
            next_mega_id=data.get("next_mega_id", 1),
            factory_points=list(data.get("factory_points", [0, 0, 0, 0])),
            paused=data.get("paused", False),
            finished=data.get("finished", False),
            winners=list(data.get("winners", [])),
        )
        g._times()
        if data.get("tiles"):
            g.tiles = {}
            for raw in data.get("tiles", []):
                g.tiles[(raw["q"], raw["r"])] = Tile(
                    q=raw["q"],
                    r=raw["r"],
                    land=raw["land"],
                    owner=raw.get("owner"),
                    shielded=raw.get("shielded", False),
                    mega_id=raw.get("mega_id"),
                )
        else:
            g.generate(g.width, g.height, seed=g.seed)
            g.paused = data.get("paused", False)
            g.finished = data.get("finished", False)
            g.winners = list(data.get("winners", []))
            g.next_mega_id = data.get("next_mega_id", 1)
            for t in g.tiles.values():
                t.owner = None
                t.shielded = False
                t.mega_id = None
            for row in data.get("owned", []):
                q, r, owner, shielded, mega_id = row
                t = g.tiles.get((q, r))
                if t is None:
                    t = Tile(int(q), int(r), land=True)
                    g.tiles[(int(q), int(r))] = t
                t.land = True
                t.owner = owner
                t.shielded = bool(shielded)
                t.mega_id = mega_id
            g.megas = {}
            g.queues = [[] for _ in PLAYERS]
            g.active = [[] for _ in PLAYERS]
            g.merges = []
            g.deconstructs = []
            g.choice = None
        g.megas = {}
        for raw in data.get("megas", []):
            mid = raw["id"]
            g.megas[mid] = Mega(
                id=mid,
                center=tuple(raw["center"]),
                cells=tuple(tuple(c) for c in raw["cells"]),
                owner=raw["owner"],
                kind=raw["kind"],
                remaining=raw.get("remaining", 0.0),
                shock_radius=raw.get("shock_radius", 2),
            )
        g.queues = [[] for _ in PLAYERS]
        g.active = [[] for _ in PLAYERS]
        for pid, blob in enumerate(data.get("queues", [])):
            for raw in blob:
                g.queues[pid].append(
                    Job(
                        q=raw["q"],
                        r=raw["r"],
                        owner=pid,
                        mega_id=raw.get("mega_id"),
                        remaining=raw.get("remaining", 0.0),
                        duration=raw.get("duration", 1.0),
                    )
                )
        for pid, blob in enumerate(data.get("active", [])):
            for raw in blob:
                g.active[pid].append(
                    Job(
                        q=raw["q"],
                        r=raw["r"],
                        owner=pid,
                        mega_id=raw.get("mega_id"),
                        remaining=raw.get("remaining", 0.0),
                        duration=raw.get("duration", 1.0),
                    )
                )
        g.merges = []
        for raw in data.get("merges", []):
            g.merges.append(
                Merge(
                    owner=raw["owner"],
                    center=tuple(raw["center"]),
                    cells=[tuple(c) for c in raw["cells"]],
                    kind=raw["kind"],
                    remaining=raw.get("remaining", 0.0),
                    duration=raw.get("duration", 1.0),
                )
            )
        g.deconstructs = []
        for raw in data.get("deconstructs", []):
            g.deconstructs.append(
                Deconstruct(
                    mega_id=raw["mega_id"],
                    owner=raw["owner"],
                    center=tuple(raw["center"]),
                    cells=[tuple(c) for c in raw["cells"]],
                    remaining=raw.get("remaining", 0.0),
                    duration=raw.get("duration", 1.0),
                )
            )
        ch = data.get("choice")
        if ch:
            g.choice = Choice(
                center=tuple(ch["center"]),
                cells=[tuple(c) for c in ch["cells"]],
            )
        g._rebuild_indexes()
        g._apply_spawns(data.get("spawns"))
        g._vis = None
        g._legal = None
        g.prune_disconnected()
        g.prune_all()
        g.dirty = True
        g.need_save = False
        return g
