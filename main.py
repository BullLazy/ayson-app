from __future__ import annotations

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
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

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(*BG)
            self._root_bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=self._update_root_bg, size=self._update_root_bg)

        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(86), spacing=dp(4))
        title = Label(
            text="Ayson",
            color=TEXT,
            bold=True,
            font_size=dp(30),
            halign="left",
            valign="bottom",
            size_hint_y=None,
            height=dp(42),
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        subtitle = Label(
            text=f"Modern link resolver  •  {VERSION}",
            color=MUTED,
            font_size=dp(13),
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(28),
        )
        subtitle.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        header.add_widget(title)
        header.add_widget(subtitle)

        card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(12), size_hint_y=None, height=dp(220))
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
        card.add_widget(Label(text="Destek: ay.live / aylink / cpmlink / bildirim / ouo", color=MUTED, font_size=dp(12), size_hint_y=None, height=dp(22)))

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
            text="Not: CAPTCHA cikarsa uygulama yanlis link vermez, hata gosterir.",
            color=MUTED,
            font_size=dp(12),
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

    def _update_root_bg(self, root, *_):
        self._root_bg.pos = root.pos
        self._root_bg.size = root.size

    def set_status(self, text, color):
        self.status.text = text
        self.status.color = color

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
            Clock.schedule_once(lambda *_: self._show_success(final), 0)
        except Exception as exc:
            Clock.schedule_once(lambda *_: self._show_error(str(exc)), 0)

    def _show_success(self, final):
        self.is_solving = False
        self.solve_btn.text = "Coz"
        self.last_result = final.strip()
        self.output.text = self.last_result
        self.set_status("Cozuldu", SUCCESS)

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


if __name__ == "__main__":
    AysonApp().run()
