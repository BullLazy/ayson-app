from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from ayson_core import resolve_url, VERSION


class AysonApp(App):
    def build(self):
        self.title = "Ayson"

        root = BoxLayout(
            orientation="vertical",
            padding=18,
            spacing=12
        )

        title = Label(
            text="Ayson Link Çözücü\n" + VERSION,
            size_hint_y=None,
            height=72,
            font_size=20
        )

        self.input = TextInput(
            hint_text="ay.live, ouo.io veya bildirim.online linkini yapıştır",
            multiline=False,
            size_hint_y=None,
            height=54
        )

        solve_btn = Button(
            text="Çöz",
            size_hint_y=None,
            height=56
        )
        solve_btn.bind(on_press=self.on_solve)

        copy_btn = Button(
            text="Sonucu Kopyala",
            size_hint_y=None,
            height=56
        )
        copy_btn.bind(on_press=self.on_copy)

        self.output = TextInput(
            text="Sonuç burada görünecek.",
            readonly=True,
            multiline=True
        )

        root.add_widget(title)
        root.add_widget(self.input)
        root.add_widget(solve_btn)
        root.add_widget(copy_btn)
        root.add_widget(self.output)

        return root

    def on_solve(self, *_):
        url = self.input.text.strip()

        if not url:
            self.output.text = "Link girmen lazım."
            return

        self.output.text = "Çözülüyor...\n" + VERSION

        def work(_dt):
            try:
                final = resolve_url(url)
                self.output.text = final
            except Exception as e:
                self.output.text = "Hata:\n" + str(e) + "\n\nSürüm:\n" + VERSION

        Clock.schedule_once(work, 0.1)

    def on_copy(self, *_):
        text = self.output.text.strip()

        if text and not text.startswith("Hata") and "Sonuç burada" not in text:
            Clipboard.copy(text)
            self.output.text = text + "\n\nKopyalandı."


if __name__ == "__main__":
    AysonApp().run()
