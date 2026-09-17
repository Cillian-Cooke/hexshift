import argparse
import sys


def overlay_importable():
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return False
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        gi.require_version("Keybinder", "3.0")
        from gi.repository import Gtk

        ok, _argv = Gtk.init_check()
        return bool(ok)
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hexshift")
    parser.add_argument("--fast", action="store_true", help="Short timers for testing")
    parser.add_argument("--new", action="store_true", help="Ignore saved game")
    parser.add_argument("--overlay", action="store_true", help="Linux desktop overlay")
    parser.add_argument("--window", action="store_true", help="Windowed mode on every OS")
    args = parser.parse_args(argv)

    extra = []
    if args.fast:
        extra.append("--fast")
    if args.new:
        extra.append("--new")

    want_overlay = args.overlay or (not args.window and overlay_importable())
    if args.window:
        want_overlay = False

    if want_overlay:
        try:
            from hexshift.app import main as overlay_main
        except Exception as exc:
            print(f"Overlay unavailable ({exc}); starting windowed mode.", file=sys.stderr)
        else:
            return overlay_main(extra)

    from hexshift.window import run

    return run(fast=args.fast, new_game=args.new)


if __name__ == "__main__":
    raise SystemExit(main())
