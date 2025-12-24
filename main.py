import discord
from discord.ext import commands
from discord.ext import tasks
import os
import hashlib
import io
import json
import random
import requests
from datetime import datetime
import time
import threading

# --- 設定 ---
TOKEN = os.getenv("DISCORD_TOKEN", "")

API_URL = "https://spla3.yuu26.com/api/schedule"
SALMON_API_URL = "https://spla3.yuu26.com/api/coop-grouping/schedule"
TEAM_CONTEST_API_URL = "https://spla3.yuu26.com/api/coop-grouping-team-contest/schedule"
EVENT_API_URL = "https://spla3.yuu26.com/api/event/schedule"
FEST_API_URL = "https://spla3.yuu26.com/api/fest/schedule"
GEAR_API_URL = "https://splatoon3.ink/data/gear.json"
COOP_API_URL = "https://splatoon3.ink/data/coop.json"
FESTIVALS_API_URL = "https://splatoon3.ink/data/festivals.json"
XRANK_API_URL = "https://splatoon3.ink/data/xrank/xrank.takoroka.json"
LOCALE_API_URL = "https://splatoon3.ink/data/locale/ja-JP.json"
USER_AGENT = "DiscordBot_SplaStageInfo (Contact: chihalu)" # 連絡先を記載

# Botの基本設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

IMG_DIR = os.path.join(os.path.dirname(__file__), "img")
WEAPON_IMG_DIR = os.path.join(os.path.dirname(__file__), "img", "武器")
FONT_PATH = os.path.join(os.path.dirname(__file__), "BlitzBold.otf")
KANJI_FONT_PATH = os.path.join(os.path.dirname(__file__), "FOT-KurokaneStd-EB.otf")
NAMEPLATE_DIR = os.path.join(os.path.dirname(__file__), "img", "ネームプレート")
STATE_PATH = os.path.join(os.path.dirname(__file__), ".bot_state.json")
GEAR_NOTIFY_STATE_PATH = os.path.join(os.path.dirname(__file__), ".gear_notify_state.json")
LOCK_DIR = os.path.join(os.path.dirname(__file__), ".locks")
STAGE_NOTIFY_CHANNEL_ID = int(os.getenv("STAGE_NOTIFY_CHANNEL_ID", "0") or "0")
STAGE_NOTIFY_ON_START = (os.getenv("STAGE_NOTIFY_ON_START", "0") == "1")
EVENT_NOTIFY_CHANNEL_ID = int(os.getenv("EVENT_NOTIFY_CHANNEL_ID", "0") or "0")
EVENT_NOTIFY_ON_START = (os.getenv("EVENT_NOTIFY_ON_START", "0") == "1")
SALMON_NOTIFY_CHANNEL_ID = int(os.getenv("SALMON_NOTIFY_CHANNEL_ID", "0") or "0")
SALMON_NOTIFY_ON_START = (os.getenv("SALMON_NOTIFY_ON_START", "0") == "1")
TEAM_CONTEST_NOTIFY_CHANNEL_ID = int(os.getenv("TEAM_CONTEST_NOTIFY_CHANNEL_ID", "0") or "0")
TEAM_CONTEST_NOTIFY_ON_START = (os.getenv("TEAM_CONTEST_NOTIFY_ON_START", "0") == "1")
FEST_NOTIFY_CHANNEL_ID = int(os.getenv("FEST_NOTIFY_CHANNEL_ID", "0") or "0")
FEST_NOTIFY_ON_START = (os.getenv("FEST_NOTIFY_ON_START", "0") == "1")
GEAR_NOTIFY_CHANNEL_ID = int(os.getenv("GEAR_NOTIFY_CHANNEL_ID", "0") or "0")
GEAR_NOTIFY_ON_START = (os.getenv("GEAR_NOTIFY_ON_START", "0") == "1")
XRANK_NOTIFY_CHANNEL_ID = int(os.getenv("XRANK_NOTIFY_CHANNEL_ID", "0") or "0")
COOP_MONTHLY_NOTIFY_CHANNEL_ID = int(os.getenv("COOP_MONTHLY_NOTIFY_CHANNEL_ID", "0") or "0")
BOT_ACTIVITY_NAME = os.getenv("BOT_ACTIVITY_NAME", "Splatoon")

_LOCALE_CACHE: dict | None = None
_NAMEPLATE_CACHE: list[str] | None = None


def _nameplate_paths() -> list[str]:
    global _NAMEPLATE_CACHE
    if _NAMEPLATE_CACHE is not None:
        return _NAMEPLATE_CACHE
    try:
        files = os.listdir(NAMEPLATE_DIR)
    except Exception:
        _NAMEPLATE_CACHE = []
        return _NAMEPLATE_CACHE
    paths = []
    for name in files:
        if name.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
            paths.append(os.path.join(NAMEPLATE_DIR, name))
    _NAMEPLATE_CACHE = paths
    return _NAMEPLATE_CACHE

def _load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def _save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

_STATE_LOCK = threading.Lock()

def _update_state(updates: dict) -> None:
    if not updates:
        return
    with _STATE_LOCK:
        state = _load_state()
        state.update(updates)
        _save_state(state)

def _load_gear_notify_state() -> dict:
    try:
        with open(GEAR_NOTIFY_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def _save_gear_notify_state(state: dict) -> None:
    try:
        with open(GEAR_NOTIFY_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving gear notify state: {e}")

def _update_gear_notify_state(updates: dict) -> None:
    if not updates:
        return
    with _STATE_LOCK:
        state = _load_gear_notify_state()
        state.update(updates)
        _save_gear_notify_state(state)

def _acquire_lock(name: str, ttl_seconds: int = 120) -> bool:
    try:
        os.makedirs(LOCK_DIR, exist_ok=True)
    except Exception:
        return False

    path = os.path.join(LOCK_DIR, f"{name}.lock")
    now = time.time()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(str(now))
        return True
    except FileExistsError:
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            return False
        if now - mtime > ttl_seconds:
            try:
                os.remove(path)
            except Exception:
                return False
            return _acquire_lock(name, ttl_seconds=ttl_seconds)
        return False
    except Exception:
        return False

def _release_lock(name: str) -> None:
    path = os.path.join(LOCK_DIR, f"{name}.lock")
    try:
        os.remove(path)
    except Exception:
        pass

async def _get_text_channel(channel_id: int) -> discord.abc.Messageable | None:
    if not channel_id:
        return None
    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception:
            return None
    return ch

def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"Error loading .env: {e}")

def get_stages():
    """APIから現在のステージ情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_salmon_schedule():
    """APIからサーモンランのスケジュール情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(SALMON_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_team_contest_schedule():
    """APIからバイトチームコンテストのスケジュール情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(TEAM_CONTEST_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_event_schedule():
    """APIからイベントマッチのスケジュール情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(EVENT_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_fest_schedule():
    """APIからフェスのスケジュール情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(FEST_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_gear_data():
    """APIからゲソタウンのギア情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(GEAR_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_coop_data():
    """APIからサーモンランのリザルト情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(COOP_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_festivals_data():
    """APIからフェス情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(FESTIVALS_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_xrank_data():
    """APIからXランキング情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(XRANK_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_locale_data():
    """APIから日本語ロケール情報を取得する"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(LOCALE_API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def _format_hhmm(iso_datetime: str) -> str:
    return _parse_iso_datetime(iso_datetime).astimezone().strftime("%H:%M")

def _parse_iso_datetime(iso_datetime: str) -> datetime:
    s = iso_datetime or ""
    # datetime.fromisoformat() は "Z" を直接解釈できないため吸収する
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

def _format_mmdd_hhmm(iso_datetime: str) -> str:
    return _parse_iso_datetime(iso_datetime).astimezone().strftime("%m/%d %H:%M")

def _format_rule(rule) -> str:
    if isinstance(rule, dict):
        return rule.get("name") or "不明"
    if isinstance(rule, str):
        return rule
    return "不明"

def _extract_stage_names(stages) -> list[str]:
    if not isinstance(stages, list):
        return ["不明", "不明"]

    names: list[str] = []
    for stage in stages:
        if isinstance(stage, dict):
            names.append(stage.get("name") or "不明")
        elif isinstance(stage, str):
            names.append(stage)
        else:
            names.append("不明")

    if not names:
        names = ["不明", "不明"]

    return names

def _format_stages(stages) -> str:
    return " / ".join(_extract_stage_names(stages))

def _find_local_image_by_name(name: str) -> str | None:
    if not name or name == "不明":
        return None

    for ext in (".webp", ".png", ".jpg", ".jpeg", ".gif"):
        path = os.path.join(IMG_DIR, f"{name}{ext}")
        if os.path.exists(path):
            return path

    return None

def _find_weapon_image_by_name(name: str) -> str | None:
    if not name or name == "不明":
        return None
    if not os.path.isdir(WEAPON_IMG_DIR):
        return None

    for ext in (".png", ".webp", ".jpg", ".jpeg", ".gif"):
        path = os.path.join(WEAPON_IMG_DIR, f"{name}{ext}")
        if os.path.exists(path):
            return path

    return None

def _safe_attachment_filename(path: str, prefix: str) -> str:
    _, ext = os.path.splitext(path)
    digest = hashlib.md5(path.encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}{ext or ''}"

def _find_local_rule_icon(rule_name: str) -> str | None:
    if not rule_name or rule_name == "不明":
        return None

    for ext in (".png", ".webp", ".jpg", ".jpeg", ".gif", ".svg"):
        path = os.path.join(IMG_DIR, f"{rule_name}{ext}")
        if os.path.exists(path):
            return path

    return None

def _find_local_mode_icon(mode_key: str) -> str | None:
    mode_to_name = {
        "regular": "ナワバリバトル",
        "bankara_challenge": "バンカラマッチ",
        "bankara_open": "バンカラマッチ",
        "x": "Xマッチ",
    }

    name = mode_to_name.get(mode_key)
    if not name:
        return None

    for ext in (".png", ".webp", ".jpg", ".jpeg", ".gif"):
        path = os.path.join(IMG_DIR, f"{name}{ext}")
        if os.path.exists(path):
            return path

    return None

def _render_stage_card_bytes(
    rule_name: str,
    rule_icon_path: str | None,
    stage1_name: str,
    stage1_path: str | None,
    stage2_name: str,
    stage2_path: str | None,
) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None

    def open_image(path: str):
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        if ext == ".svg":
            try:
                import cairosvg  # type: ignore
            except Exception:
                return None
            png_bytes = cairosvg.svg2png(url=path)
            return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        return Image.open(path).convert("RGBA")

    def load_font(size: int):
        for candidate in (
            FONT_PATH,
            r"C:\Windows\Fonts\meiryo.ttc",
            r"C:\Windows\Fonts\YuGothR.ttc",
            r"C:\Windows\Fonts\msgothic.ttc",
        ):
            if os.path.exists(candidate):
                try:
                    return ImageFont.truetype(candidate, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def is_kanji(ch: str) -> bool:
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
            or 0x20000 <= code <= 0x2A6DF
            or 0x2A700 <= code <= 0x2B73F
            or 0x2B740 <= code <= 0x2B81F
            or 0x2B820 <= code <= 0x2CEAF
        )

    def _font_metrics(font) -> tuple[int, int]:
        try:
            return font.getmetrics()
        except Exception:
            return (0, 0)

    def measure_text(text: str, base_font, kanji_font) -> tuple[int, int]:
        total_w = 0
        max_ascent = 0
        max_descent = 0
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            bbox = tmp_draw.textbbox((0, 0), ch, font=font)
            total_w += bbox[2] - bbox[0]
            ascent, descent = _font_metrics(font)
            if ascent > max_ascent:
                max_ascent = ascent
            if descent > max_descent:
                max_descent = descent
        return total_w, max_ascent + max_descent

    def draw_text_with_kanji_font(draw, pos: tuple[int, int], text: str, base_font, kanji_font, **kwargs):
        x, y = pos
        base_ascent, _ = _font_metrics(base_font)
        kanji_ascent, _ = _font_metrics(kanji_font)
        max_ascent = max(base_ascent, kanji_ascent)
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            ascent, _ = _font_metrics(font)
            draw.text((x, y + (max_ascent - ascent)), ch, font=font, **kwargs)
            bbox = draw.textbbox((0, 0), ch, font=font)
            x += bbox[2] - bbox[0]

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def is_kanji(ch: str) -> bool:
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
            or 0x20000 <= code <= 0x2A6DF
            or 0x2A700 <= code <= 0x2B73F
            or 0x2B740 <= code <= 0x2B81F
            or 0x2B820 <= code <= 0x2CEAF
        )

    def _font_metrics(font) -> tuple[int, int]:
        try:
            return font.getmetrics()
        except Exception:
            return (0, 0)

    def measure_text(text: str, base_font, kanji_font) -> tuple[int, int]:
        total_w = 0
        max_ascent = 0
        max_descent = 0
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            bbox = tmp_draw.textbbox((0, 0), ch, font=font)
            total_w += bbox[2] - bbox[0]
            ascent, descent = _font_metrics(font)
            if ascent > max_ascent:
                max_ascent = ascent
            if descent > max_descent:
                max_descent = descent
        return total_w, max_ascent + max_descent

    def draw_text_with_kanji_font(draw, pos: tuple[int, int], text: str, base_font, kanji_font, **kwargs):
        x, y = pos
        base_ascent, _ = _font_metrics(base_font)
        kanji_ascent, _ = _font_metrics(kanji_font)
        max_ascent = max(base_ascent, kanji_ascent)
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            ascent, _ = _font_metrics(font)
            draw.text((x, y + (max_ascent - ascent)), ch, font=font, **kwargs)
            bbox = draw.textbbox((0, 0), ch, font=font)
            x += bbox[2] - bbox[0]

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    def is_kanji(ch: str) -> bool:
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
            or 0x20000 <= code <= 0x2A6DF
            or 0x2A700 <= code <= 0x2B73F
            or 0x2B740 <= code <= 0x2B81F
            or 0x2B820 <= code <= 0x2CEAF
        )

    def _font_metrics(font) -> tuple[int, int]:
        try:
            return font.getmetrics()
        except Exception:
            return (0, 0)

    def measure_text(text: str, base_font, kanji_font) -> tuple[int, int]:
        total_w = 0
        max_ascent = 0
        max_descent = 0
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            bbox = tmp_draw.textbbox((0, 0), ch, font=font)
            total_w += bbox[2] - bbox[0]
            ascent, descent = _font_metrics(font)
            if ascent > max_ascent:
                max_ascent = ascent
            if descent > max_descent:
                max_descent = descent
        return total_w, max_ascent + max_descent

    def draw_text_with_kanji_font(draw, pos: tuple[int, int], text: str, base_font, kanji_font, **kwargs):
        x, y = pos
        base_ascent, _ = _font_metrics(base_font)
        kanji_ascent, _ = _font_metrics(kanji_font)
        max_ascent = max(base_ascent, kanji_ascent)
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            ascent, _ = _font_metrics(font)
            draw.text((x, y + (max_ascent - ascent)), ch, font=font, **kwargs)
            bbox = draw.textbbox((0, 0), ch, font=font)
            x += bbox[2] - bbox[0]

    # Discord のEmbed内では横幅に合わせて縮小されるため、縦横比を大きめにして見やすくする
    card_w = 1000
    card_h = 520
    pad = 20
    gap = 16
    header_h = 64
    corner_r = 18

    bg = (25, 32, 44, 255)
    card = Image.new("RGBA", (card_w, card_h), bg)
    draw = ImageDraw.Draw(card)

    # header (rule icon + name)
    icon_size = 40
    icon_x = pad
    icon_y = pad + 6

    icon_img = None
    if rule_icon_path:
        icon_img = open_image(rule_icon_path)

    if icon_img:
        icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        # subtle shadow behind the icon for contrast
        try:
            from PIL import ImageFilter  # type: ignore

            shadow = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            shadow.alpha_composite(icon_img)
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2))
            card.alpha_composite(shadow, (icon_x + 1, icon_y + 2))
        except Exception:
            pass
        card.alpha_composite(icon_img, (icon_x, icon_y))
    else:
        badge_r = icon_size // 2
        badge_cx = icon_x + badge_r
        badge_cy = icon_y + badge_r
        badge_box = (badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r)
        draw.ellipse(badge_box, fill=(255, 196, 0, 255))

    title_font = load_font(30)
    title_kanji_font = load_kanji_font(30)
    draw_text_with_kanji_font(
        draw,
        (icon_x + icon_size + 14, pad + 10),
        rule_name,
        title_font,
        title_kanji_font,
        fill=(255, 255, 255, 255),
    )

    # stage panels
    panel_top = pad + header_h
    panel_h = card_h - panel_top - pad
    panel_w = (card_w - pad * 2 - gap) // 2

    def rounded_panel(x: int, y: int, w: int, h: int):
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(panel)
        pdraw.rounded_rectangle((0, 0, w, h), radius=corner_r, fill=(18, 24, 33, 255))
        return panel

    def paste_cover(target: Image.Image, img: Image.Image, box_xywh: tuple[int, int, int, int]):
        x, y, w, h = box_xywh
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        cropped = resized.crop((left, top, left + w, top + h))
        target.alpha_composite(cropped, (x, y))

    def draw_stage_label(x: int, y: int, w: int, h: int, text: str):
        label_h = 46
        overlay = Image.new("RGBA", (w, label_h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rounded_rectangle((0, 0, w, label_h), radius=12, fill=(0, 0, 0, 120))
        font = load_font(26)
        kanji_font = load_kanji_font(26)
        # center text
        tw, th = measure_text(text, font, kanji_font)
        draw_text_with_kanji_font(
            odraw,
            ((w - tw) // 2, (label_h - th) // 2 - 1),
            text,
            font,
            kanji_font,
            fill=(255, 255, 255, 255),
        )
        card.alpha_composite(overlay, (x, y + h - label_h - 8))

    # Left stage
    left_x = pad
    right_x = pad + panel_w + gap

    for x, stage_name, stage_path in (
        (left_x, stage1_name, stage1_path),
        (right_x, stage2_name, stage2_path),
    ):
        panel = rounded_panel(0, 0, panel_w, panel_h)
        if stage_path:
            img = open_image(stage_path)
            if img:
                paste_cover(panel, img, (0, 0, panel_w, panel_h))
        card.alpha_composite(panel, (x, panel_top))
        if stage_name and stage_name != "不明":
            draw_stage_label(x, panel_top, panel_w, panel_h, stage_name)

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()

def _render_salmon_stage_with_weapons_bytes(stage_path: str | None, weapon_names: list[str]) -> bytes | None:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        return None

    if not stage_path:
        return None

    icon_paths = []
    for name in weapon_names:
        if name == "不明":
            continue
        if name == "ランダム":
            icon_path = _find_weapon_image_by_name("ランダム")
        else:
            icon_path = _find_weapon_image_by_name(name)
        if icon_path:
            icon_paths.append(icon_path)

    if not icon_paths:
        return None

    try:
        stage_img = Image.open(stage_path).convert("RGBA")
    except Exception:
        return None

    target_w = 1000
    target_h = 520
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 255))

    iw, ih = stage_img.size
    scale = max(target_w / iw, target_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = stage_img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))
    canvas.alpha_composite(cropped, (0, 0))

    bar_h = 150
    overlay = Image.new("RGBA", (target_w, bar_h), (0, 0, 0, 166))
    canvas.alpha_composite(overlay, (0, target_h - bar_h))

    max_icons = 4
    icons = icon_paths[:max_icons]
    icon_size = 110
    gap = 18
    total_w = len(icons) * icon_size + (len(icons) - 1) * gap
    start_x = (target_w - total_w) // 2
    y = target_h - bar_h + (bar_h - icon_size) // 2

    for idx, path in enumerate(icons):
        try:
            icon = Image.open(path).convert("RGBA")
        except Exception:
            continue
        iw, ih = icon.size
        scale = min(icon_size / iw, icon_size / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        icon = icon.resize((nw, nh), Image.Resampling.LANCZOS)
        x = start_x + idx * (icon_size + gap) + (icon_size - nw) // 2
        y2 = y + (icon_size - nh) // 2
        canvas.alpha_composite(icon, (x, y2))

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()

def _render_gear_collage_bytes(items: list[dict], title: str) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None

    if not items:
        return None

    def load_font(size: int):
        for candidate in (
            FONT_PATH,
            r"C:\Windows\Fonts\meiryo.ttc",
            r"C:\Windows\Fonts\YuGothR.ttc",
            r"C:\Windows\Fonts\msgothic.ttc",
        ):
            if os.path.exists(candidate):
                try:
                    return ImageFont.truetype(candidate, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def load_kanji_font(size: int):
        if os.path.exists(KANJI_FONT_PATH):
            try:
                return ImageFont.truetype(KANJI_FONT_PATH, size=size)
            except Exception:
                pass
        return load_font(size)

    cols = 3
    rows = (len(items) + cols - 1) // cols
    card_w = 1000
    card_h = 520
    pad = 24
    gap = 16
    header_h = 60
    cell_w = (card_w - pad * 2 - gap * (cols - 1)) // cols
    cell_h = (card_h - pad * 2 - header_h - gap * (rows - 1)) // rows

    bg = (20, 24, 34, 255)
    card = Image.new("RGBA", (card_w, card_h), bg)
    draw = ImageDraw.Draw(card)

    def fetch_image(url: str) -> Image.Image | None:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        except Exception:
            return None

    logo_cache: dict[str, Image.Image] = {}
    nameplate_cache: dict[str, Image.Image] = {}
    nameplate_paths = _nameplate_paths()

    def fetch_logo(path: str) -> Image.Image | None:
        if not path:
            return None
        cached = logo_cache.get(path)
        if cached is not None:
            return cached
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None
        logo_cache[path] = img
        return img

    def fetch_nameplate(path: str) -> Image.Image | None:
        if not path:
            return None
        cached = nameplate_cache.get(path)
        if cached is not None:
            return cached
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None
        nameplate_cache[path] = img
        return img

    def is_kanji(ch: str) -> bool:
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
            or 0x20000 <= code <= 0x2A6DF
            or 0x2A700 <= code <= 0x2B73F
            or 0x2B740 <= code <= 0x2B81F
            or 0x2B820 <= code <= 0x2CEAF
        )

    def _font_metrics(font) -> tuple[int, int]:
        try:
            return font.getmetrics()
        except Exception:
            return (0, 0)

    def measure_text(text: str, base_font, kanji_font) -> tuple[int, int]:
        total_w = 0
        max_ascent = 0
        max_descent = 0
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            bbox = tmp_draw.textbbox((0, 0), ch, font=font)
            total_w += bbox[2] - bbox[0]
            ascent, descent = _font_metrics(font)
            if ascent > max_ascent:
                max_ascent = ascent
            if descent > max_descent:
                max_descent = descent
        return total_w, max_ascent + max_descent

    def draw_text_with_kanji_font(draw, pos: tuple[int, int], text: str, base_font, kanji_font, **kwargs):
        x, y = pos
        base_ascent, _ = _font_metrics(base_font)
        kanji_ascent, _ = _font_metrics(kanji_font)
        max_ascent = max(base_ascent, kanji_ascent)
        for ch in text:
            font = kanji_font if is_kanji(ch) else base_font
            ascent, _ = _font_metrics(font)
            draw.text((x, y + (max_ascent - ascent)), ch, font=font, **kwargs)
            bbox = draw.textbbox((0, 0), ch, font=font)
            x += bbox[2] - bbox[0]

    title_font = load_font(28)
    title_kanji_font = load_kanji_font(28)
    draw_text_with_kanji_font(
        draw,
        (pad, pad + 6),
        title,
        title_font,
        title_kanji_font,
        fill=(255, 255, 255, 255),
    )

    def paste_cover(target: Image.Image, img: Image.Image, x: int, y: int, w: int, h: int):
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        cropped = resized.crop((left, top, left + w, top + h))
        target.alpha_composite(cropped, (x, y))

    def paste_logo(target: Image.Image, logo: Image.Image, pad_px: int = 10):
        tw, th = target.size
        lw, lh = logo.size
        max_size = int(min(tw, th) * 0.22)
        if max_size <= 0:
            return
        scale = min(max_size / lw, max_size / lh)
        nw, nh = max(1, int(lw * scale)), max(1, int(lh * scale))
        resized = logo.resize((nw, nh), Image.Resampling.LANCZOS)
        target.alpha_composite(resized, (tw - nw - pad_px, pad_px))

    label_font_size = 20
    label_font = load_font(label_font_size)
    label_h = 34

    for idx, item in enumerate(items):
        row = idx // cols
        col = idx % cols
        x = pad + col * (cell_w + gap)
        y = pad + header_h + row * (cell_h + gap)

        label_h_eff = label_h
        plate_x = 0
        plate_y = cell_h - label_h
        plate_w = cell_w
        plate_h = label_h
        plate_img = None
        if nameplate_paths:
            plate_path = random.choice(nameplate_paths)
            plate = fetch_nameplate(plate_path)
            if plate:
                plate_w, plate_h = plate.size
                scale = min(cell_w / plate_w, cell_h / plate_h, 1.0)
                if scale < 1.0:
                    plate = plate.resize(
                        (max(1, int(plate_w * scale)), max(1, int(plate_h * scale))),
                        Image.Resampling.LANCZOS,
                    )
                    plate_w, plate_h = plate.size
                plate_x = (cell_w - plate_w) // 2
                plate_y = cell_h - plate_h
                plate_img = plate
        if plate_img is not None:
            label_h_eff = plate_h
        else:
            label_h_eff = label_h
            plate_w = cell_w
            plate_h = label_h
        image_h = max(1, cell_h - label_h_eff)
        label_y = image_h

        panel = Image.new("RGBA", (cell_w, cell_h), (10, 12, 18, 255))
        img = fetch_image(item.get("image_url") or "")
        if img:
            paste_cover(panel, img, 0, 0, cell_w, image_h)
        logo_path = item.get("brand_logo_path") or ""
        if logo_path:
            logo = fetch_logo(logo_path)
            if logo:
                paste_logo(panel, logo)

        if plate_img is not None:
            panel.paste(plate_img, (plate_x, label_y), plate_img)
        else:
            overlay = Image.new("RGBA", (cell_w, label_h), (0, 0, 0, 160))
            panel.alpha_composite(overlay, (plate_x, label_y))
        odraw = ImageDraw.Draw(panel)
        name = item.get("name") or "不明"
        max_w = max(10, plate_w - 12)
        font = label_font
        kanji_font = load_kanji_font(label_font_size)
        for size in range(label_font_size, 11, -2):
            font = load_font(size)
            kanji_font = load_kanji_font(size)
            tw, _ = measure_text(name, font, kanji_font)
            if tw <= max_w:
                break
        else:
            tw = max_w + 1
        if tw > max_w:
            truncated = name
            while truncated:
                truncated = truncated[:-1]
                test = f"{truncated}..."
                tw, _ = measure_text(test, font, kanji_font)
                if tw <= max_w:
                    name = test
                    break
        tw, th = measure_text(name, font, kanji_font)
        text_x = plate_x + (plate_w - tw) // 2
        text_y = label_y + (label_h_eff - th) // 2 - 1
        draw_text_with_kanji_font(
            odraw,
            (text_x, text_y),
            name,
            font,
            kanji_font,
            fill=(20, 20, 20, 255),
            stroke_width=2,
            stroke_fill=(255, 255, 255, 220),
        )

        card.alpha_composite(panel, (x, y))

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()

def _render_gear_collage_sections_bytes(sections: list[tuple[str, list[dict]]]) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None

    sections = [(title, items) for title, items in sections if items]
    if not sections:
        return None

    def load_font(size: int):
        for candidate in (
            FONT_PATH,
            r"C:\Windows\Fonts\meiryo.ttc",
            r"C:\Windows\Fonts\YuGothR.ttc",
            r"C:\Windows\Fonts\msgothic.ttc",
        ):
            if os.path.exists(candidate):
                try:
                    return ImageFont.truetype(candidate, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def fetch_image(url: str) -> Image.Image | None:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        except Exception:
            return None

    logo_cache: dict[str, Image.Image] = {}
    nameplate_cache: dict[str, Image.Image] = {}
    nameplate_paths = _nameplate_paths()

    def fetch_logo(path: str) -> Image.Image | None:
        if not path:
            return None
        cached = logo_cache.get(path)
        if cached is not None:
            return cached
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None
        logo_cache[path] = img
        return img

    def fetch_nameplate(path: str) -> Image.Image | None:
        if not path:
            return None
        cached = nameplate_cache.get(path)
        if cached is not None:
            return cached
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return None
        nameplate_cache[path] = img
        return img

    def paste_cover(target: Image.Image, img: Image.Image, x: int, y: int, w: int, h: int):
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - w) // 2
        top = (nh - h) // 2
        cropped = resized.crop((left, top, left + w, top + h))
        target.alpha_composite(cropped, (x, y))

    def paste_logo(target: Image.Image, logo: Image.Image, pad_px: int = 10):
        tw, th = target.size
        lw, lh = logo.size
        max_size = int(min(tw, th) * 0.22)
        if max_size <= 0:
            return
        scale = min(max_size / lw, max_size / lh)
        nw, nh = max(1, int(lw * scale)), max(1, int(lh * scale))
        resized = logo.resize((nw, nh), Image.Resampling.LANCZOS)
        target.alpha_composite(resized, (tw - nw - pad_px, pad_px))

    card_w = 1000
    card_h = 900
    pad = 24
    gap = 16
    section_gap = 28
    header_h = 46
    cols = 3

    bg = (20, 24, 34, 255)
    card = Image.new("RGBA", (card_w, card_h), bg)
    draw = ImageDraw.Draw(card)
    title_font = load_font(26)
    title_kanji_font = load_kanji_font(26)
    label_font_size = 20
    label_font = load_font(label_font_size)
    label_h = 34

    y_cursor = pad
    for title, items in sections:
        draw_text_with_kanji_font(
            draw,
            (pad, y_cursor + 2),
            title,
            title_font,
            title_kanji_font,
            fill=(255, 255, 255, 255),
        )
        y_cursor += header_h

        rows = (len(items) + cols - 1) // cols
        cell_w = (card_w - pad * 2 - gap * (cols - 1)) // cols
        cell_h = 220

        for idx, item in enumerate(items):
            row = idx // cols
            col = idx % cols
            x = pad + col * (cell_w + gap)
            y = y_cursor + row * (cell_h + gap)

            label_h_eff = label_h
            plate_x = 0
            plate_y = cell_h - label_h
            plate_w = cell_w
            plate_h = label_h
            plate_img = None
            if nameplate_paths:
                plate_path = random.choice(nameplate_paths)
                plate = fetch_nameplate(plate_path)
                if plate:
                    plate_w, plate_h = plate.size
                    scale = min(cell_w / plate_w, cell_h / plate_h, 1.0)
                    if scale < 1.0:
                        plate = plate.resize(
                            (max(1, int(plate_w * scale)), max(1, int(plate_h * scale))),
                            Image.Resampling.LANCZOS,
                        )
                        plate_w, plate_h = plate.size
                    plate_x = (cell_w - plate_w) // 2
                    plate_y = cell_h - plate_h
                    plate_img = plate
            if plate_img is not None:
                label_h_eff = plate_h
            else:
                label_h_eff = label_h
                plate_w = cell_w
                plate_h = label_h
            image_h = max(1, cell_h - label_h_eff)
            label_y = image_h

            panel = Image.new("RGBA", (cell_w, cell_h), (10, 12, 18, 255))
            img = fetch_image(item.get("image_url") or "")
            if img:
                paste_cover(panel, img, 0, 0, cell_w, image_h)
            logo_path = item.get("brand_logo_path") or ""
            if logo_path:
                logo = fetch_logo(logo_path)
                if logo:
                    paste_logo(panel, logo)

            if plate_img is not None:
                panel.paste(plate_img, (plate_x, label_y), plate_img)
            else:
                overlay = Image.new("RGBA", (cell_w, label_h), (0, 0, 0, 160))
                panel.alpha_composite(overlay, (plate_x, label_y))
            odraw = ImageDraw.Draw(panel)
            name = item.get("name") or "不明"
            max_w = max(10, plate_w - 12)
            font = label_font
            kanji_font = load_kanji_font(label_font_size)
            for size in range(label_font_size, 11, -2):
                font = load_font(size)
                kanji_font = load_kanji_font(size)
                tw, _ = measure_text(name, font, kanji_font)
                if tw <= max_w:
                    break
            else:
                tw = max_w + 1
            if tw > max_w:
                truncated = name
                while truncated:
                    truncated = truncated[:-1]
                    test = f"{truncated}..."
                    tw, _ = measure_text(test, font, kanji_font)
                    if tw <= max_w:
                        name = test
                        break
            tw, th = measure_text(name, font, kanji_font)
            text_x = plate_x + (plate_w - tw) // 2
            text_y = label_y + (label_h_eff - th) // 2 - 1
            draw_text_with_kanji_font(
                odraw,
                (text_x, text_y),
                name,
                font,
                kanji_font,
                fill=(20, 20, 20, 255),
                stroke_width=2,
                stroke_fill=(255, 255, 255, 220),
            )

            card.alpha_composite(panel, (x, y))

        y_cursor += rows * (cell_h + gap) - gap + section_gap

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()

def _build_mode_embeds(result: dict, schedule_index: int, title_prefix: str) -> tuple[list[discord.Embed], list[discord.File]]:
    # 取得したいモードのリスト
    modes = {
        "regular": "ナワバリバトル",
        "bankara_challenge": "バンカラマッチ (チャレンジ)",
        "bankara_open": "バンカラマッチ (オープン)",
        "x": "Xマッチ"
    }

    mode_colors = {
        "regular": 0x19FF19,  # green
        "bankara_challenge": 0xFF3B30,  # red
        "bankara_open": 0xFF3B30,  # red
        "x": 0x33CCFF,  # light blue
    }

    embeds: list[discord.Embed] = []
    files_by_name: dict[str, discord.File] = {}

    for key, name in modes.items():
        color = mode_colors.get(key, 0x19FF19)
        mode_icon_path = _find_local_mode_icon(key)
        mode_data = result.get(key, [])
        if len(mode_data) <= schedule_index:
            embed = discord.Embed(title=f"【{name}】", description="情報がありません。", color=color)
            if mode_icon_path:
                filename = _safe_attachment_filename(mode_icon_path, prefix="mode")
                embed.set_thumbnail(url=f"attachment://{filename}")
                if filename not in files_by_name:
                    files_by_name[filename] = discord.File(mode_icon_path, filename=filename)
            embeds.append(embed)
            continue

        item = mode_data[schedule_index]
        rule = _format_rule(item.get("rule"))
        stage_names = _extract_stage_names(item.get("stages"))
        stage1_name = stage_names[0] if len(stage_names) > 0 else "不明"
        stage2_name = stage_names[1] if len(stage_names) > 1 else "不明"
        start_time = _format_hhmm(item["start_time"])
        end_time = _format_hhmm(item["end_time"])

        embed = discord.Embed(title=f"【{name}】", color=color)
        embed.add_field(name="時間", value=f"{start_time}～{end_time}", inline=True)
        embed.add_field(name="ルール", value=f"**{rule}**", inline=True)
        embed.add_field(name="ステージ", value=f"1. {stage1_name}\n2. {stage2_name}", inline=False)
        if mode_icon_path:
            filename = _safe_attachment_filename(mode_icon_path, prefix="mode")
            embed.set_thumbnail(url=f"attachment://{filename}")
            if filename not in files_by_name:
                files_by_name[filename] = discord.File(mode_icon_path, filename=filename)
        stage1_path = _find_local_image_by_name(stage1_name)
        stage2_path = _find_local_image_by_name(stage2_name)
        rule_icon_path = _find_local_rule_icon(rule)

        card_bytes = _render_stage_card_bytes(
            rule_name=rule,
            rule_icon_path=rule_icon_path,
            stage1_name=stage1_name,
            stage1_path=stage1_path,
            stage2_name=stage2_name,
            stage2_path=stage2_path,
        )
        if card_bytes:
            filename = f"card_{hashlib.md5(card_bytes).hexdigest()}.png"
            embed.set_image(url=f"attachment://{filename}")
            if filename not in files_by_name:
                files_by_name[filename] = discord.File(fp=io.BytesIO(card_bytes), filename=filename)
        else:
            # Fallback: attach available stage images individually.
            if stage1_path:
                filename = _safe_attachment_filename(stage1_path, prefix="stage")
                embed.set_image(url=f"attachment://{filename}")
                if filename not in files_by_name:
                    files_by_name[filename] = discord.File(stage1_path, filename=filename)

        embeds.append(embed)

    return embeds, list(files_by_name.values())

def _get_stage_payload(schedule_index: int, title_prefix: str) -> tuple[list[discord.Embed] | None, list[discord.File] | None, str | None]:
    data = get_stages()
    if not data:
        return None, None, "データの取得に失敗しました。"

    res = data.get("result", {})
    embeds, files = _build_mode_embeds(res, schedule_index=schedule_index, title_prefix=title_prefix)
    return embeds, files, None

def _get_stage_rotation_key(data: dict) -> str | None:
    try:
        res = data.get("result", {})
        regular = res.get("regular", [])
        if not regular:
            return None
        cur = regular[0]
        return cur.get("start_time")
    except Exception:
        return None

def _find_current_item(results: list[dict]) -> dict | None:
    now = datetime.now().astimezone()
    for item in results:
        try:
            start_raw = item.get("start_time") or item.get("startTime") or ""
            end_raw = item.get("end_time") or item.get("endTime") or ""
            start_time = _parse_iso_datetime(start_raw)
            end_time = _parse_iso_datetime(end_raw)
        except Exception:
            continue
        if start_time <= now < end_time:
            return item
    return None

def _load_locale() -> dict:
    global _LOCALE_CACHE
    if _LOCALE_CACHE is not None:
        return _LOCALE_CACHE
    data = get_locale_data()
    _LOCALE_CACHE = data or {}
    return _LOCALE_CACHE

def _locale_name(category: str, key: str | None) -> str | None:
    if not key:
        return None
    loc = _load_locale()
    item = (loc.get(category) or {}).get(key)
    if isinstance(item, dict):
        return item.get("name")
    return None

def _localized_gear_name(gear: dict) -> str:
    key = gear.get("__splatoon3ink_id")
    name = _locale_name("gear", key)
    return name or gear.get("name") or "不明"

def _localized_power_name(power: dict) -> str:
    key = power.get("__splatoon3ink_id")
    name = _locale_name("powers", key)
    return name or power.get("name") or "不明"


def _localized_brand_name(brand: dict) -> str:
    key = brand.get("id") or brand.get("__splatoon3ink_id")
    name = _locale_name("brands", key)
    return name or brand.get("name") or "不明"


def _find_brand_logo_path(brand: dict) -> str | None:
    base_dir = os.path.join(os.path.dirname(__file__), "img", "ギアブランド")
    name = _localized_brand_name(brand)
    if name:
        candidate = os.path.join(base_dir, f"{name}.png")
        if os.path.exists(candidate):
            return candidate
    raw_name = brand.get("name")
    if raw_name and raw_name != name:
        candidate = os.path.join(base_dir, f"{raw_name}.png")
        if os.path.exists(candidate):
            return candidate
    return None

def _get_current_fest_record(data: dict) -> dict | None:
    if not data:
        return None
    region = data.get("JP") or {}
    records = region.get("data", {}).get("festRecords", {}).get("nodes", [])
    current = _find_current_item(records)
    return current


def _is_fest_active() -> bool:
    data = get_festivals_data()
    current = _get_current_fest_record(data or {})
    return current is not None

def _get_salmon_payload() -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    data = get_salmon_schedule()
    if not data:
        return None, None, "データの取得に失敗しました。"

    results = data.get("results") or []
    if not results:
        return None, None, "サーモンランの情報がありません。"

    return _build_salmon_payload_from_item(results[0])

def _build_salmon_payload_from_item(item: dict) -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    current = item
    stage = current.get("stage") or {}
    boss = current.get("boss") or {}
    weapons = current.get("weapons") or []

    stage_name = stage.get("name") or "不明"
    boss_name = boss.get("name") or "不明"
    start_time = _format_mmdd_hhmm(current["start_time"])
    end_time = _format_mmdd_hhmm(current["end_time"])
    is_big_run = bool(current.get("is_big_run"))

    embed = discord.Embed(title="【サーモンラン】", color=0xFF8C00)
    embed.add_field(name="時間", value=f"{start_time}～{end_time}", inline=True)
    embed.add_field(name="ステージ", value=f"**{stage_name}**", inline=True)
    embed.add_field(name="オカシラ", value=f"**{boss_name}**", inline=True)
    if is_big_run:
        embed.add_field(name="ビッグラン", value="開催中", inline=True)

    weapon_names = []
    for w in weapons:
        if isinstance(w, dict):
            weapon_names.append(w.get("name") or "不明")
        elif isinstance(w, str):
            weapon_names.append(w)
    if weapon_names:
        embed.add_field(name="ブキ", value="\n".join(f"- {n}" for n in weapon_names), inline=False)

    files_by_name: dict[str, discord.File] = {}

    stage_path = _find_local_image_by_name(stage_name)
    salmon_card = _render_salmon_stage_with_weapons_bytes(stage_path, weapon_names)
    if salmon_card:
        filename = f"salmon_{hashlib.md5(salmon_card).hexdigest()}.png"
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(fp=io.BytesIO(salmon_card), filename=filename)
    elif stage_path:
        filename = _safe_attachment_filename(stage_path, prefix="salmon_stage")
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(stage_path, filename=filename)

    boss_path = _find_local_image_by_name(boss_name)
    if boss_path:
        filename = _safe_attachment_filename(boss_path, prefix="salmon_boss")
        embed.set_thumbnail(url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(boss_path, filename=filename)
    else:
        random_weapon = any(n == "ランダム" for n in weapon_names)
        if random_weapon:
            random_path = _find_weapon_image_by_name("ランダム")
            if random_path:
                filename = _safe_attachment_filename(random_path, prefix="salmon_random")
                embed.set_thumbnail(url=f"attachment://{filename}")
                if filename not in files_by_name:
                    files_by_name[filename] = discord.File(random_path, filename=filename)

    salmon_icon_path = _find_local_image_by_name("サーモンラン")
    if salmon_icon_path:
        filename = _safe_attachment_filename(salmon_icon_path, prefix="salmon")
        embed.set_footer(text="SALMON RUN", icon_url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(salmon_icon_path, filename=filename)

    return embed, list(files_by_name.values()), None

async def _send_ephemeral_payloads(
    interaction: discord.Interaction,
    payloads: list[tuple[list[discord.Embed] | None, list[discord.File] | None]],
) -> None:
    first = True
    use_followup_only = interaction.response.is_done()
    for embeds, files in payloads:
        if not embeds:
            continue
        if first and not use_followup_only:
            await interaction.response.send_message(embeds=embeds, files=files, ephemeral=True)
            first = False
        else:
            await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)

async def _send_ephemeral_text(interaction: discord.Interaction, text: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)

def _get_current_event_item(data: dict) -> dict | None:
    results = data.get("results") or []
    return _find_current_item(results)

def _build_event_payload_from_item(
    item: dict,
    title_prefix: str,
    status_label: str | None,
) -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    rule = _format_rule(item.get("rule"))
    event = item.get("event") or {}
    event_name = event.get("name") or "不明"
    event_desc = event.get("desc") or ""
    stage_names = _extract_stage_names(item.get("stages"))
    stage1_name = stage_names[0] if len(stage_names) > 0 else "不明"
    stage2_name = stage_names[1] if len(stage_names) > 1 else "不明"

    try:
        start_time = _format_mmdd_hhmm(item.get("start_time", ""))
        end_time = _format_mmdd_hhmm(item.get("end_time", ""))
    except Exception:
        start_time = "不明"
        end_time = "不明"

    embed = discord.Embed(title="【イベントマッチ】", color=0xFF69B4)
    embed.add_field(name="時間", value=f"{start_time}～{end_time}", inline=True)
    embed.add_field(name="イベント", value=f"**{event_name}**", inline=False)
    if event_desc:
        embed.add_field(name="説明", value=event_desc, inline=False)
    embed.add_field(name="ルール", value=f"**{rule}**", inline=True)
    embed.add_field(name="ステージ", value=f"1. {stage1_name}\n2. {stage2_name}", inline=False)

    files_by_name: dict[str, discord.File] = {}
    event_icon_path = _find_local_image_by_name("イベントマッチ")
    if event_icon_path:
        filename = _safe_attachment_filename(event_icon_path, prefix="event")
        embed.set_thumbnail(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(event_icon_path, filename=filename)
    stage1_path = _find_local_image_by_name(stage1_name)
    stage2_path = _find_local_image_by_name(stage2_name)
    rule_icon_path = _find_local_rule_icon(rule)

    card_bytes = _render_stage_card_bytes(
        rule_name=rule,
        rule_icon_path=rule_icon_path,
        stage1_name=stage1_name,
        stage1_path=stage1_path,
        stage2_name=stage2_name,
        stage2_path=stage2_path,
    )
    if card_bytes:
        filename = f"event_{hashlib.md5(card_bytes).hexdigest()}.png"
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(fp=io.BytesIO(card_bytes), filename=filename)
    else:
        if stage1_path:
            filename = _safe_attachment_filename(stage1_path, prefix="event_stage")
            embed.set_image(url=f"attachment://{filename}")
            if filename not in files_by_name:
                files_by_name[filename] = discord.File(stage1_path, filename=filename)

    return embed, list(files_by_name.values()), None

def _get_event_payload() -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    data = get_event_schedule()
    if not data:
        return None, None, "データの取得に失敗しました。"

    results = data.get("results") or []
    if not results:
        return None, None, "イベントマッチの情報がありません。"

    current = _get_current_event_item(data)
    if current:
        return _build_event_payload_from_item(current, "イベントマッチ情報", "開催中")

    now = datetime.now().astimezone()
    for item in results:
        try:
            end_time = _parse_iso_datetime(item.get("end_time", ""))
        except Exception:
            continue
        if now < end_time:
            return _build_event_payload_from_item(item, "イベントマッチ情報", "次回")

    return _build_event_payload_from_item(results[0], "イベントマッチ情報", None)

def _resolve_notify_channel_id(state: dict, state_key: str, env_value: int) -> int:
    value = int(state.get(state_key) or env_value or 0)
    if value:
        return value
    return int(state.get("stage_notify_channel_id") or STAGE_NOTIFY_CHANNEL_ID or 0)

def _get_current_salmon_item(data: dict) -> dict | None:
    results = data.get("results") or []
    return _find_current_item(results)

def _get_current_team_contest_item(data: dict) -> dict | None:
    results = data.get("results") or []
    return _find_current_item(results)

def _normalize_gear_items(entries: list[dict]) -> list[dict]:
    items: list[dict] = []
    for g in entries:
        gear = g.get("gear") or {}
        name = _localized_gear_name(gear)
        price = g.get("price") or "?"
        item_id = gear.get("__splatoon3ink_id") or gear.get("name") or name
        image_url = (gear.get("image") or {}).get("url")
        brand = gear.get("brand") or {}
        items.append(
            {
                "id": item_id,
                "name": name,
                "price": price,
                "image_url": image_url,
                "brand_logo_path": _find_brand_logo_path(brand),
            }
        )
    return items


def _gear_item_key(item: dict) -> str:
    return f"{item.get('id') or ''}:{item.get('price') or ''}"


def _gear_items_signature(items: list[dict]) -> str:
    parts = sorted(_gear_item_key(item) for item in items)
    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _pickup_signature(pickup: dict, items: list[dict]) -> str:
    brand = pickup.get("brand") or {}
    brand_key = brand.get("__splatoon3ink_id") or brand.get("name") or ""
    parts = sorted(_gear_item_key(item) for item in items)
    raw = "|".join([str(brand_key)] + parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _serialize_gear_items(items: list[dict]) -> list[dict]:
    return [{"id": item.get("id"), "name": item.get("name"), "price": item.get("price")} for item in items]


def _build_gear_rotation_payload(
    limited_items: list[dict],
    added_keys: set[str],
    removed_items: list[dict],
) -> tuple[list[discord.Embed] | None, list[discord.File] | None, str | None]:
    embed = discord.Embed(title="【販売ギア入れ替わり】", color=0x4CAF50)

    if removed_items:
        lines = [f"{item.get('name')} ({item.get('price')}G)" for item in removed_items]
        embed.add_field(name="販売終了ギア", value="\n".join(lines), inline=False)

    if added_keys:
        lines = []
        for item in limited_items:
            if _gear_item_key(item) in added_keys:
                lines.append(f"**[New]**{item.get('name')} ({item.get('price')}G)")
        if lines:
            embed.add_field(name="新販売ギア", value="\n".join(lines), inline=False)

    if limited_items:
        lines = []
        for item in limited_items:
            label = f"{item.get('name')} ({item.get('price')}G)"
            if _gear_item_key(item) in added_keys:
                label = f"**[New]**{label}"
            lines.append(label)
        embed.add_field(name="販売中ギア", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="販売中ギア", value="なし", inline=False)

    files_by_name: dict[str, discord.File] = {}
    collage = _render_gear_collage_bytes(limited_items, "販売中ギア")
    if collage:
        filename = f"gear_limited_{hashlib.md5(collage).hexdigest()}.png"
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(fp=io.BytesIO(collage), filename=filename)

    return [embed], list(files_by_name.values()), None


def _build_pickup_payload(
    pickup: dict, pickup_items: list[dict]
) -> tuple[list[discord.Embed] | None, list[discord.File] | None, str | None]:
    embed = discord.Embed(title="【ピックアップ更新】", color=0x4CAF50)

    sale_end = pickup.get("saleEndTime") or ""
    try:
        sale_end_fmt = _format_mmdd_hhmm(sale_end)
    except Exception:
        sale_end_fmt = "不明"

    brand = pickup.get("brand") or {}
    brand_name = _localized_brand_name(brand)
    power = brand.get("usualGearPower") or {}
    power_name = _localized_power_name(power)
    embed.add_field(
        name="注目ブランド",
        value=f"{brand_name}\n得意ギアパワー: {power_name}\n期間: {sale_end_fmt}まで",
        inline=False,
    )

    if pickup_items:
        lines = [f"{item.get('name')} ({item.get('price')}G)" for item in pickup_items]
        embed.add_field(name="ピックアップ", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="ピックアップ", value="なし", inline=False)

    files_by_name: dict[str, discord.File] = {}
    collage = _render_gear_collage_bytes(pickup_items, "ピックアップ")
    if collage:
        filename = f"gear_pickup_{hashlib.md5(collage).hexdigest()}.png"
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(fp=io.BytesIO(collage), filename=filename)

    return [embed], list(files_by_name.values()), None

def _build_gear_payloads(data: dict) -> tuple[list[discord.Embed] | None, list[discord.File] | None, str | None]:
    try:
        gesotown = data.get("data", {}).get("gesotown", {})
    except Exception:
        return None, None, "データの取得に失敗しました。"

    pickup = gesotown.get("pickupBrand") or {}
    limited = gesotown.get("limitedGears") or []

    pickup_items = _normalize_gear_items(pickup.get("brandGears") or [])
    limited_items = _normalize_gear_items(limited)

    embeds: list[discord.Embed] = []
    files_by_name: dict[str, discord.File] = {}

    rotation_embeds, rotation_files, _ = _build_gear_rotation_payload(limited_items, set(), [])
    if rotation_embeds:
        embeds.extend(rotation_embeds)
    if rotation_files:
        for f in rotation_files:
            files_by_name[f.filename] = f

    pickup_embeds, pickup_files, _ = _build_pickup_payload(pickup, pickup_items)
    if pickup_embeds:
        embeds.extend(pickup_embeds)
    if pickup_files:
        for f in pickup_files:
            files_by_name[f.filename] = f

    if not embeds:
        return None, None, "ゲソタウンの情報がありません。"

    return embeds, list(files_by_name.values()), None

def _build_coop_monthly_payload(data: dict) -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    try:
        monthly = data.get("data", {}).get("coopResult", {}).get("monthlyGear") or {}
    except Exception:
        return None, None, "データの取得に失敗しました。"

    name = _localized_gear_name(monthly)
    embed = discord.Embed(title="【サーモンラン報酬ギア更新】", color=0xFF8C00)
    embed.add_field(name="ギア", value=name, inline=True)

    image_url = (monthly.get("image") or {}).get("url")
    if image_url:
        embed.set_thumbnail(url=image_url)

    files_by_name: dict[str, discord.File] = {}
    return embed, list(files_by_name.values()), None

def _build_xrank_text(data: dict, top_n: int = 100) -> tuple[str, str]:
    cur = data.get("data", {}).get("xRanking", {}).get("currentSeason", {}) if data else {}
    season_name = cur.get("name") or "Xランキング"
    last_update = cur.get("lastUpdateTime") or ""

    try:
        last_update_fmt = _format_mmdd_hhmm(last_update)
    except Exception:
        last_update_fmt = "不明"

    mode_map = {
        "xRankingAr": "ガチエリア",
        "xRankingCl": "ガチアサリ",
        "xRankingGl": "ガチホコ",
        "xRankingLf": "ガチヤグラ",
    }

    lines = [f"{season_name}", f"更新: {last_update_fmt}", ""]
    for key, label in mode_map.items():
        nodes = (cur.get(key) or {}).get("nodes") or []
        lines.append(f"■ {label}")
        for n in nodes[:top_n]:
            rank = n.get("rank")
            name = n.get("name") or "?"
            power = n.get("xPower")
            if power is None:
                power_text = "?"
            else:
                power_text = f"{power:.1f}" if isinstance(power, (int, float)) else str(power)
            lines.append(f"{rank}. {name} ({power_text})")
        lines.append("")

    return "\n".join(lines).strip(), last_update_fmt

def _build_fest_payload_from_record(record: dict) -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    try:
        start_time = _format_mmdd_hhmm(record.get("startTime", ""))
        end_time = _format_mmdd_hhmm(record.get("endTime", ""))
    except Exception:
        start_time = "不明"
        end_time = "不明"

    title = record.get("title") or "フェス"
    embed = discord.Embed(title="【フェス】", color=0xFF3D6E)
    embed.add_field(name="フェステーマ", value=title, inline=False)
    embed.add_field(name="時間", value=f"{start_time}～{end_time}", inline=True)

    teams = record.get("teams") or []
    team_names = [t.get("teamName") for t in teams if isinstance(t, dict) and t.get("teamName")]
    if team_names:
        embed.add_field(name="チーム", value="\n".join(f"- {n}" for n in team_names), inline=False)

    image_url = (record.get("image") or {}).get("url")
    if image_url:
        embed.set_image(url=image_url)

    files_by_name: dict[str, discord.File] = {}
    fest_icon_path = _find_local_image_by_name("フェス")
    if fest_icon_path:
        filename = _safe_attachment_filename(fest_icon_path, prefix="fest")
        embed.set_thumbnail(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(fest_icon_path, filename=filename)

    return embed, list(files_by_name.values()), None


def _get_team_contest_payload() -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    data = get_team_contest_schedule()
    if not data:
        return None, None, "データの取得に失敗しました。"

    results = data.get("results") or []
    if not results:
        return None, None, "バイトチームコンテストの予定がありません。"

    contest = results[0]
    stage = contest.get("stage") or {}
    boss = contest.get("boss") or {}
    weapons = contest.get("weapons") or []

    stage_name = stage.get("name") or "不明"
    boss_name = boss.get("name") or "不明"
    start_time = _format_mmdd_hhmm(contest.get("start_time", ""))
    end_time = _format_mmdd_hhmm(contest.get("end_time", ""))

    embed = discord.Embed(title="【バイトチームコンテスト】", color=0xFFB000)
    embed.add_field(name="時間", value=f"{start_time}～{end_time}", inline=True)
    embed.add_field(name="ステージ", value=f"**{stage_name}**", inline=True)
    if boss_name != "不明":
        embed.add_field(name="オカシラ", value=f"**{boss_name}**", inline=True)

    weapon_names = []
    for w in weapons:
        if isinstance(w, dict):
            weapon_names.append(w.get("name") or "不明")
        elif isinstance(w, str):
            weapon_names.append(w)
    if weapon_names:
        embed.add_field(name="ブキ", value="\n".join(f"- {n}" for n in weapon_names), inline=False)

    files_by_name: dict[str, discord.File] = {}

    stage_path = _find_local_image_by_name(stage_name)
    if stage_path:
        filename = _safe_attachment_filename(stage_path, prefix="team_stage")
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(stage_path, filename=filename)

    boss_path = _find_local_image_by_name(boss_name)
    if boss_path:
        filename = _safe_attachment_filename(boss_path, prefix="team_boss")
        embed.set_thumbnail(url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(boss_path, filename=filename)

    team_icon_path = _find_local_image_by_name("バイトチームコンテスト")
    if team_icon_path:
        filename = _safe_attachment_filename(team_icon_path, prefix="team")
        embed.set_footer(text="TEAM CONTEST", icon_url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(team_icon_path, filename=filename)

    return embed, list(files_by_name.values()), None

async def _send_stage_embed(ctx, schedule_index: int, title: str):
    embeds, files, error = _get_stage_payload(schedule_index=schedule_index, title_prefix=title)
    if error:
        await ctx.send(error)
        return
    await ctx.send(embeds=embeds, files=files)

@bot.command(name="next")
async def next_stage(ctx):
    """/next で次のステージを通知"""
    await _send_stage_embed(ctx, schedule_index=1, title="つぎのステージ情報")

@bot.command()
async def now(ctx):
    """/now で現在のステージを通知"""
    await _send_stage_embed(ctx, schedule_index=0, title="現在のステージ情報")

@bot.tree.command(name="now", description="現在のステージを表示します")
async def now_slash(interaction: discord.Interaction):
    embeds, files, error = _get_stage_payload(schedule_index=0, title_prefix="現在のステージ情報")
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embeds=embeds, files=files)

@bot.tree.command(name="next", description="次のステージを表示します")
async def next_slash(interaction: discord.Interaction):
    embeds, files, error = _get_stage_payload(schedule_index=1, title_prefix="つぎのステージ情報")
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embeds=embeds, files=files)

@bot.tree.command(name="all-next", description="取得できる全ての時間帯のステージを表示します")
async def all_next_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = get_stages()
    if not data:
        await _send_ephemeral_text(interaction, "データの取得に失敗しました。")
        return
    res = data.get("result", {})
    mode_keys = ("regular", "bankara_challenge", "bankara_open", "x")
    max_len = 0
    for key in mode_keys:
        try:
            max_len = max(max_len, len(res.get(key, [])))
        except Exception:
            continue
    if max_len == 0:
        await _send_ephemeral_text(interaction, "ステージ情報がありません。")
        return
    payloads: list[tuple[list[discord.Embed] | None, list[discord.File] | None]] = []
    for idx in range(max_len):
        embeds, files = _build_mode_embeds(res, schedule_index=idx, title_prefix="ステージ情報")
        payloads.append((embeds, files))
    if not payloads:
        await _send_ephemeral_text(interaction, "ステージ情報がありません。")
        return
    await _send_ephemeral_payloads(interaction, payloads)

@bot.tree.command(name="salmon", description="現在のサーモンランを表示します")
async def salmon_slash(interaction: discord.Interaction):
    embed, files, error = _get_salmon_payload()
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="all-salmon", description="取得できる全ての時間帯のサーモンランを表示します")
async def all_salmon_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = get_salmon_schedule()
    if not data:
        await _send_ephemeral_text(interaction, "データの取得に失敗しました。")
        return
    results = data.get("results") or []
    if not results:
        await _send_ephemeral_text(interaction, "サーモンランの情報がありません。")
        return
    payloads: list[tuple[list[discord.Embed] | None, list[discord.File] | None]] = []
    for item in results:
        embed, files, error = _build_salmon_payload_from_item(item)
        if error or not embed:
            continue
        payloads.append(([embed], files))
    if not payloads:
        await _send_ephemeral_text(interaction, "サーモンランの情報がありません。")
        return
    await _send_ephemeral_payloads(interaction, payloads)

@bot.tree.command(name="team_contest", description="バイトチームコンテストを表示します")
async def team_contest_slash(interaction: discord.Interaction):
    embed, files, error = _get_team_contest_payload()
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="event", description="イベントマッチを表示します")
async def event_slash(interaction: discord.Interaction):
    embed, files, error = _get_event_payload()
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="all-event", description="取得できる全ての時間帯のイベントマッチを表示します")
async def all_event_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = get_event_schedule()
    if not data:
        await _send_ephemeral_text(interaction, "データの取得に失敗しました。")
        return
    results = data.get("results") or []
    if not results:
        await _send_ephemeral_text(interaction, "イベントマッチの情報がありません。")
        return
    payloads: list[tuple[list[discord.Embed] | None, list[discord.File] | None]] = []
    for item in results:
        embed, files, error = _build_event_payload_from_item(item, "イベントマッチ情報", None)
        if error or not embed:
            continue
        payloads.append(([embed], files))
    if not payloads:
        await _send_ephemeral_text(interaction, "イベントマッチの情報がありません。")
        return
    await _send_ephemeral_payloads(interaction, payloads)

@bot.tree.command(name="gear", description="ゲソタウンのギア更新情報を表示します")
async def gear_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = get_gear_data()
    if not data:
        await interaction.followup.send("データの取得に失敗しました。", ephemeral=True)
        return
    embeds, files, error = _build_gear_payloads(data)
    if error:
        await interaction.followup.send(error, ephemeral=True)
        return
    await interaction.followup.send(embeds=embeds, files=files)

@bot.tree.command(name="monthly_gear", description="サーモンランの月替わりギアを表示します")
async def monthly_gear_slash(interaction: discord.Interaction):
    data = get_coop_data()
    if not data:
        await interaction.response.send_message("データの取得に失敗しました。", ephemeral=True)
        return
    embed, files, error = _build_coop_monthly_payload(data)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="fest", description="フェス情報を表示します")
async def fest_slash(interaction: discord.Interaction):
    data = get_festivals_data()
    if not data:
        await interaction.response.send_message("データの取得に失敗しました。", ephemeral=True)
        return
    record = _get_current_fest_record(data)
    if not record:
        await interaction.response.send_message("現在開催中のフェスはありません。", ephemeral=True)
        return
    embed, files, error = _build_fest_payload_from_record(record)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="all-fest", description="取得できる全てのフェス情報を表示します")
async def all_fest_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = get_festivals_data()
    if not data:
        await _send_ephemeral_text(interaction, "データの取得に失敗しました。")
        return
    region = data.get("JP") or {}
    records = region.get("data", {}).get("festRecords", {}).get("nodes", [])
    if not records:
        await _send_ephemeral_text(interaction, "フェス情報がありません。")
        return
    payloads: list[tuple[list[discord.Embed] | None, list[discord.File] | None]] = []
    for record in records:
        embed, files, error = _build_fest_payload_from_record(record)
        if error or not embed:
            continue
        payloads.append(([embed], files))
    if not payloads:
        await _send_ephemeral_text(interaction, "フェス情報がありません。")
        return
    await _send_ephemeral_payloads(interaction, payloads)


@bot.tree.command(name="xrank", description="Xランキング（タカオカ）のトップ100を表示します")
async def xrank_slash(interaction: discord.Interaction):
    data = get_xrank_data()
    if not data:
        await interaction.response.send_message("データの取得に失敗しました。", ephemeral=True)
        return
    text, last_update_fmt = _build_xrank_text(data, top_n=100)
    if not text:
        await interaction.response.send_message("データの取得に失敗しました。", ephemeral=True)
        return
    embed = discord.Embed(title="【Xランキング トップ100】", color=0x4DA3FF)
    embed.add_field(name="更新", value=last_update_fmt, inline=True)
    file_obj = discord.File(fp=io.BytesIO(text.encode("utf-8")), filename="xrank_top100.txt")
    await interaction.response.send_message(embed=embed, file=file_obj)

@bot.tree.command(name="help", description="コマンド一覧を表示します")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="コマンド一覧", color=0x6C8EBF)
    embed.add_field(
        name="表示",
        value=(
            "/next\n"
            "/all-next\n"
            "/salmon\n"
            "/all-salmon\n"
            "/team_contest\n"
            "/event\n"
            "/all-event\n"
            "/fest\n"
            "/all-fest\n"
            "/gear\n"
            "/monthly_gear\n"
            "/xrank"
        ),
        inline=False,
    )
    embed.add_field(
        name="通知チャンネル設定",
        value=(
            "/notify_here\n"
            "/event_notify_here\n"
            "/salmon_notify_here\n"
            "/team_contest_notify_here\n"
            "/fest_notify_here\n"
            "/gear_notify_here\n"
            "/monthly_gear_notify_here\n"
            "/xrank_notify_here"
        ),
        inline=False,
    )
    embed.add_field(
        name="通知テスト",
        value="なし",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="notify_here", description="ステージ自動通知の送信先をこのチャンネルに設定します")
async def notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"stage_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをステージ自動通知の送信先に設定しました。", ephemeral=True)


@bot.tree.command(name="event_notify_here", description="イベントマッチ自動通知の送信先をこのチャンネルに設定します")
async def event_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"event_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをイベントマッチ自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="salmon_notify_here", description="サーモンラン自動通知の送信先をこのチャンネルに設定します")
async def salmon_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"salmon_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをサーモンラン自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="team_contest_notify_here", description="バイトチームコンテスト自動通知の送信先をこのチャンネルに設定します")
async def team_contest_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"team_contest_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをバイトチームコンテスト自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="fest_notify_here", description="フェス自動通知の送信先をこのチャンネルに設定します")
async def fest_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"fest_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをフェス自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="gear_notify_here", description="ギア更新自動通知の送信先をこのチャンネルに設定します")
async def gear_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"gear_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをギア更新自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="monthly_gear_notify_here", description="サーモンラン月替わりギア自動通知の送信先をこのチャンネルに設定します")
async def monthly_gear_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"coop_monthly_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをサーモンラン月替わりギア自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="xrank_notify_here", description="Xランキング自動通知の送信先をこのチャンネルに設定します")
async def xrank_notify_here_slash(interaction: discord.Interaction):
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    _update_state({"xrank_notify_channel_id": int(interaction.channel_id)})
    await interaction.response.send_message("このチャンネルをXランキング自動通知の送信先に設定しました。", ephemeral=True)


_did_sync_app_commands = False

@tasks.loop(minutes=1)
async def _stage_auto_notify_loop():
    state = _load_state()
    channel_id = int(state.get("stage_notify_channel_id") or STAGE_NOTIFY_CHANNEL_ID or 0)
    if not channel_id:
        return
    if _is_fest_active():
        return

    data = get_stages()
    if not data:
        return

    rotation_key = _get_stage_rotation_key(data)
    if not rotation_key:
        return

    last_key = state.get("stage_last_rotation_key")
    if last_key is None:
        _update_state({"stage_last_rotation_key": rotation_key})
        if not STAGE_NOTIFY_ON_START:
            return

    if last_key == rotation_key:
        return

    channel = await _get_text_channel(channel_id)
    if channel is None:
        return

    embeds, files, error = _get_stage_payload(schedule_index=0, title_prefix="現在のステージ情報")
    if error:
        return
    last_message_id = state.get("stage_last_message_id")
    if last_message_id:
        try:
            old_msg = await channel.fetch_message(int(last_message_id))
            await old_msg.delete()
        except Exception:
            pass

    sent = await channel.send(embeds=embeds, files=files)

    _update_state(
        {
            "stage_last_rotation_key": rotation_key,
            "stage_last_message_id": int(sent.id),
        }
    )

@tasks.loop(minutes=1)
async def _event_auto_notify_loop():
    state = _load_state()
    channel_id = _resolve_notify_channel_id(state, "event_notify_channel_id", EVENT_NOTIFY_CHANNEL_ID)
    if not channel_id:
        return
    if _is_fest_active():
        return

    data = get_event_schedule()
    if not data:
        return

    current = _get_current_event_item(data)
    if not current:
        return

    rotation_key = current.get("start_time")
    if not rotation_key:
        return

    last_key = state.get("event_last_rotation_key")
    if last_key is None:
        _update_state({"event_last_rotation_key": rotation_key})
        if not EVENT_NOTIFY_ON_START:
            return

    if last_key == rotation_key:
        return

    channel = await _get_text_channel(channel_id)
    if channel is None:
        return

    embed, files, error = _build_event_payload_from_item(current, "イベントマッチ開始", "開催中")
    if error:
        return
    await channel.send(embed=embed, files=files)

    _update_state({"event_last_rotation_key": rotation_key})

@tasks.loop(minutes=1)
async def _salmon_auto_notify_loop():
    if not _acquire_lock("salmon_auto_notify"):
        return
    state = _load_state()
    try:
        channel_id = _resolve_notify_channel_id(state, "salmon_notify_channel_id", SALMON_NOTIFY_CHANNEL_ID)
        if not channel_id:
            return
        if _is_fest_active():
            return

        data = get_salmon_schedule()
        if not data:
            return

        current = _get_current_salmon_item(data)
        if not current:
            return

        rotation_key = current.get("start_time")
        if not rotation_key:
            return

        last_key = state.get("salmon_last_rotation_key")
        if last_key is None:
            _update_state({"salmon_last_rotation_key": rotation_key})
            if not SALMON_NOTIFY_ON_START:
                return

        if last_key == rotation_key:
            return

        channel = await _get_text_channel(channel_id)
        if channel is None:
            return

        embed, files, error = _get_salmon_payload()
        if error:
            return
        await channel.send(embed=embed, files=files)

        _update_state({"salmon_last_rotation_key": rotation_key})
    finally:
        _release_lock("salmon_auto_notify")

@tasks.loop(minutes=1)
async def _team_contest_auto_notify_loop():
    state = _load_state()
    channel_id = _resolve_notify_channel_id(state, "team_contest_notify_channel_id", TEAM_CONTEST_NOTIFY_CHANNEL_ID)
    if not channel_id:
        return
    if _is_fest_active():
        return

    data = get_team_contest_schedule()
    if not data:
        return

    current = _get_current_team_contest_item(data)
    if not current:
        return

    rotation_key = current.get("start_time")
    if not rotation_key:
        return

    last_key = state.get("team_contest_last_rotation_key")
    if last_key is None:
        _update_state({"team_contest_last_rotation_key": rotation_key})
        if not TEAM_CONTEST_NOTIFY_ON_START:
            return

    if last_key == rotation_key:
        return

    channel = await _get_text_channel(channel_id)
    if channel is None:
        return

    embed, files, error = _get_team_contest_payload()
    if error:
        return
    await channel.send(embed=embed, files=files)

    _update_state({"team_contest_last_rotation_key": rotation_key})

@tasks.loop(minutes=1)
async def _fest_auto_notify_loop():
    state = _load_state()
    channel_id = _resolve_notify_channel_id(state, "fest_notify_channel_id", FEST_NOTIFY_CHANNEL_ID)
    if not channel_id:
        return

    data = get_festivals_data()
    if not data:
        return

    current = _get_current_fest_record(data)
    if not current:
        return

    rotation_key = current.get("startTime")
    if not rotation_key:
        return

    last_key = state.get("fest_last_rotation_key")
    if last_key is None:
        _update_state({"fest_last_rotation_key": rotation_key})
        if not FEST_NOTIFY_ON_START:
            return

    if last_key == rotation_key:
        return

    channel = await _get_text_channel(channel_id)
    if channel is None:
        return

    embed, files, error = _build_fest_payload_from_record(current)
    if error:
        return
    await channel.send(embed=embed, files=files)

    _update_state({"fest_last_rotation_key": rotation_key})


@tasks.loop(minutes=10)
async def _gear_auto_notify_loop():
    if not _acquire_lock("gear_auto_notify"):
        return
    state = _load_state()
    try:
        channel_id = _resolve_notify_channel_id(state, "gear_notify_channel_id", GEAR_NOTIFY_CHANNEL_ID)
        if not channel_id:
            return
        if _is_fest_active():
            return

        gear_data = get_gear_data()
        if not gear_data:
            return

        try:
            gesotown = gear_data.get("data", {}).get("gesotown", {})
        except Exception:
            return

        pickup = gesotown.get("pickupBrand") or {}
        limited = gesotown.get("limitedGears") or []
        pickup_items = _normalize_gear_items(pickup.get("brandGears") or [])
        limited_items = _normalize_gear_items(limited)

        gear_state = _load_gear_notify_state()
        last_limited_sig = gear_state.get("gesotown_limited_sig")
        last_pickup_sig = gear_state.get("gesotown_pickup_sig")
        current_limited_sig = _gear_items_signature(limited_items)
        current_pickup_sig = _pickup_signature(pickup, pickup_items)
        first_seen = last_limited_sig is None and last_pickup_sig is None

        if first_seen:
            _update_gear_notify_state(
                {
                    "gesotown_limited_sig": current_limited_sig,
                    "gesotown_pickup_sig": current_pickup_sig,
                    "gesotown_limited_items": _serialize_gear_items(limited_items),
                    "gesotown_pickup_items": _serialize_gear_items(pickup_items),
                }
            )
            if not GEAR_NOTIFY_ON_START:
                return

        channel = await _get_text_channel(channel_id)
        if channel is None:
            return

        if last_limited_sig != current_limited_sig:
            prev_limited = gear_state.get("gesotown_limited_items") or []
            prev_by_key = {_gear_item_key(item): item for item in prev_limited}
            cur_by_key = {_gear_item_key(item): item for item in limited_items}
            added_keys = set(cur_by_key.keys()) - set(prev_by_key.keys())
            removed_items = [prev_by_key[key] for key in prev_by_key.keys() if key not in cur_by_key]

            embeds, files, error = _build_gear_rotation_payload(limited_items, added_keys, removed_items)
            if not error:
                await channel.send(embeds=embeds, files=files)

        if last_pickup_sig != current_pickup_sig:
            embeds, files, error = _build_pickup_payload(pickup, pickup_items)
            if not error:
                await channel.send(embeds=embeds, files=files)

        _update_gear_notify_state(
            {
                "gesotown_limited_sig": current_limited_sig,
                "gesotown_pickup_sig": current_pickup_sig,
                "gesotown_limited_items": _serialize_gear_items(limited_items),
                "gesotown_pickup_items": _serialize_gear_items(pickup_items),
            }
        )

        coop_data = get_coop_data()
        if not coop_data:
            return
        monthly = coop_data.get("data", {}).get("coopResult", {}).get("monthlyGear") or {}
        monthly_id = monthly.get("__splatoon3ink_id") or monthly.get("name")
        if not monthly_id:
            return

        last_monthly = state.get("coop_monthly_gear_id")
        if last_monthly is None:
            _update_state({"coop_monthly_gear_id": monthly_id})
            return

        if last_monthly != monthly_id:
            monthly_channel_id = _resolve_notify_channel_id(
                state,
                "coop_monthly_notify_channel_id",
                COOP_MONTHLY_NOTIFY_CHANNEL_ID,
            )
            if monthly_channel_id:
                monthly_channel = await _get_text_channel(monthly_channel_id)
                if monthly_channel is not None:
                    embed, files, error = _build_coop_monthly_payload(coop_data)
                    if not error:
                        await monthly_channel.send(embed=embed, files=files)
            _update_state({"coop_monthly_gear_id": monthly_id})
    finally:
        _release_lock("gear_auto_notify")

@tasks.loop(minutes=1)
async def _xrank_daily_notify_loop():
    state = _load_state()
    channel_id = _resolve_notify_channel_id(state, "xrank_notify_channel_id", XRANK_NOTIFY_CHANNEL_ID)
    if not channel_id:
        return
    if _is_fest_active():
        return

    data = get_xrank_data()
    if not data:
        return

    cur = data.get("data", {}).get("xRanking", {}).get("currentSeason", {}) if data else {}
    end_time_raw = cur.get("endTime") or ""
    try:
        end_time = _parse_iso_datetime(end_time_raw).astimezone()
    except Exception:
        return

    now = datetime.now().astimezone()
    if not (now.year == end_time.year and now.month == end_time.month and now.day == end_time.day):
        return
    if not (now.hour == 0 and now.minute <= 5):
        return

    today_key = now.strftime("%Y-%m-%d")
    if state.get("xrank_last_sent_date") == today_key:
        return

    text, last_update_fmt = _build_xrank_text(data, top_n=100)
    if not text:
        return

    channel = await _get_text_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(title="【Xランキング トップ100】", color=0x4DA3FF)
    embed.add_field(name="更新", value=last_update_fmt, inline=True)
    file_obj = discord.File(fp=io.BytesIO(text.encode("utf-8")), filename="xrank_top100.txt")
    await channel.send(embed=embed, file=file_obj)

    _update_state({"xrank_last_sent_date": today_key})

@bot.event
async def on_ready():
    global _did_sync_app_commands
    print(f'Logged in as {bot.user.name}')
    if not _did_sync_app_commands:
        await bot.tree.sync()
        _did_sync_app_commands = True
    await bot.change_presence(activity=discord.Game(name=BOT_ACTIVITY_NAME))
    if not _stage_auto_notify_loop.is_running():
        _stage_auto_notify_loop.start()
    if not _event_auto_notify_loop.is_running():
        _event_auto_notify_loop.start()
    if not _salmon_auto_notify_loop.is_running():
        _salmon_auto_notify_loop.start()
    if not _team_contest_auto_notify_loop.is_running():
        _team_contest_auto_notify_loop.start()
    if not _fest_auto_notify_loop.is_running():
        _fest_auto_notify_loop.start()
    if not _gear_auto_notify_loop.is_running():
        _gear_auto_notify_loop.start()
    if not _xrank_daily_notify_loop.is_running():
        _xrank_daily_notify_loop.start()

if __name__ == "__main__":
    if not os.getenv("DISCORD_TOKEN"):
        _load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "")
    if not token:
        raise RuntimeError("環境変数 DISCORD_TOKEN に Discord Bot Token を設定してください。")

    bot.run(token)
