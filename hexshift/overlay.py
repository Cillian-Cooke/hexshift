import time

import cairo
from gi.repository import Gdk, GLib, Gtk

from hexshift.draw import (
    collect_click_boxes,
    draw_merge_progress,
    draw_tooltip,
    draw_world_fx,
    draw_world_static,
)
from hexshift.game import Game
from hexshift.hud import apply_hud_action, draw_hud, hit_hud, hud_boxes, layout_hud, show_help_dialog


def _workarea():
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor() if display else None
    if monitor is None and display is not None:
        monitor = display.get_monitor(0)
    if monitor is None:
        return Gdk.Rectangle()
    return monitor.get_workarea()


class Overlay(Gtk.Window):
    def __init__(self, game: Game):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.game = game
        self.hidden = False
        self.hud_collapsed = False
        self._banners = []
        self._score = (0, 0, 1, 1)
        self._chrome = {}
        self._shape_key = None
        self._hover_x = None
        self._hover_y = None
        self._hover_info = None
        self._hover_draw = 0.0
        self._world_surf = None
        self._world_key = None
        self._world_boxes = None
        self._world_boxes_rev = None

        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.stick()
        self.set_resizable(False)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)

        wa = _workarea()
        self.move(wa.x, wa.y)
        self.set_default_size(wa.width, wa.height)
        game.set_size(wa.width, wa.height)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(wa.width, wa.height)
        self.area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.area.connect("draw", self._on_draw)
        self.area.connect("button-press-event", self._on_click)
        self.area.connect("motion-notify-event", self._on_motion)
        self.area.connect("leave-notify-event", self._on_leave)
        self.add(self.area)

        self.connect("realize", self._on_realize)
        self.connect("configure-event", self._on_configure)

        css = Gtk.CssProvider()
        css.load_from_data(b"window, drawingarea { background-color: transparent; }")
        Gtk.StyleContext.add_provider_for_screen(
            screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _on_realize(self, *_args):
        gdk = self.get_window()
        if gdk is None:
            return
        gdk.set_override_redirect(False)
        gdk.set_keep_above(True)
        try:
            gdk.set_pass_through(False)
        except AttributeError:
            pass

    def _on_configure(self, _widget, event):
        if event.width > 0 and event.height > 0:
            size_changed = event.width != self.game.width or event.height != self.game.height
            self.game.set_size(event.width, event.height)
            self.area.set_size_request(event.width, event.height)
            if size_changed:
                self._shape_key = None
                self._world_key = None
                self._world_surf = None
                self._world_boxes_rev = None
        return False

    def _on_motion(self, _area, event):
        self._hover_x = event.x
        self._hover_y = event.y
        if self.hidden:
            return False
        info = self.game.hover_info(event.x, event.y)
        if info == self._hover_info:
            if not info:
                return False
            now = time.monotonic()
            if now - self._hover_draw < 0.12:
                return False
            self._hover_draw = now
        else:
            self._hover_info = info
            self._hover_draw = time.monotonic()
        self.area.queue_draw()
        return False

    def _on_leave(self, _area, _event):
        self._hover_x = None
        self._hover_y = None
        if self._hover_info is not None:
            self._hover_info = None
            self.area.queue_draw()
        return False

    def _ensure_world_cache(self, w, h):
        scale = self.get_scale_factor() if hasattr(self, "get_scale_factor") else 1
        key = (w, h, scale, self.game.world_rev)
        if self._world_surf is not None and self._world_key == key:
            return self._world_surf
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w * scale), max(1, h * scale))
        if scale != 1:
            surf.set_device_scale(scale, scale)
        cr = cairo.Context(surf)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        draw_world_static(cr, self.game)
        self._world_surf = surf
        self._world_key = key
        return surf

    def _on_draw(self, _area, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        if not self.hidden:
            surf = self._ensure_world_cache(w, h)
            cr.set_source_surface(surf, 0, 0)
            cr.paint()
            draw_world_fx(cr, self.game)
            draw_merge_progress(cr, self.game)
            self._banners, self._score, self._chrome = layout_hud(
                self.game, w, h, collapsed=self.hud_collapsed
            )
            draw_hud(cr, self.game, self._banners, self._score, self._chrome)
            if self._hover_x is not None and self._hover_y is not None:
                draw_tooltip(cr, self.game, self._hover_x, self._hover_y, w, h)
        else:
            self._banners, self._score, self._chrome = [], (0, 0, 0, 0), {}
        shape_key = (
            self.hidden,
            self.hud_collapsed,
            self.game.world_rev,
            len(self._banners),
            self._score,
            tuple(self._chrome.items()),
        )
        if shape_key != self._shape_key:
            self._shape_key = shape_key
            GLib.idle_add(self._update_input_shape)
        self.game.dirty = False
        return False

    def _world_click_boxes(self):
        if self._world_boxes_rev != self.game.world_rev:
            self._world_boxes = collect_click_boxes(self.game)
            self._world_boxes_rev = self.game.world_rev
        return self._world_boxes

    def _update_input_shape(self):
        gdk = self.get_window()
        if gdk is None:
            return False
        region = cairo.Region()
        if not self.hidden:
            boxes = list(self._world_click_boxes())
            boxes.extend(hud_boxes(self._banners, self._score, self._chrome))
            for x, y, w, h in boxes:
                if w <= 0 or h <= 0:
                    continue
                region.union(cairo.RectangleInt(int(x), int(y), int(w), int(h)))
        try:
            gdk.input_shape_combine_region(region, 0, 0)
        except TypeError:
            gdk.input_shape_combine_region(region)
        return False

    def _on_click(self, _area, event):
        if event.button != 1:
            return False
        double = event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS
        if not self.hidden:
            hit = hit_hud(self._banners, self._score, self._chrome, event.x, event.y)
            if hit:
                kind, payload = hit if isinstance(hit, tuple) else (hit, None)
                if kind == "info":
                    self.set_accept_focus(True)
                    try:
                        show_help_dialog(self)
                    finally:
                        self.set_accept_focus(False)
                    return True
                if kind in ("collapse", "tab"):
                    self.hud_collapsed = not self.hud_collapsed
                    self.queue_redraw()
                    return True
                if kind != "hud":
                    apply_hud_action(self.game, hit)
                    self.queue_redraw()
                return True
            self.game.click(event.x, event.y, double=double)
            self.queue_redraw()
        return True

    def queue_redraw(self):
        self.game.dirty = True
        self.area.queue_draw()

    def set_hidden(self, hidden: bool):
        self.hidden = hidden
        self._shape_key = None
        self.queue_redraw()

    def toggle_hidden(self):
        self.set_hidden(not self.hidden)

    def refresh_workarea(self):
        wa = _workarea()
        self.move(wa.x, wa.y)
        self.resize(wa.width, wa.height)
        self.game.set_size(wa.width, wa.height)
        self.area.set_size_request(wa.width, wa.height)
        self._shape_key = None
        self._world_key = None
        self._world_surf = None
        self._world_boxes_rev = None
        self.queue_redraw()
