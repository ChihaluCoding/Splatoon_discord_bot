import discord
from discord.ext import commands
from discord.ext import tasks
import os
import hashlib
import io
import json
import requests
from datetime import datetime

# --- 設定 ---
TOKEN = os.getenv("DISCORD_TOKEN", "")

API_URL = "https://spla3.yuu26.com/api/schedule"
SALMON_API_URL = "https://spla3.yuu26.com/api/coop-grouping/schedule"
TEAM_CONTEST_API_URL = "https://spla3.yuu26.com/api/coop-grouping-team-contest/schedule"
USER_AGENT = "DiscordBot_SplaStageInfo (Contact: chihalu)" # 連絡先を記載

# Botの基本設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

IMG_DIR = os.path.join(os.path.dirname(__file__), "img")
STATE_PATH = os.path.join(os.path.dirname(__file__), ".bot_state.json")
STAGE_NOTIFY_CHANNEL_ID = int(os.getenv("STAGE_NOTIFY_CHANNEL_ID", "0") or "0")
STAGE_NOTIFY_ON_START = (os.getenv("STAGE_NOTIFY_ON_START", "0") == "1")
BOT_ACTIVITY_NAME = os.getenv("BOT_ACTIVITY_NAME", "Splatoon")

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
    draw.text((icon_x + icon_size + 14, pad + 10), rule_name, fill=(255, 255, 255, 255), font=title_font)

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
        # center text
        bbox = odraw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        odraw.text(((w - tw) // 2, (label_h - th) // 2 - 1), text, fill=(255, 255, 255, 255), font=font)
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
            embed.set_author(name=title_prefix)
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
        embed.set_author(name=title_prefix)
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

def _get_salmon_payload() -> tuple[discord.Embed | None, list[discord.File] | None, str | None]:
    data = get_salmon_schedule()
    if not data:
        return None, None, "データの取得に失敗しました。"

    results = data.get("results") or []
    if not results:
        return None, None, "サーモンランの情報がありません。"

    current = results[0]
    stage = current.get("stage") or {}
    boss = current.get("boss") or {}
    weapons = current.get("weapons") or []

    stage_name = stage.get("name") or "不明"
    boss_name = boss.get("name") or "不明"
    start_time = _format_mmdd_hhmm(current["start_time"])
    end_time = _format_mmdd_hhmm(current["end_time"])
    is_big_run = bool(current.get("is_big_run"))

    embed = discord.Embed(title="【サーモンラン】", color=0xFF8C00)
    embed.set_author(name="現在のサーモンラン情報")
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
    if stage_path:
        filename = _safe_attachment_filename(stage_path, prefix="salmon_stage")
        embed.set_image(url=f"attachment://{filename}")
        files_by_name[filename] = discord.File(stage_path, filename=filename)

    boss_path = _find_local_image_by_name(boss_name)
    if boss_path:
        filename = _safe_attachment_filename(boss_path, prefix="salmon_boss")
        embed.set_thumbnail(url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(boss_path, filename=filename)

    salmon_icon_path = _find_local_image_by_name("サーモンラン")
    if salmon_icon_path:
        filename = _safe_attachment_filename(salmon_icon_path, prefix="salmon")
        embed.set_footer(text="SALMON RUN", icon_url=f"attachment://{filename}")
        if filename not in files_by_name:
            files_by_name[filename] = discord.File(salmon_icon_path, filename=filename)

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
    embed.set_author(name="バイトチームコンテスト情報")
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

@bot.command()
async def now(ctx):
    """/now で現在のステージを通知"""
    await _send_stage_embed(ctx, schedule_index=0, title="現在のステージ情報")

@bot.command(name="next")
async def next_stage(ctx):
    """/next で次のステージを通知"""
    await _send_stage_embed(ctx, schedule_index=1, title="つぎのステージ情報")

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

@bot.tree.command(name="salmon", description="現在のサーモンランを表示します")
async def salmon_slash(interaction: discord.Interaction):
    embed, files, error = _get_salmon_payload()
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="team_contest", description="バイトチームコンテストを表示します")
async def team_contest_slash(interaction: discord.Interaction):
    embed, files, error = _get_team_contest_payload()
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message(embed=embed, files=files)

@bot.tree.command(name="notify_here", description="ステージ自動通知の送信先をこのチャンネルに設定します")
async def notify_here_slash(interaction: discord.Interaction):
    state = _load_state()
    if interaction.channel_id is None:
        await interaction.response.send_message("この場所では設定できません。", ephemeral=True)
        return
    state["stage_notify_channel_id"] = int(interaction.channel_id)
    _save_state(state)
    await interaction.response.send_message("このチャンネルをステージ自動通知の送信先に設定しました。", ephemeral=True)

@bot.tree.command(name="notify_test", description="ステージ自動通知をテスト送信します")
async def notify_test_slash(interaction: discord.Interaction):
    embeds, files, error = _get_stage_payload(schedule_index=0, title_prefix="現在のステージ情報")
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    await interaction.response.send_message("送信します。", ephemeral=True)
    await interaction.channel.send(embeds=embeds, files=files)

_did_sync_app_commands = False

@tasks.loop(minutes=1)
async def _stage_auto_notify_loop():
    state = _load_state()
    channel_id = int(state.get("stage_notify_channel_id") or STAGE_NOTIFY_CHANNEL_ID or 0)
    if not channel_id:
        return

    data = get_stages()
    if not data:
        return

    rotation_key = _get_stage_rotation_key(data)
    if not rotation_key:
        return

    last_key = state.get("stage_last_rotation_key")
    if last_key is None:
        state["stage_last_rotation_key"] = rotation_key
        _save_state(state)
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
    await channel.send(embeds=embeds, files=files)

    state["stage_last_rotation_key"] = rotation_key
    _save_state(state)

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

if __name__ == "__main__":
    if not os.getenv("DISCORD_TOKEN"):
        _load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "")
    if not token:
        raise RuntimeError("環境変数 DISCORD_TOKEN に Discord Bot Token を設定してください。")

    bot.run(token)
