import json
import os
import sys
import tempfile

from hexshift.game import Game

APP_ID = "hexshift"


def data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "Hexshift")
    elif sys.platform == "darwin":
        path = os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", "hexshift"
        )
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
        path = os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


def save_path():
    return os.path.join(data_dir(), "save.json")


def load_game(fast=None):
    path = save_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return Game.from_dict(data, fast=fast)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def save_game(game: Game):
    path = save_path()
    payload = game.to_dict()
    fd, tmp = tempfile.mkstemp(prefix="hexshift-", suffix=".json", dir=data_dir())
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    game.need_save = False
