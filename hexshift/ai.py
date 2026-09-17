import random

from hexshift.constants import HUMAN, PLAYERS
from hexshift.game import Game
from hexshift.hexmath import cluster, neighbors

AI_WEIGHTS = {
    "eye": 3,
    "hourglass": 3,
    "forge": 3,
    "shockwave": 3,
    "blade": 2,
    "factory": 1,
    "shield": 1,
}


def _frontier(game: Game, pid: int):
    reach = game._reach_cells(pid, include_queue=True)
    empty = []
    enemy = []
    megas = []
    seen_mega = set()
    seen = set()
    for cell in reach:
        for n in neighbors(*cell):
            if n in seen:
                continue
            seen.add(n)
            t = game.tiles.get(n)
            if not t or not t.land or t.owner == pid:
                continue
            if t.mega_id is not None:
                m = game.megas.get(t.mega_id)
                if m and m.owner != pid and m.id not in seen_mega:
                    seen_mega.add(m.id)
                    megas.append((m.center, m.id))
                continue
            if t.owner is None:
                empty.append((n, None))
            elif not t.shielded:
                enemy.append((n, None))
    return empty, enemy, megas


def step(game: Game, pid: int):
    if game.paused or game.finished or pid == HUMAN:
        return
    pending = len(game.active[pid]) + len(game.queues[pid])
    building = sum(1 for m in game.merges if m.owner == pid)
    if building < game.merge_slots(pid) and random.random() < 0.18:
        centers = game.ready_clusters(pid)
        if centers:
            center = random.choice(centers)
            kinds = list(AI_WEIGHTS)
            weights = [AI_WEIGHTS[k] for k in kinds]
            kind = random.choices(kinds, weights=weights, k=1)[0]
            # map kind to the offset cell so start_merge still uses cluster(center)
            game.start_merge(pid, cluster(*center), kind)
            return
    if pending >= max(5, game.capture_slots(pid) + 3):
        return
    empty, enemy, megas = _frontier(game, pid)
    roll = random.random()
    target = None
    if megas and roll > 0.92:
        target = random.choice(megas)
    elif enemy and roll > 0.78:
        target = random.choice(enemy)
    elif empty:
        target = random.choice(empty)
    elif enemy:
        target = random.choice(enemy)
    elif megas:
        target = random.choice(megas)
    if target:
        key, mega_id = target
        game.enqueue(pid, key, mega_id=mega_id)


def tick_ais(game: Game, accum: list, dt: float, period: float):
    if game.paused or game.finished:
        return
    for i, pid in enumerate(PLAYERS):
        if pid == HUMAN:
            continue
        accum[i] += dt
        # stagger so they don't all act on the same frame
        wait = period + pid * 0.7
        if accum[i] >= wait:
            accum[i] = 0.0
            step(game, pid)
