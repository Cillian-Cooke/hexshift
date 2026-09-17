# Hexshift

A slow hexagonal territory game that sits over your Linux desktop. Translucent hex tiles cover the work area with gaps between them, so clicks on fog and empty space pass through to whatever is underneath. Queue captures, walk away, and come back when timers finish.

Built for **Linux Mint (Cinnamon / X11)**. Uses Python 3, GTK 3, Cairo, and Ayatana AppIndicator (already on Mint, no extra packages).

## Run

From this folder:

```bash
python3 -m hexshift
```

or:

```bash
python3 hexshift.py
```

| Flag | Effect |
|------|--------|
| `--fast` | Short timers (seconds instead of minutes) for testing |
| `--new` | Ignore the saved game and generate a fresh map |

Progress autosaves to `~/.local/share/hexshift/save.json`.

## Pin to the menu

```bash
cp hexshift.desktop ~/.local/share/applications/
```

Then find **Hexshift** in the Cinnamon application menu.

## How it plays

### The map

You start as **teal** at the centre of a procedurally generated island. Three AI factions expand from the fog: **Coral**, **Amber**, and **Violet**.

You begin with **3 tiles of vision** around owned territory. Unexplored land stays hidden until you expand into it.

### Capturing tiles

Click an **adjacent** hex to queue a capture:

| Target | Time |
|--------|------|
| Empty land | 5 minutes |
| Enemy land | 10 minutes |

Queue several captures and leave them running. **Forge** megatiles let you run up to **2 captures at once** (1 by default).

**Cancel a capture:** click the same hex again, or tap the **X** on its banner in the bottom-right HUD. Cancelling drops that job and any queued jobs that no longer have a valid path.

### Megatiles

When you own a **cluster of 7 small hexes** (one centre plus six neighbours), **double-click** the centre hex to open the ability picker. Choose one:

| Ability | Effect |
|---------|--------|
| **Eye** | +3 vision range (stacks with other Eyes) |
| **Hourglass** | Empty captures 20% faster per Hourglass (stacks) |
| **Blade** | Enemy captures 40% faster per Blade (stacks) |
| **Shield** | Every 4 min, shields a random owned small tile (immune to capture and shockwave) |
| **Shockwave** | Every 15 min, pulses outward one ring at a time, converting unshielded enemy tiles; can steal enemy megatiles |
| **Forge** | +1 simultaneous capture slot (max 2) |
| **Factory** | +5 score points every 10 min |

Building a megatile takes **10 minutes**. Only one merge can run at a time. Cancel it from the banner X if you picked the wrong ability.

**Stealing enemy megatiles:** click an enemy megatile you can reach. It captures like enemy land (10 min) and transfers the whole structure to you when done.

### Scoring

The HUD shows tile count and factory points for all four players. Small tiles count as 1; megatiles count as 7.

### Tray icon

Hexshift lives in the Cinnamon panel tray:

- Switches to an **attention mark** when you have a legal move and nothing is currently capturing
- **Hide overlay** toggles visibility (timers keep running). Shortcut: **Ctrl+Alt+H** (works from any app)
- **Pause timers** freezes all captures, merges, and AI
- **New game** wipes progress and generates a fresh map
- **Quit**

## Project layout

```
hexshift/
├── hexshift.py          # Entry point
├── hexshift/
│   ├── app.py           # Tray icon, game loop, autosave
│   ├── game.py          # Rules, timers, AI hooks
│   ├── overlay.py       # Full-screen transparent window
│   ├── draw.py          # Cairo rendering
│   ├── hud.py           # Score panel and capture banners
│   ├── ai.py            # AI expansion
│   ├── save.py          # JSON save/load
│   └── constants.py     # Timings and colours
├── icons/               # Tray icons
└── hexshift.desktop     # Cinnamon launcher
```

## Requirements

- Linux with X11 (Cinnamon on Linux Mint tested)
- Python 3.11+
- GTK 3, PyGObject, Cairo, Ayatana AppIndicator3
