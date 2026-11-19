import os
import shutil
import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform
import yt_dlp


def get_download_dirs():
  if platform == "android":
    videos_dir = "/storage/emulated/0/Movies/ADNAN_Bhi"
    audios_dir = "/storage/emulated/0/Music/ADNAN_Bhi"
  else:
    base = os.path.join(os.path.expanduser("~"), "Downloads", "ADNAN_Bhi")
    videos_dir = os.path.join(base, "Videos")
    audios_dir = os.path.join(base, "Audios")
  os.makedirs(videos_dir, exist_ok=True)
  os.makedirs(audios_dir, exist_ok=True)
  return videos_dir, audios_dir


class AdnansDownloaderRoot(BoxLayout):

  def __init__(self, **kwargs):
    super().__init__(orientation="vertical", padding=14, spacing=10, **kwargs)
    self.video_dir, self.audio_dir = get_download_dirs()
    self.has_ffmpeg = shutil.which("ffmpeg") is not None
    self.active_tab = "Video"
    self.formats_data = {"Video": [], "Audio": []}
    self.is_busy = False

    self.add_widget(
        Label(
            text="ADNAN Bhi - Downloader",
            size_hint_y=None,
            height=44,
            bold=True,
            font_size="20sp",
        )
    )

    top_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
    self.url_input = TextInput(
        hint_text="Paste video or audio link here...",
        multiline=False,
        font_size="14sp",
    )
    self.start_btn = Button(
        text="Start",
        size_hint_x=0.28,
        background_color=(0.91, 0.12, 0.39, 1),
        on_press=lambda *_: self.fetch_formats(),
    )
    top_row.add_widget(self.url_input)
    top_row.add_widget(self.start_btn)
    self.add_widget(top_row)

    self.title_lbl = Label(
        text="No link loaded",
        size_hint_y=None,
        height=36,
        font_size="13sp",
    )
    self.add_widget(self.title_lbl)

    tab_row = BoxLayout(size_hint_y=None, height=42, spacing=8)
    self.video_tab_btn = Button(
        text="Video", on_press=lambda *_: self.switch_tab("Video")
    )
    self.audio_tab_btn = Button(
        text="Audio", on_press=lambda *_: self.switch_tab("Audio")
    )
    tab_row.add_widget(self.video_tab_btn)
    tab_row.add_widget(self.audio_tab_btn)
    self.add_widget(tab_row)

    scroll = ScrollView(do_scroll_x=False)
    self.list_box = BoxLayout(
        orientation="vertical", size_hint_y=None, spacing=6
    )
    self.list_box.bind(minimum_height=self.list_box.setter("height"))
    scroll.add_widget(self.list_box)
    self.add_widget(scroll)

    self.status_lbl = Label(
        text=f"Videos: {self.video_dir}",
        size_hint_y=None,
        height=38,
        font_size="11sp",
    )
    self.add_widget(self.status_lbl)

  def set_status(self, msg):
    Clock.schedule_once(lambda dt: setattr(self.status_lbl, "text", msg))

  def set_title(self, msg):
    Clock.schedule_once(lambda dt: setattr(self.title_lbl, "text", msg))

  def switch_tab(self, tab_name):
    self.active_tab = tab_name
    self.render_formats()

  def fetch_formats(self):
    if self.is_busy:
      return
    url = self.url_input.text.strip()
    if not url:
      self.set_status("Please paste a valid link.")
      return
    self.is_busy = True
    self.set_status("Loading formats...")
    threading.Thread(
        target=self._fetch_worker, args=(url,), daemon=True
    ).start()

  def _fetch_worker(self, url):
    try:
      with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
      title = info.get("title", "Media")
      heights = sorted(
          {
              f.get("height")
              for f in info.get("formats", [])
              if f.get("vcodec") != "none" and f.get("height")
          },
          reverse=True,
      )
      video_items = []
      for h in heights:
        if self.has_ffmpeg:
          fmt = f"bestvideo[height={h}]+bestaudio/best[height={h}]/best"
        else:
          fmt = f"best[height={h}][acodec!=none]/best[height<={h}][acodec!=none]/best[height={h}]"
        video_items.append({"label": f"{h}p MP4", "fmt": fmt, "is_audio": False})

      if not video_items:
        video_items.append(
            {"label": "Best Video", "fmt": "best", "is_audio": False}
        )

      audio_items = [
          {
              "label": "Audio (Best Quality)",
              "fmt": "bestaudio/best",
              "is_audio": True,
          },
      ]
      self.formats_data = {"Video": video_items, "Audio": audio_items}
      self.set_title(title)
      Clock.schedule_once(lambda dt: self._finish_fetch())
    except Exception as e:
      self.is_busy = False
      self.set_status(f"Error: {e}")

  def _finish_fetch(self):
    self.is_busy = False
    self.render_formats()
    self.set_status("Select a quality to download.")

  def render_formats(self):
    self.list_box.clear_widgets()
    items = self.formats_data.get(self.active_tab, [])
    for item in items:
      btn = Button(
          text=f"Download {item['label']}",
          size_hint_y=None,
          height=46,
          background_color=(0.18, 0.55, 0.34, 1),
          on_press=lambda _, it=item: self.start_download(it),
      )
      self.list_box.add_widget(btn)

  def start_download(self, item):
    if self.is_busy:
      return
    url = self.url_input.text.strip()
    if not url:
      self.set_status("Link is empty.")
      return
    self.url_input.text = ""
    self.is_busy = True
    self.set_status(f"Downloading {item['label']}...")
    threading.Thread(
        target=self._download_worker, args=(url, item), daemon=True
    ).start()

  def _download_worker(self, url, item):
    try:
      out_dir = self.audio_dir if item["is_audio"] else self.video_dir

      def hook(d):
        if d.get("status") == "downloading":
          pct = d.get("_percent_str", "").strip()
          self.set_status(f"Downloading: {pct}")

      opts = {
          "format": item["fmt"],
          "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
          "noplaylist": True,
          "progress_hooks": [hook],
      }
      if not item["is_audio"] and self.has_ffmpeg:
        opts["merge_output_format"] = "mp4"

      with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

      self.set_status(f"Saved in: {out_dir}")
    except Exception as e:
      self.set_status(f"Failed: {e}")
    finally:
      self.is_busy = False


class AdnansMobileApp(App):

  def build(self):
    if platform == "android":
      from android.permissions import Permission, request_permissions

      request_permissions([
          Permission.INTERNET,
          Permission.READ_EXTERNAL_STORAGE,
          Permission.WRITE_EXTERNAL_STORAGE,
      ])
    return AdnansDownloaderRoot()


if __name__ == "__main__":
  AdnansMobileApp().run()