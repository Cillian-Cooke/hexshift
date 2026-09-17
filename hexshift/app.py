import argparse
import os
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
gi.require_version("Keybinder", "3.0")

from gi.repository import AyatanaAppIndicator3 as AppIndicator3
from gi.repository import GLib, Gtk, Keybinder

from hexshift.ai import tick_ais
from hexshift.constants import AI_PERIOD, ANIM_PERIOD, HIDE_ACCEL, SAVE_PERIOD, TICK_MS
from hexshift.game import Game
from hexshift.overlay import Overlay, _workarea
from hexshift.save import load_game, save_game

ROOT = os.path.abspath(os.path.dirname(__file__))
_ICON_CANDIDATES = (
    os.path.join(ROOT, "icons", "tray.svg"),
    os.path.join(os.path.dirname(ROOT), "icons", "tray.svg"),
)
ICON = next((p for p in _ICON_CANDIDATES if os.path.isfile(p)), _ICON_CANDIDATES[0])
ICON_ATTENTION = ICON.replace("tray.svg", "tray-attention.svg")


class App:
    def __init__(self, fast=False, new_game=False):
        self.fast = fast
        self.game = None
        if not new_game:
            self.game = load_game(fast=fast)
        if self.game is None:
            self.game = Game(fast=fast)
            wa = _workarea()
            self.game.generate(max(wa.width, 800), max(wa.height, 600))
        else:
            self.game.fast = fast
            self.game._times()

        self.overlay = Overlay(self.game)
        self.overlay.connect("destroy", self.quit)
        self.overlay.show_all()

        self._ai_accum = [0.0, 0.0, 0.0, 0.0]
        self._save_accum = 0.0
        self._anim_accum = 0.0
        self._last = time.monotonic()
        self._attention = False
        self._tray_state = None

        self.hide_item = Gtk.CheckMenuItem(label="Hide overlay\tCtrl+Alt+H")
        self.hide_item.connect("toggled", self._on_hide)
        self.pause_item = Gtk.CheckMenuItem(label="Pause timers")
        self.pause_item.set_active(self.game.paused)
        self.pause_item.connect("toggled", self._on_pause)

        Keybinder.init()
        if not Keybinder.bind(HIDE_ACCEL, self._on_hide_hotkey):
            print("Could not bind Ctrl+Alt+H (already in use?). Use the tray menu.", file=sys.stderr)

        menu = Gtk.Menu()
        for widget in (self.hide_item, self.pause_item):
            menu.append(widget)
        new_item = Gtk.MenuItem(label="New game")
        new_item.connect("activate", self._on_new)
        menu.append(new_item)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit)
        menu.append(quit_item)
        menu.show_all()

        self.indicator = AppIndicator3.Indicator.new(
            "hexshift",
            ICON,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_attention_icon_full(ICON_ATTENTION, "Your move")
        self.indicator.set_icon_full(ICON, "Hexshift")
        self.indicator.set_menu(menu)
        self.indicator.set_title("Hexshift")

        GLib.timeout_add(TICK_MS, self._tick)
        self._refresh_tray()

    def _tick(self):
        now = time.monotonic()
        dt = min(1.0, now - self._last)
        self._last = now
        self.game.update(dt)
        tick_ais(self.game, self._ai_accum, dt, AI_PERIOD)
        if self.game.need_save:
            self._save_accum += dt
            if self._save_accum >= SAVE_PERIOD:
                try:
                    save_game(self.game)
                except OSError:
                    pass
                self._save_accum = 0.0
        else:
            self._save_accum = 0.0
        if not self.overlay.hidden:
            if self.game.dirty:
                self.overlay.area.queue_draw()
                self._anim_accum = 0.0
            elif self.game.animating():
                self._anim_accum += dt
                if self._anim_accum >= ANIM_PERIOD:
                    self._anim_accum = 0.0
                    self.overlay.area.queue_draw()
        self._refresh_tray()
        return True

    def _refresh_tray(self):
        idle_with_moves = (
            not self.game.paused
            and not self.game.human_busy()
            and self.game.legal_human_moves()
        )
        if idle_with_moves == self._tray_state:
            return
        self._tray_state = idle_with_moves
        if idle_with_moves and not self._attention:
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ATTENTION)
            self.indicator.set_title("Hexshift — your move")
            self._attention = True
        elif not idle_with_moves and self._attention:
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.indicator.set_title("Hexshift")
            self._attention = False

    def _on_hide(self, item):
        self.overlay.set_hidden(item.get_active())

    def _on_hide_hotkey(self, *_args):
        self.hide_item.set_active(not self.hide_item.get_active())

    def _on_pause(self, item):
        self.game.paused = item.get_active()
        self.game.need_save = True

    def _on_new(self, *_args):
        dialog = Gtk.MessageDialog(
            transient_for=self.overlay,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Start a new map?",
        )
        dialog.format_secondary_text("Current progress will be replaced.")
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        wa = _workarea()
        self.game.fast = self.fast
        self.game.generate(max(wa.width, 800), max(wa.height, 600))
        self.overlay.refresh_workarea()
        try:
            save_game(self.game)
        except OSError:
            pass

    def quit(self, *_args):
        try:
            Keybinder.unbind(HIDE_ACCEL)
        except Exception:
            pass
        try:
            save_game(self.game)
        except OSError:
            pass
        Gtk.main_quit()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hexshift overlay")
    parser.add_argument("--fast", action="store_true", help="Short timers for testing")
    parser.add_argument("--new", action="store_true", help="Ignore saved game")
    args = parser.parse_args(argv)
    ok, _argv = Gtk.init_check()
    if not ok:
        print("Hexshift needs a graphical display (Cinnamon / X11).", file=sys.stderr)
        return 1
    App(fast=args.fast, new_game=args.new)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
