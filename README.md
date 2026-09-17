# Hexshift

Install and run on Linux, Windows, or macOS (Python 3.10+):

```bash
curl -fsSL https://raw.githubusercontent.com/Cillian-Cooke/hexshift/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/Cillian-Cooke/hexshift/main/install.ps1 | iex
```

A slow hexagonal territory game. On Linux with GTK it can sit as a translucent overlay over the desktop; everywhere else it opens in a window. Queue captures, walk away, and come back when timers finish.

## Play

```bash
python3 -m hexshift
```

| Flag | Effect |
|------|--------|
| `--fast` | Short timers (seconds instead of minutes) for testing |
| `--new` | Ignore the saved game and generate a fresh map |
| `--window` | Force the windowed client |
| `--overlay` | Force the Linux desktop overlay |

Progress saves to `~/.local/share/hexshift/` on Linux, `~/Library/Application Support/hexshift/` on macOS, and `%APPDATA%\Hexshift\` on Windows.

## Pin to the Linux menu

After install, Hexshift is added to your application menu. From a git checkout:

```bash
cp hexshift.desktop ~/.local/share/applications/
```

## How it plays

### The map

You start as **teal** at the centre of a procedurally generated continent. Three AI factions expand from the fog: **Coral**, **Amber**, and **Violet**.

You begin with **3 tiles of vision** around owned territory. Unexplored land stays hidden until you expand into it.

### Capturing tiles

Click an **adjacent** hex to queue a capture:

| Target | Time |
|--------|------|
| Empty land | 5 minutes |
| Enemy land | 10 minutes |

Queue several captures and leave them running. **Forge** megatiles add extra simultaneous capture slots.

**Cancel a capture:** click the same hex again, or tap the **X** on its banner in the bottom-right HUD. Cancelling drops that job and any queued jobs that no longer have a valid path.

### Supply lines

Land you own must stay connected to your home. If another player cuts a branch off, that whole branch becomes empty — shields and megatiles included.

### Megatiles

When you own a **cluster of 7 small hexes** (one centre plus six neighbours), **double-click** the centre hex to open the ability picker. Inner abilities make a 7-cell megatile; outer-ring picks make a large footprint. Builds take **15 minutes**.

| Ability | Effect |
|---------|--------|
| **Eye** | +3 vision range (stacks) |
| **Hourglass** | Empty captures 20% faster (stacks) |
| **Blade** | Enemy captures 40% faster (stacks) |
| **Shield** | Every 4 min, shields a random owned small tile |
| **Shockwave** | Every 15 min, pulses outward, converting unshielded land |
| **Forge** | +1 simultaneous capture slot |
| **Factory** | +1 simultaneous megatile-build slot |

**Stealing enemy megatiles:** click an enemy megatile you can reach. It captures like enemy land (10 min) and transfers the whole structure to you when done.

### Scoring

The game ends when every land tile is owned. Most tiles wins (a small megatile counts as 7, a large one as its full footprint).

### Controls

Windowed: **P** pause, **N** (twice) new map, **I** rules, **H** hide HUD, **F11** fullscreen, **Esc** quit.

Linux overlay: tray icon plus **Ctrl+Alt+H** to hide. Timers keep running while hidden.

## Requirements

- Python 3.10+ (the install command uses pip to fetch [pygame-ce](https://pyga.me/))
- Linux overlay extra: GTK 3, PyGObject, Cairo, Ayatana AppIndicator3, Keybinder 3.0 (typical on Linux Mint)
