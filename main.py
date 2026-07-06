from __future__ import annotations

import json
import os
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from ayson_core import VERSION, resolve_url


BG = (0.045, 0.047, 0.065, 1)
CARD = (0.085, 0.090, 0.125, 1)
CARD_2 = (0.105, 0.112, 0.155, 1)
BORDER = (0.210, 0.225, 0.300, 1)
ACCENT = (0.365, 0.455, 1.000, 1)
ACCENT_DARK = (0.270, 0.345, 0.800, 1)
TEXT = (0.945, 0.950, 0.980, 1)
MUTED = (0.620, 0.650, 0.730, 1)
SUCCESS = (0.220, 0.760, 0.520, 1)
ERROR = (1.000, 0.370, 0.370, 1)
WARNING = (1.000, 0.710, 0.250, 1)
HISTORY_LIMIT = 30


class RoundedBox(BoxLayout):
    bg_color = ListProperty(CARD)
    border_color = ListProperty(BORDER)
    radius = dp(18)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*self.border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(max(0, self.width - dp(2)), max(0, self.height - dp(2))),
                radius=[self.radius],
            )
        self.bind(pos=self._update_canvas, size=self._update_canvas, bg_color=self._update_canvas, border_color=self._update_canvas)

    def _update_canvas(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(max(0, self.width - dp(2)), max(0, self.height - dp(2))),
                radius=[self.radius],
            )


class PillButton(Button):
    bg_color = ListProperty(ACCENT)
    bg_down = ListProperty(ACCENT_DARK)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = TEXT
        self.bold = True
        self.font_size = dp(15)
        self.size_hint_y = None
        self.height = dp(52)
        with self.canvas.before:
            Color(*self.bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._update_canvas, size=self._update_canvas, state=self._update_canvas, bg_color=self._update_canvas)

    def _update_canvas(self, *_):
        color = self.bg_down if self.state == "down" else self.bg_color
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])


class GhostButton(PillButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = CARD_2
        self.bg_down = (0.145, 0.155, 0.205, 1)


class IconButton(GhostButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.width = dp(52)
        self.height = dp(48)
        self.text = ""
        self.bind(pos=self._draw_icon, size=self._draw_icon, state=self._draw_icon)
        self._draw_icon()

    def _draw_icon(self, *_):
        self.canvas.after.clear()
        x1 = self.x + self.width * 0.32
        x2 = self.x + self.width * 0.68
        ys = [self.center_y + dp(7), self.center_y, self.center_y - dp(7)]
        with self.canvas.after:
            Color(*TEXT)
            for y in ys:
                Line(points=[x1, y, x2, y], width=dp(1.6), cap="round")


class ModernInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = CARD_2
        self.foreground_color = TEXT
        self.hint_text_color = MUTED
        self.cursor_color = ACCENT
        self.selection_color = (0.365, 0.455, 1.0, 0.35)
        self.padding = [dp(16), dp(15), dp(16), dp(15)]
        self.font_size = dp(15)
        self.multiline = False
        self.size_hint_y = None
        self.height = dp(56)


class OutputBox(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = TEXT
        self.cursor_color = ACCENT
        self.hint_text_color = MUTED
        self.padding = [dp(14), dp(12), dp(14), dp(12)]
        self.font_size = dp(14)
        self.readonly = True
        self.multiline = True


class AysonApp(App):
    def build(self):
        self.title = "Ayson"
        self.is_solving = False
        self.last_result = ""
        self.history = self._load_history()

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(*BG)
            self._root_bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=self._update_root_bg, size=self._update_root_bg)

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(66), spacing=dp(10))
        title_box = BoxLayout(orientation="vertical")
        title = Label(
            text="Ayson",
            color=TEXT,
            bold=True,
            font_size=dp(34),
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        title_box.add_widget(title)
        menu_btn = IconButton()
        menu_btn.bind(on_press=self.show_history)
        header.add_widget(title_box)
        header.add_widget(menu_btn)

        card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(12), size_hint_y=None, height=dp(182))
        input_label = Label(
            text="Kisa linki yapistir",
            color=TEXT,
            bold=True,
            font_size=dp(15),
            halign="left",
            size_hint_y=None,
            height=dp(24),
        )
        input_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        self.input = ModernInput(
            hint_text="ay.live, aylink.co, cpmlink.pro, ouo.io veya bildirim.online",
        )

        buttons = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        self.solve_btn = PillButton(text="Coz")
        self.solve_btn.bind(on_press=self.on_solve)
        paste_btn = GhostButton(text="Yapistir")
        paste_btn.bind(on_press=self.on_paste)
        buttons.add_widget(self.solve_btn)
        buttons.add_widget(paste_btn)

        card.add_widget(input_label)
        card.add_widget(self.input)
        card.add_widget(buttons)

        result_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10), bg_color=(0.070, 0.075, 0.105, 1))
        result_top = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(36))
        self.status = Label(
            text="Hazir",
            color=SUCCESS,
            bold=True,
            font_size=dp(14),
            halign="left",
            valign="middle",
        )
        self.status.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.copy_btn = GhostButton(text="Kopyala", size_hint_x=None, width=dp(112), height=dp(36))
        self.copy_btn.font_size = dp(13)
        self.copy_btn.bind(on_press=self.on_copy)
        result_top.add_widget(self.status)
        result_top.add_widget(self.copy_btn)

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        self.output = OutputBox(text="Sonuc burada gorunecek.")
        scroll.add_widget(self.output)
        self.output.bind(minimum_height=self.output.setter("height"))

        result_card.add_widget(result_top)
        result_card.add_widget(scroll)

        footer = Label(
            text="Made By Black Corp.",
            color=MUTED,
            font_size=dp(12),
            bold=True,
            size_hint_y=None,
            height=dp(28),
            halign="center",
        )
        footer.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        root.add_widget(header)
        root.add_widget(card)
        root.add_widget(result_card)
        root.add_widget(footer)
        return root

    @property
    def history_path(self):
        return os.path.join(self.user_data_dir, "history.json")

    def _update_root_bg(self, root, *_):
        self._root_bg.pos = root.pos
        self._root_bg.size = root.size

    def set_status(self, text, color):
        self.status.text = text
        self.status.color = color

    def _load_history(self):
        try:
            path = os.path.join(self.user_data_dir, "history.json")
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[:HISTORY_LIMIT]
        except Exception:
            pass
        return []

    def _save_history(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history[:HISTORY_LIMIT], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _add_history(self, source, result):
        source = (source or "").strip()
        result = (result or "").strip()
        if not result:
            return
        item = {
            "source": source,
            "result": result,
            "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
        self.history = [h for h in self.history if h.get("result") != result]
        self.history.insert(0, item)
        self.history = self.history[:HISTORY_LIMIT]
        self._save_history()

    def on_paste(self, *_):
        try:
            text = Clipboard.paste().strip()
        except Exception:
            text = ""
        if text:
            self.input.text = text
            self.set_status("Yapistirildi", SUCCESS)
        else:
            self.set_status("Panoda link yok", WARNING)

    def on_solve(self, *_):
        if self.is_solving:
            return
        url = self.input.text.strip()
        if not url:
            self.output.text = "Link girmen lazim."
            self.set_status("Link bekleniyor", WARNING)
            return

        self.is_solving = True
        self.solve_btn.text = "Cozuluyor..."
        self.output.text = "Cozuluyor...\n\n" + url
        self.set_status("Cozuluyor", WARNING)

        thread = threading.Thread(target=self._solve_worker, args=(url,), daemon=True)
        thread.start()

    def _solve_worker(self, url):
        try:
            final = resolve_url(url)
            Clock.schedule_once(lambda _dt, source=url, result=final: self._show_success(source, result), 0)
        except BaseException as exc:
            message = str(exc) or exc.__class__.__name__
            Clock.schedule_once(lambda _dt, msg=message: self._show_error(msg), 0)

    def _show_success(self, source, final):
        self.is_solving = False
        self.solve_btn.text = "Coz"
        self.last_result = final.strip()
        self.output.text = self.last_result
        self.set_status("Cozuldu", SUCCESS)
        self._add_history(source, self.last_result)

    def _show_error(self, message):
        self.is_solving = False
        self.solve_btn.text = "Coz"
        self.last_result = ""
        self.output.text = "Hata:\n" + message + "\n\nSurum:\n" + VERSION
        self.set_status("Hata", ERROR)

    def on_copy(self, *_):
        text = self.last_result or self.output.text.strip()
        if not text or text.startswith("Hata") or "Sonuc burada" in text or text.startswith("Cozuluyor"):
            self.set_status("Kopyalanacak sonuc yok", WARNING)
            return
        Clipboard.copy(text)
        self.set_status("Kopyalandi", SUCCESS)

    def show_history(self, *_):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        title = Label(text="Gecmis", color=TEXT, bold=True, font_size=dp(20), halign="left", valign="middle")
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        close_btn = GhostButton(text="Kapat", size_hint_x=None, width=dp(92), height=dp(40))
        close_btn.font_size = dp(13)
        top.add_widget(title)
        top.add_widget(close_btn)
        content.add_widget(top)

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        items = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        items.bind(minimum_height=items.setter("height"))

        if not self.history:
            empty = Label(
                text="Henuz gecmis yok.",
                color=MUTED,
                font_size=dp(14),
                size_hint_y=None,
                height=dp(80),
                halign="center",
                valign="middle",
            )
            empty.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            items.add_widget(empty)
        else:
            for h in self.history:
                items.add_widget(self._history_item(h))

        scroll.add_widget(items)
        content.add_widget(scroll)

        popup = Popup(
            title="",
            content=content,
            size_hint=(0.92, 0.82),
            background_color=(0.045, 0.047, 0.065, 1),
            separator_height=0,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def _history_item(self, item):
        box = RoundedBox(orientation="vertical", padding=dp(10), spacing=dp(8), size_hint_y=None, height=dp(152), bg_color=(0.070, 0.075, 0.105, 1))

        time_label = Label(
            text=item.get("time", ""),
            color=MUTED,
            font_size=dp(11),
            size_hint_y=None,
            height=dp(18),
            halign="left",
        )
        time_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        source_label = Label(
            text=self._shorten(item.get("source", ""), 78),
            color=MUTED,
            font_size=dp(11),
            size_hint_y=None,
            height=dp(18),
            halign="left",
        )
        source_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        result = TextInput(
            text=item.get("result", ""),
            readonly=True,
            multiline=True,
            background_normal="",
            background_active="",
            background_color=CARD_2,
            foreground_color=TEXT,
            cursor_color=ACCENT,
            padding=[dp(8), dp(6), dp(8), dp(6)],
            font_size=dp(12),
            size_hint_y=None,
            height=dp(54),
        )

        actions = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(34))
        copy_btn = GhostButton(text="Kopyala", height=dp(34))
        copy_btn.font_size = dp(12)
        use_btn = PillButton(text="Ac", height=dp(34))
        use_btn.font_size = dp(12)
        copy_btn.bind(on_press=lambda *_: self._copy_history(item.get("result", "")))
        use_btn.bind(on_press=lambda *_: self._use_history(item.get("source", ""), item.get("result", "")))
        actions.add_widget(copy_btn)
        actions.add_widget(use_btn)

        box.add_widget(time_label)
        box.add_widget(source_label)
        box.add_widget(result)
        box.add_widget(actions)
        return box

    def _copy_history(self, result):
        if result:
            Clipboard.copy(result)
            self.set_status("Gecmisten kopyalandi", SUCCESS)

    def _use_history(self, source, result):
        if source:
            self.input.text = source
        if result:
            self.last_result = result
            self.output.text = result
            self.set_status("Gecmisten acildi", SUCCESS)

    def _shorten(self, text, limit):
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)] + "..."


if __name__ == "__main__":
    AysonApp().run()
