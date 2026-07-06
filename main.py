from __future__ import annotations

import threading
import webbrowser
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

try:
    from android.runnable import run_on_ui_thread  # type: ignore
    from jnius import PythonJavaClass, autoclass, java_method  # type: ignore
except Exception:
    run_on_ui_thread = None
    PythonJavaClass = object
    autoclass = None

    def java_method(*_args, **_kwargs):
        def deco(func):
            return func
        return deco

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
DANGER = (0.900, 0.250, 0.250, 1)

HISTORY_LIMIT = 50

SHORTENER_HOSTS = {
    "ay.live", "aylink.co", "cpmlink.co", "cpmlink.pro",
    "bildirim.online", "bildirim.vip", "ouo.io", "ouo.press",
    "lnk.news", "tulink.fun", "bit.ly", "bitly.com", "tinyurl.com",
    "is.gd", "v.gd", "t.co", "lnkd.in", "goo.gl", "ow.ly",
    "buff.ly", "rebrand.ly", "rb.gy", "shorturl.at", "cutt.ly",
    "s.id", "tiny.cc", "short.io", "adf.ly", "bc.vc", "shorte.st",
    "clk.sh", "shrinke.me", "exe.io", "exey.io", "fc.lc",
    "fc-lc.xyz", "linkvertise.com",
}


def simple_host(url):
    try:
        import urllib.parse
        h = urllib.parse.urlparse(url or "").hostname or ""
        h = h.lower()
        if h.startswith("www."):
            h = h[4:]
        return h
    except Exception:
        return ""


def looks_like_final_url(url):
    h = simple_host(url)
    if not h:
        return False
    if h in SHORTENER_HOSTS:
        return False
    low = (url or "").lower()
    bad = ("captcha", "challenge", "cloudflare", "turnstile", "recaptcha")
    if any(x in low for x in bad):
        return False
    return url.startswith("http://") or url.startswith("https://")


class AndroidClickListener(PythonJavaClass):
    __javainterfaces__ = ["android/view/View$OnClickListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @java_method("(Landroid/view/View;)V")
    def onClick(self, view):
        try:
            self.callback()
        except Exception:
            pass


class RoundedBox(BoxLayout):
    bg_color = ListProperty(CARD)
    border_color = ListProperty(BORDER)
    radius_value = dp(18)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*self.border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_value])
            Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(max(0, self.width - dp(2)), max(0, self.height - dp(2))),
                radius=[self.radius_value],
            )
        self.bind(pos=self._update_canvas, size=self._update_canvas, bg_color=self._update_canvas, border_color=self._update_canvas)

    def _update_canvas(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius_value])
            Color(*self.bg_color)
            self._rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(max(0, self.width - dp(2)), max(0, self.height - dp(2))),
                radius=[self.radius_value],
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


class DangerButton(GhostButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = (0.170, 0.095, 0.115, 1)
        self.bg_down = (0.240, 0.110, 0.130, 1)


class MenuButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text = ""
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.size_hint = (None, None)
        self.size = (dp(52), dp(52))
        with self.canvas.before:
            Color(*CARD_2)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        with self.canvas.after:
            Color(*TEXT)
            self._l1 = Line(points=[], width=dp(1.8))
            self._l2 = Line(points=[], width=dp(1.8))
            self._l3 = Line(points=[], width=dp(1.8))
        self.bind(pos=self._update_canvas, size=self._update_canvas, state=self._update_canvas)

    def _update_canvas(self, *_):
        self.canvas.before.clear()
        color = (0.145, 0.155, 0.205, 1) if self.state == "down" else CARD_2
        with self.canvas.before:
            Color(*color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        cx1 = self.x + dp(16)
        cx2 = self.right - dp(16)
        y_mid = self.center_y
        self._l1.points = [cx1, y_mid + dp(8), cx2, y_mid + dp(8)]
        self._l2.points = [cx1, y_mid, cx2, y_mid]
        self._l3.points = [cx1, y_mid - dp(8), cx2, y_mid - dp(8)]


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
        self.icon = "icon.png"
        self.is_solving = False
        self.last_result = ""
        self.last_input = ""
        self.open_target = ""
        self.history = []
        self.history_query = ""
        self.web_overlay = None
        self.webview = None
        self.webview_target = ""
        self._web_poll_event = None
        self.store = JsonStore("ayson_history.json")
        self._load_history()

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with root.canvas.before:
            Color(*BG)
            root._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(
            pos=lambda w, *_: setattr(w._bg, "pos", w.pos),
            size=lambda w, *_: setattr(w._bg, "size", w.size),
        )

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(62), spacing=dp(12))

        title_box = BoxLayout(orientation="vertical", spacing=dp(1))
        title = Label(
            text="Ayson",
            color=TEXT,
            bold=True,
            font_size=dp(31),
            halign="left",
            valign="middle",
            size_hint_y=1,
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        title_box.add_widget(title)

        menu = MenuButton()
        menu.bind(on_release=lambda *_: self.show_history())

        header.add_widget(title_box)
        header.add_widget(menu)
        root.add_widget(header)

        card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(12), size_hint_y=None, height=dp(190))
        self.url_input = ModernInput(hint_text="Linki buraya yapıştır")
        card.add_widget(self.url_input)

        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        self.solve_btn = PillButton(text="Çöz")
        paste_btn = GhostButton(text="Yapıştır")
        self.solve_btn.bind(on_release=lambda *_: self.solve())
        paste_btn.bind(on_release=lambda *_: self.paste_clipboard())
        row.add_widget(self.solve_btn)
        row.add_widget(paste_btn)
        card.add_widget(row)

        self.status_label = Label(
            text="Hazır",
            color=MUTED,
            font_size=dp(13),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(24),
        )
        self.status_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        card.add_widget(self.status_label)
        root.add_widget(card)

        result_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10))
        result_top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        result_title = Label(
            text="Sonuç",
            color=TEXT,
            bold=True,
            font_size=dp(17),
            halign="left",
            valign="middle",
        )
        result_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        result_top.add_widget(result_title)
        result_card.add_widget(result_top)

        out_wrap = RoundedBox(orientation="vertical", bg_color=(0.060, 0.064, 0.090, 1), border_color=(0.130, 0.145, 0.200, 1))
        self.output = OutputBox(hint_text="Çözülen link burada görünür")
        out_wrap.add_widget(self.output)
        result_card.add_widget(out_wrap)

        action_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        copy_btn = GhostButton(text="Kopyala")
        self.open_btn = GhostButton(text="Aç")
        self.inner_open_btn = GhostButton(text="İç Aç")
        copy_btn.bind(on_release=lambda *_: self.copy_result())
        self.open_btn.bind(on_release=lambda *_: self.open_current())
        self.inner_open_btn.bind(on_release=lambda *_: self.open_current_inside())
        action_row.add_widget(copy_btn)
        action_row.add_widget(self.open_btn)
        action_row.add_widget(self.inner_open_btn)
        result_card.add_widget(action_row)

        root.add_widget(result_card)

        footer = Label(
            text="Made By Black Corp.",
            color=MUTED,
            font_size=dp(12),
            size_hint_y=None,
            height=dp(24),
            halign="center",
            valign="middle",
        )
        footer.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        root.add_widget(footer)

        self.root = root
        Clock.schedule_once(lambda *_: self.read_shared_text(), 0.7)
        return root

    def set_status(self, text, color=MUTED):
        self.status_label.text = text
        self.status_label.color = color

    def paste_clipboard(self):
        try:
            self.url_input.text = Clipboard.paste() or ""
            self.set_status("Panodan alındı", SUCCESS)
        except Exception:
            self.set_status("Pano okunamadı", ERROR)

    def copy_result(self):
        text = (self.output.text or "").strip()
        if not text:
            self.set_status("Kopyalanacak sonuç yok", WARNING)
            return
        try:
            Clipboard.copy(text)
            self.set_status("Kopyalandı", SUCCESS)
        except Exception:
            self.set_status("Kopyalanamadı", ERROR)

    def open_current(self):
        target = self.open_target or self.last_result or self.last_input or (self.url_input.text or "").strip()
        if not target:
            self.set_status("Açılacak link yok", WARNING)
            return
        try:
            webbrowser.open(target)
            self.set_status("Tarayıcıda açılıyor", SUCCESS)
        except Exception:
            self.set_status("Tarayıcı açılamadı", ERROR)

    def open_current_inside(self):
        target = self.open_target or self.last_result or self.last_input or (self.url_input.text or "").strip()
        if not target:
            self.set_status("İçeride açılacak link yok", WARNING)
            return
        self.open_webview(target)
        def solve(self):
        if self.is_solving:
            return

        url = (self.url_input.text or "").strip()
        if not url:
            self.set_status("Önce link gir", WARNING)
            return

        self.is_solving = True
        self.solve_btn.disabled = True
        self.last_input = url
        self.last_result = ""
        self.open_target = url
        self.output.text = ""
        self.set_status("Çözülüyor...", ACCENT)

        threading.Thread(target=self._solve_thread, args=(url,), daemon=True).start()

    def _solve_thread(self, url):
        try:
            result = resolve_url(url)
            Clock.schedule_once(lambda *_: self._solve_success(url, result), 0)
        except Exception as exc:
            msg = str(exc)
            Clock.schedule_once(lambda *_: self._solve_error(url, msg), 0)

    def _solve_success(self, input_url, result):
        self.is_solving = False
        self.solve_btn.disabled = False

        result = (result or "").strip()
        self.last_result = result
        self.open_target = result or input_url

        self.output.text = result
        self.set_status("Çözüldü", SUCCESS)

        try:
            Clipboard.copy(result)
        except Exception:
            pass

        self._add_history(
            input_url=input_url,
            result_url=result,
            status="success",
            note="Çözüldü",
        )

    def _solve_error(self, input_url, msg):
        self.is_solving = False
        self.solve_btn.disabled = False

        self.last_result = ""
        self.open_target = input_url

        clean_msg = msg or "Bilinmeyen hata"

        if self._is_manual_needed(clean_msg):
            text = (
                "Bu link CAPTCHA/dogrulama istiyor.\n\n"
                "Uygulama yanlis link vermedi. Tarayicida veya ic tarayicida acip devam edebilirsin.\n\n"
                f"{input_url}"
            )
            self.output.text = text
            self.set_status("Manuel doğrulama gerekli", WARNING)
            self._add_history(
                input_url=input_url,
                result_url=input_url,
                status="manual",
                note="Manuel doğrulama gerekli",
            )
        else:
            self.output.text = "Hata:\n" + clean_msg + "\n\nSurum:\n" + VERSION
            self.set_status("Hata", ERROR)
            self._add_history(
                input_url=input_url,
                result_url=input_url,
                status="error",
                note=clean_msg[:180],
            )

    def _is_manual_needed(self, msg):
        low = (msg or "").lower()
        markers = (
            "captcha",
            "doğrulama",
            "dogrulama",
            "anti-bot",
            "turnstile",
            "cloudflare",
            "i'm a human",
            "human",
            "tarayıcıda aç",
            "tarayicida ac",
            "koruma",
        )
        return any(x in low for x in markers)

    def _load_history(self):
        try:
            if self.store.exists("items"):
                self.history = self.store.get("items").get("data", [])
            else:
                self.history = []
        except Exception:
            self.history = []

    def _save_history(self):
        try:
            self.store.put("items", data=self.history[:HISTORY_LIMIT])
        except Exception:
            pass

    def _add_history(self, input_url, result_url, status="success", note=""):
        if not input_url and not result_url:
            return

        item = {
            "input": input_url or "",
            "result": result_url or "",
            "status": status or "",
            "note": note or "",
            "tag": "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        # Aynı sonucu tekrar en üste taşı
        new_history = []
        for old in self.history:
            if old.get("input") == item["input"] and old.get("result") == item["result"]:
                item["tag"] = old.get("tag", "")
                continue
            new_history.append(old)

        self.history = [item] + new_history
        self.history = self.history[:HISTORY_LIMIT]
        self._save_history()

    def read_shared_text(self):
        if autoclass is None:
            return

        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            activity = PythonActivity.mActivity
            intent = activity.getIntent()

            if intent is None:
                return

            action = intent.getAction()
            shared_text = ""

            if action == Intent.ACTION_SEND:
                shared_text = intent.getStringExtra(Intent.EXTRA_TEXT) or ""
            elif action == Intent.ACTION_VIEW:
                data = intent.getData()
                if data:
                    shared_text = data.toString()

            shared_text = (shared_text or "").strip()
            if shared_text.startswith("http://") or shared_text.startswith("https://"):
                self.url_input.text = shared_text
                self.set_status("Paylaşılan link alındı", SUCCESS)
        except Exception:
            pass

    def show_history(self):
        popup_root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        with popup_root.canvas.before:
            Color(*BG)
            popup_root._bg = RoundedRectangle(pos=popup_root.pos, size=popup_root.size, radius=[dp(18)])
        popup_root.bind(
            pos=lambda w, *_: setattr(w._bg, "pos", w.pos),
            size=lambda w, *_: setattr(w._bg, "size", w.size),
        )

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(10))

        title = Label(
            text="Geçmiş",
            color=TEXT,
            bold=True,
            font_size=dp(22),
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        close_btn = GhostButton(text="Kapat")
        close_btn.size_hint_x = None
        close_btn.width = dp(100)

        top.add_widget(title)
        top.add_widget(close_btn)
        popup_root.add_widget(top)

        search = ModernInput(hint_text="Geçmişte ara / etiket ara")
        search.height = dp(52)
        popup_root.add_widget(search)

        scroll = ScrollView()
        list_box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        list_box.bind(minimum_height=list_box.setter("height"))
        scroll.add_widget(list_box)
        popup_root.add_widget(scroll)

        popup = Popup(
            title="",
            content=popup_root,
            size_hint=(0.94, 0.88),
            background="",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )

        close_btn.bind(on_release=lambda *_: popup.dismiss())

        def refresh(*_):
            q = (search.text or "").strip().lower()
            list_box.clear_widgets()

            items = self.history or []
            if q:
                filtered = []
                for item in items:
                    hay = " ".join(
                        [
                            item.get("input", ""),
                            item.get("result", ""),
                            item.get("status", ""),
                            item.get("note", ""),
                            item.get("tag", ""),
                            item.get("date", ""),
                        ]
                    ).lower()
                    if q in hay:
                        filtered.append(item)
                items = filtered

            if not items:
                empty = Label(
                    text="Geçmiş boş",
                    color=MUTED,
                    font_size=dp(15),
                    size_hint_y=None,
                    height=dp(80),
                )
                list_box.add_widget(empty)
                return

            for index, item in enumerate(items):
                list_box.add_widget(self._history_card(item, popup, refresh))

        search.bind(text=refresh)
        refresh()
        
        popup.open()
            def _history_card(self, item, popup, refresh_callback):
        card = RoundedBox(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8),
            size_hint_y=None,
            height=dp(178),
            bg_color=CARD,
            border_color=BORDER,
        )

        status = item.get("status", "")
        tag = item.get("tag", "")
        date = item.get("date", "")

        status_text = "Başarılı" if status == "success" else "Manuel" if status == "manual" else "Hata"
        status_color = SUCCESS if status == "success" else WARNING if status == "manual" else ERROR

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(24), spacing=dp(8))

        status_lbl = Label(
            text=status_text,
            color=status_color,
            bold=True,
            font_size=dp(13),
            halign="left",
            valign="middle",
        )
        status_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        date_lbl = Label(
            text=date,
            color=MUTED,
            font_size=dp(12),
            halign="right",
            valign="middle",
            size_hint_x=None,
            width=dp(130),
        )
        date_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        top.add_widget(status_lbl)
        top.add_widget(date_lbl)
        card.add_widget(top)

        result = item.get("result", "") or item.get("input", "")
        input_url = item.get("input", "")

        link_lbl = Label(
            text=result,
            color=TEXT,
            font_size=dp(12),
            halign="left",
            valign="top",
            shorten=True,
            shorten_from="middle",
            size_hint_y=None,
            height=dp(38),
        )
        link_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        card.add_widget(link_lbl)

        meta_text = "Kaynak: " + input_url
        if tag:
            meta_text += "\nEtiket: " + tag

        meta_lbl = Label(
            text=meta_text,
            color=MUTED,
            font_size=dp(11),
            halign="left",
            valign="top",
            shorten=True,
            shorten_from="middle",
            size_hint_y=None,
            height=dp(38),
        )
        meta_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        card.add_widget(meta_lbl)

        row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42))

        open_btn = GhostButton(text="Aç")
        copy_btn = GhostButton(text="Kopyala")
        inside_btn = GhostButton(text="İç Aç")
        tag_btn = GhostButton(text="Etiket")
        del_btn = DangerButton(text="Sil")

        for b in (open_btn, copy_btn, inside_btn, tag_btn, del_btn):
            b.font_size = dp(11)
            b.height = dp(42)

        open_btn.bind(on_release=lambda *_: self._open_history_item(item))
        copy_btn.bind(on_release=lambda *_: self._copy_history_item(item))
        inside_btn.bind(on_release=lambda *_: self.open_webview(item.get("result", "") or item.get("input", "")))
        tag_btn.bind(on_release=lambda *_: self._edit_tag(item, refresh_callback))
        del_btn.bind(on_release=lambda *_: self._delete_history_item(item, refresh_callback))

        row.add_widget(open_btn)
        row.add_widget(copy_btn)
        row.add_widget(inside_btn)
        row.add_widget(tag_btn)
        row.add_widget(del_btn)

        card.add_widget(row)
        return card

    def _open_history_item(self, item):
        target = item.get("result", "") or item.get("input", "")
        if not target:
            return
        try:
            webbrowser.open(target)
        except Exception:
            pass

    def _copy_history_item(self, item):
        target = item.get("result", "") or item.get("input", "")
        if not target:
            return
        try:
            Clipboard.copy(target)
            self.set_status("Geçmiş linki kopyalandı", SUCCESS)
        except Exception:
            self.set_status("Kopyalanamadı", ERROR)

    def _delete_history_item(self, item, refresh_callback=None):
        self.history = [
            old for old in self.history
            if not (
                old.get("input") == item.get("input")
                and old.get("result") == item.get("result")
                and old.get("date") == item.get("date")
            )
        ]
        self._save_history()
        if refresh_callback:
            refresh_callback()

    def _edit_tag(self, item, refresh_callback=None):
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))

        title = Label(
            text="Etiket ekle / düzenle",
            color=TEXT,
            bold=True,
            font_size=dp(19),
            size_hint_y=None,
            height=dp(34),
        )
        root.add_widget(title)

        inp = ModernInput(hint_text="Örn: film, oyun, önemli")
        inp.text = item.get("tag", "")
        root.add_widget(inp)

        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))

        save_btn = PillButton(text="Kaydet")
        clear_btn = GhostButton(text="Sil")
        cancel_btn = GhostButton(text="İptal")

        row.add_widget(save_btn)
        row.add_widget(clear_btn)
        row.add_widget(cancel_btn)
        root.add_widget(row)

        popup = Popup(
            title="",
            content=root,
            size_hint=(0.88, None),
            height=dp(190),
            background="",
            background_color=(0.04, 0.045, 0.065, 1),
            separator_height=0,
        )

        def apply_tag(value):
            for old in self.history:
                if (
                    old.get("input") == item.get("input")
                    and old.get("result") == item.get("result")
                    and old.get("date") == item.get("date")
                ):
                    old["tag"] = value
                    item["tag"] = value
                    break
            self._save_history()
            popup.dismiss()
            if refresh_callback:
                refresh_callback()

        save_btn.bind(on_release=lambda *_: apply_tag((inp.text or "").strip()))
        clear_btn.bind(on_release=lambda *_: apply_tag(""))
        cancel_btn.bind(on_release=lambda *_: popup.dismiss())

        popup.open()

    def open_webview(self, url):
        url = (url or "").strip()
        if not url:
            self.set_status("İçeride açılacak link yok", WARNING)
            return

        if autoclass is None or run_on_ui_thread is None:
            self.set_status("İç Aç sadece Android APK içinde çalışır", ERROR)
            try:
                webbrowser.open(url)
            except Exception:
                pass
            return

        self.webview_target = url
        self.set_status("İç tarayıcı açılıyor", ACCENT)
        self._show_web_overlay()
        self._android_open_webview(url)

    def _show_web_overlay(self):
        if self.web_overlay is not None:
            return

        overlay = BoxLayout(orientation="vertical", spacing=dp(0))
        with overlay.canvas.before:
            Color(*BG)
            overlay._bg = RoundedRectangle(pos=overlay.pos, size=overlay.size, radius=[0])
        overlay.bind(
            pos=lambda w, *_: setattr(w._bg, "pos", w.pos),
            size=lambda w, *_: setattr(w._bg, "size", w.size),
        )

        top = BoxLayout(
            orientation="horizontal",
            padding=[dp(10), dp(8), dp(10), dp(8)],
            spacing=dp(8),
            size_hint_y=None,
            height=dp(66),
        )

        close_btn = GhostButton(text="Kapat")
        capture_btn = PillButton(text="Yakala")
        open_external_btn = GhostButton(text="Tarayıcı")

        close_btn.bind(on_release=lambda *_: self.close_webview())
        capture_btn.bind(on_release=lambda *_: self.capture_webview_url())
        open_external_btn.bind(on_release=lambda *_: self.open_webview_external())

        top.add_widget(close_btn)
        top.add_widget(capture_btn)
        top.add_widget(open_external_btn)

        self.web_status = Label(
            text="Sayfa yükleniyor...",
            color=MUTED,
            font_size=dp(12),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(34),
            padding=[dp(12), 0],
        )
        self.web_status.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        placeholder = Label(
            text="Android WebView alanı\n\nYeşil bar / doğrulama / Linke Git işlemlerini burada manuel yap.",
            color=MUTED,
            font_size=dp(15),
            halign="center",
            valign="middle",
        )
        placeholder.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))

        overlay.add_widget(top)
        overlay.add_widget(self.web_status)
        overlay.add_widget(placeholder)

        self.web_overlay = overlay
        self.root.clear_widgets()
        self.root.add_widget(overlay)
            @run_on_ui_thread if run_on_ui_thread else (lambda f: f)
    def _android_open_webview(self, url):
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            WebView = autoclass("android.webkit.WebView")
            WebViewClient = autoclass("android.webkit.WebViewClient")
            WebSettings = autoclass("android.webkit.WebSettings")
            LinearLayout = autoclass("android.widget.LinearLayout")
            ViewGroup = autoclass("android.view.ViewGroup")

            activity = PythonActivity.mActivity

            if self.webview is not None:
                try:
                    self.webview.destroy()
                except Exception:
                    pass
                self.webview = None

            webview = WebView(activity)
            self.webview = webview

            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setLoadWithOverviewMode(True)
            settings.setUseWideViewPort(True)
            settings.setSupportZoom(True)
            settings.setBuiltInZoomControls(False)
            settings.setCacheMode(WebSettings.LOAD_DEFAULT)
            settings.setUserAgentString(
                "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
            )

            webview.setWebViewClient(WebViewClient())

            params = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
            )

            activity.addContentView(webview, params)
            webview.loadUrl(url)

            if self._web_poll_event:
                self._web_poll_event.cancel()
            self._web_poll_event = Clock.schedule_interval(lambda *_: self._poll_webview_url(), 1.0)

        except Exception as exc:
            self.set_status("WebView açılamadı: " + str(exc), ERROR)
            try:
                webbrowser.open(url)
            except Exception:
                pass

    def _poll_webview_url(self):
        if self.webview is None:
            return False

        try:
            current = self._get_webview_url()
            if current:
                self.webview_target = current
                if hasattr(self, "web_status"):
                    self.web_status.text = current

                # Final linke gelmiş gibi görünüyorsa otomatik yakala.
                if looks_like_final_url(current):
                    self._capture_url_value(current, auto=True)
        except Exception:
            pass

        return True

    def _get_webview_url(self):
        if self.webview is None:
            return ""

        result = {"url": ""}

        if run_on_ui_thread is None:
            return ""

        @run_on_ui_thread
        def read_url():
            try:
                result["url"] = self.webview.getUrl() or ""
            except Exception:
                result["url"] = ""

        read_url()
        return result.get("url", "")

    def capture_webview_url(self):
        current = self._get_webview_url() or self.webview_target
        if not current:
            self.set_status("Yakalanacak URL yok", WARNING)
            return

        self._capture_url_value(current, auto=False)

    def _capture_url_value(self, url, auto=False):
        url = (url or "").strip()
        if not url:
            return

        self.last_result = url
        self.open_target = url
        self.output.text = url

        try:
            Clipboard.copy(url)
        except Exception:
            pass

        status = "success" if looks_like_final_url(url) else "manual"
        note = "WebView final yakalandı" if status == "success" else "WebView URL yakalandı"

        self._add_history(
            input_url=self.last_input or self.url_input.text or url,
            result_url=url,
            status=status,
            note=note,
        )

        if auto:
            self.set_status("Final URL otomatik yakalandı", SUCCESS)
        else:
            self.set_status("URL yakalandı", SUCCESS)

    def open_webview_external(self):
        target = self.webview_target or self.open_target or self.last_input
        if not target:
            self.set_status("Açılacak link yok", WARNING)
            return
        try:
            webbrowser.open(target)
            self.set_status("Tarayıcıda açılıyor", SUCCESS)
        except Exception:
            self.set_status("Tarayıcı açılamadı", ERROR)

    def close_webview(self):
        if self._web_poll_event:
            self._web_poll_event.cancel()
            self._web_poll_event = None

        if self.webview is not None and run_on_ui_thread is not None:
            self._android_close_webview()
        else:
            self.webview = None

        self.web_overlay = None
        self.root.clear_widgets()
        self.root.add_widget(self._rebuild_main_screen())

    @run_on_ui_thread if run_on_ui_thread else (lambda f: f)
    def _android_close_webview(self):
        try:
            if self.webview is not None:
                parent = self.webview.getParent()
                if parent is not None:
                    parent.removeView(self.webview)
                self.webview.destroy()
        except Exception:
            pass
        self.webview = None

    def _rebuild_main_screen(self):
        # WebView kapatınca uygulamayı yeniden oluşturmak yerine mevcut ana ekranı tekrar kuruyoruz.
        # En temiz yol: build() içindeki root'u yeniden üretmek.
        old_input = self.url_input.text if hasattr(self, "url_input") else ""
        old_output = self.output.text if hasattr(self, "output") else ""
        old_status = self.status_label.text if hasattr(self, "status_label") else "Hazır"

        new_root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
        with new_root.canvas.before:
            Color(*BG)
            new_root._bg = RoundedRectangle(pos=new_root.pos, size=new_root.size, radius=[0])
        new_root.bind(
            pos=lambda w, *_: setattr(w._bg, "pos", w.pos),
            size=lambda w, *_: setattr(w._bg, "size", w.size),
        )

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(62), spacing=dp(12))

        title_box = BoxLayout(orientation="vertical", spacing=dp(1))
        title = Label(
            text="Ayson",
            color=TEXT,
            bold=True,
            font_size=dp(31),
            halign="left",
            valign="middle",
            size_hint_y=1,
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        title_box.add_widget(title)

        menu = MenuButton()
        menu.bind(on_release=lambda *_: self.show_history())

        header.add_widget(title_box)
        header.add_widget(menu)
        new_root.add_widget(header)

        card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(12), size_hint_y=None, height=dp(190))
        self.url_input = ModernInput(hint_text="Linki buraya yapıştır")
        self.url_input.text = old_input
        card.add_widget(self.url_input)

        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        self.solve_btn = PillButton(text="Çöz")
        paste_btn = GhostButton(text="Yapıştır")
        self.solve_btn.bind(on_release=lambda *_: self.solve())
        paste_btn.bind(on_release=lambda *_: self.paste_clipboard())
        row.add_widget(self.solve_btn)
        row.add_widget(paste_btn)
        card.add_widget(row)

        self.status_label = Label(
            text=old_status,
            color=MUTED,
            font_size=dp(13),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(24),
        )
        self.status_label.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        card.add_widget(self.status_label)
        new_root.add_widget(card)

        result_card = RoundedBox(orientation="vertical", padding=dp(14), spacing=dp(10))
        result_top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30))
        result_title = Label(
            text="Sonuç",
            color=TEXT,
            bold=True,
            font_size=dp(17),
            halign="left",
            valign="middle",
        )
        result_title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        result_top.add_widget(result_title)
        result_card.add_widget(result_top)

        out_wrap = RoundedBox(
            orientation="vertical",
            bg_color=(0.060, 0.064, 0.090, 1),
            border_color=(0.130, 0.145, 0.200, 1),
        )
        self.output = OutputBox(hint_text="Çözülen link burada görünür")
        self.output.text = old_output
        out_wrap.add_widget(self.output)
        result_card.add_widget(out_wrap)

        action_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(52))
        copy_btn = GhostButton(text="Kopyala")
        self.open_btn = GhostButton(text="Aç")
        self.inner_open_btn = GhostButton(text="İç Aç")
        copy_btn.bind(on_release=lambda *_: self.copy_result())
        self.open_btn.bind(on_release=lambda *_: self.open_current())
        self.inner_open_btn.bind(on_release=lambda *_: self.open_current_inside())
        action_row.add_widget(copy_btn)
        action_row.add_widget(self.open_btn)
        action_row.add_widget(self.inner_open_btn)
        result_card.add_widget(action_row)

        new_root.add_widget(result_card)

        footer = Label(
            text="Made By Black Corp.",
            color=MUTED,
            font_size=dp(12),
            size_hint_y=None,
            height=dp(24),
            halign="center",
            valign="middle",
        )
        footer.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        new_root.add_widget(footer)

        self.root = new_root
        return new_root


if __name__ == "__main__":
    AysonApp().run()
