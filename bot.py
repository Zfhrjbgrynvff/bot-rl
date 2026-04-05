import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN          = "TON_TOKEN_ICI"   # ← Remplace par ton token Discord
QUEUE_CHANNEL_NAME = "6man-queue"
LOG_CHANNEL_NAME   = "6man-logs"
MAX_PLAYERS        = 6
ELO_FILE           = "elo_data.json"

# ── Paramètres ELO ────────────────────────────────────────────────────────────
ELO_DEFAULT = 800
ELO_K       = 32

# ── Rangs (C3 = débutant, A1 = élite, SSL = légende) ─────────────────────────
RANKS = [
    (0,    "🔵 C3",  0x5B8DD9),
    (200,  "🔵 C2",  0x4A7BC8),
    (400,  "🔵 C1",  0x3A6AB7),
    (600,  "🟣 B3",  0x8B5CF6),
    (800,  "🟣 B2",  0x7C3AED),
    (1000, "🟣 B1",  0x6D28D9),
    (1200, "🟡 A3",  0xF59E0B),
    (1500, "🟡 A2",  0xD97706),
    (1800, "🟡 A1",  0xB45309),
    (2200, "🏆 SSL", 0xFF4500),
]

def get_rank(elo: int) -> tuple[str, int]:
    rank_label, rank_color = RANKS[0][1], RANKS[0][2]
    for threshold, label, color in RANKS:
        if elo >= threshold:
            rank_label, rank_color = label, color
    return rank_label, rank_color

def get_next_rank(elo: int):
    for threshold, label, _ in RANKS:
        if elo < threshold:
            return threshold, label
    return None

# ══════════════════════════════════════════════════════════════════════════════
# PERSISTANCE ELO
# ══════════════════════════════════════════════════════════════════════════════

def load_elo() -> dict:
    if os.path.exists(ELO_FILE):
        with open(ELO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_elo(data: dict):
    with open(ELO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_player(user_id: int) -> dict:
    uid = str(user_id)
    if uid not in elo_db:
        elo_db[uid] = {
            "elo": ELO_DEFAULT, "wins": 0, "losses": 0,
            "matches": 0, "streak": 0, "peak_elo": ELO_DEFAULT, "history": [],
        }
        save_elo(elo_db)
    return elo_db[uid]

def expected_score(elo_a: float, elo_b: float) -> float:
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

def compute_elo_changes(team_a: list, team_b: list, winner: str) -> dict:
    avg_a = sum(get_player(p.id)["elo"] for p in team_a) / len(team_a)
    avg_b = sum(get_player(p.id)["elo"] for p in team_b) / len(team_b)
    ea = expected_score(avg_a, avg_b)
    eb = 1 - ea
    score_a = 1 if winner == "a" else 0
    score_b = 1 - score_a
    changes = {}
    for player in team_a:
        old = get_player(player.id)["elo"]
        delta = round(ELO_K * (score_a - ea))
        changes[player.id] = {"old": old, "new": old + delta, "delta": delta, "won": winner == "a"}
    for player in team_b:
        old = get_player(player.id)["elo"]
        delta = round(ELO_K * (score_b - eb))
        changes[player.id] = {"old": old, "new": old + delta, "delta": delta, "won": winner == "b"}
    return changes

def apply_elo_changes(changes: dict, players: list):
    for player in players:
        uid = str(player.id)
        ch  = changes[player.id]
        p   = get_player(player.id)
        p["elo"]      = ch["new"]
        p["matches"] += 1
        p["peak_elo"] = max(p["peak_elo"], ch["new"])
        if ch["won"]:
            p["wins"]  += 1
            p["streak"] = max(0, p["streak"]) + 1
        else:
            p["losses"] += 1
            p["streak"]  = min(0, p["streak"]) - 1
        p["history"].append(ch["delta"])
        p["history"] = p["history"][-10:]
        elo_db[uid] = p
    save_elo(elo_db)

elo_db = load_elo()

# ══════════════════════════════════════════════════════════════════════════════
# BOT
# ══════════════════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

queue:         list[discord.Member]      = []
queue_message: Optional[discord.Message] = None
active_match:  Optional[dict]            = None

# ══════════════════════════════════════════════════════════════════════════════
# EMBEDS
# ══════════════════════════════════════════════════════════════════════════════

def build_queue_embed() -> discord.Embed:
    filled = len(queue)
    bar    = "🟦" * filled + "⬜" * (MAX_PLAYERS - filled)
    lines  = []
    for i, p in enumerate(queue):
        prof = get_player(p.id)
        rank, _ = get_rank(prof["elo"])
        lines.append(f"`{i+1}.` {p.display_name} — {rank} **{prof['elo']}**")
    players_str = "\n".join(lines) or "*Aucun joueur pour l'instant…*"
    embed = discord.Embed(
        title="🚀 File 6-Man — Rocket League",
        description=f"**{filled}/{MAX_PLAYERS}** joueurs\n{bar}",
        color=0x00BFFF, timestamp=datetime.utcnow(),
    )
    embed.add_field(name="👥 Joueurs dans la file", value=players_str, inline=False)
    if filled == MAX_PLAYERS:
        embed.add_field(name="✅ File pleine !", value="Lancement du tirage…", inline=False)
        embed.color = 0x00FF7F
    embed.set_footer(text="✅ Rejoindre • ❌ Quitter • 📋 Liste")
    return embed

def build_match_embed(orange: list, blue: list, map_name: str) -> discord.Embed:
    def team_str(team):
        return "\n".join(
            f"• **{p.display_name}** {get_rank(get_player(p.id)['elo'])[0]} `{get_player(p.id)['elo']}`"
            for p in team
        )
    avg_o = round(sum(get_player(p.id)["elo"] for p in orange) / len(orange))
    avg_b = round(sum(get_player(p.id)["elo"] for p in blue)   / len(blue))
    ea    = round(expected_score(avg_o, avg_b) * 100)
    embed = discord.Embed(title="⚽ Match lancé !", color=0xFFA500, timestamp=datetime.utcnow())
    embed.add_field(name=f"🟠 Équipe Orange (avg {avg_o})", value=team_str(orange), inline=True)
    embed.add_field(name=f"🔵 Équipe Bleue (avg {avg_b})",  value=team_str(blue),   inline=True)
    embed.add_field(name="🗺️ Map", value=f"`{map_name}`", inline=False)
    embed.add_field(
        name="📊 Proba de victoire",
        value=f"🟠 Orange : **{ea}%** | 🔵 Bleue : **{100-ea}%**",
        inline=False,
    )
    embed.set_footer(text="GG ! • /win orange | /win blue pour reporter le résultat")
    return embed

def build_result_embed(winner_team: str, orange: list, blue: list, changes: dict) -> discord.Embed:
    emoji = "🟠" if winner_team == "orange" else "🔵"
    color = 0xFF8C00 if winner_team == "orange" else 0x1E90FF

    def delta_str(member):
        ch = changes[member.id]
        arrow = "▲" if ch["delta"] >= 0 else "▼"
        sign  = "+" if ch["delta"] >= 0 else ""
        rank, _ = get_rank(ch["new"])
        return f"• **{member.display_name}** {rank} `{ch['old']} → {ch['new']}` ({sign}{ch['delta']} {arrow})"

    embed = discord.Embed(
        title=f"{emoji} Victoire de l'équipe {winner_team.capitalize()} !",
        color=color, timestamp=datetime.utcnow(),
    )
    embed.add_field(name="🟠 Équipe Orange", value="\n".join(delta_str(p) for p in orange), inline=False)
    embed.add_field(name="🔵 Équipe Bleue",  value="\n".join(delta_str(p) for p in blue),   inline=False)

    for p in orange + blue:
        prof = get_player(p.id)
        if prof["streak"] >= 3:
            embed.add_field(
                name="🔥 Win Streak !",
                value=f"**{p.display_name}** est sur **{prof['streak']}** victoires consécutives !",
                inline=False,
            )
            break

    embed.set_footer(text="ELO mis à jour • /rank pour voir ton profil")
    return embed

def build_rank_embed(member: discord.Member) -> discord.Embed:
    prof = get_player(member.id)
    elo  = prof["elo"]
    rank, color = get_rank(elo)
    next_r = get_next_rank(elo)
    winrate = round(prof["wins"] / prof["matches"] * 100) if prof["matches"] else 0

    streak_label = ""
    if prof["streak"] >= 3:
        streak_label = f"🔥 Win streak ×{prof['streak']}"
    elif prof["streak"] <= -3:
        streak_label = f"💀 Lose streak ×{abs(prof['streak'])}"

    history_str = " ".join(
        (f"**+{d}**" if d >= 0 else f"**{d}**") for d in prof["history"][-5:]
    ) or "Aucun match"

    embed = discord.Embed(title=f"🎮 Profil de {member.display_name}", color=color, timestamp=datetime.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏅 Rang",           value=rank,                  inline=True)
    embed.add_field(name="📈 ELO",            value=f"**{elo}**",          inline=True)
    embed.add_field(name="🏆 Peak ELO",       value=f"`{prof['peak_elo']}`", inline=True)
    embed.add_field(name="✅ Victoires",      value=f"`{prof['wins']}`",   inline=True)
    embed.add_field(name="❌ Défaites",       value=f"`{prof['losses']}`", inline=True)
    embed.add_field(name="🎯 Win Rate",       value=f"`{winrate}%`",       inline=True)
    embed.add_field(name="🕹️ Matchs joués",   value=f"`{prof['matches']}`", inline=True)
    if streak_label:
        embed.add_field(name="⚡ Série",      value=streak_label,          inline=True)
    if next_r:
        embed.add_field(
            name="⬆️ Prochain rang",
            value=f"{next_r[1]} dans **{next_r[0] - elo}** ELO",
            inline=False,
        )
    embed.add_field(name="📊 Historique récent", value=history_str, inline=False)
    return embed

def build_leaderboard_embed(guild: discord.Guild, page: int = 0) -> discord.Embed:
    per_page = 10
    sorted_players = sorted(
        [(uid, d) for uid, d in elo_db.items() if d["matches"] > 0],
        key=lambda x: x[1]["elo"], reverse=True,
    )
    total  = len(sorted_players)
    pages  = max(1, (total + per_page - 1) // per_page)
    page   = max(0, min(page, pages - 1))
    slice_ = sorted_players[page * per_page: (page + 1) * per_page]

    medals = ["🥇", "🥈", "🥉"]
    lines  = []
    for i, (uid, data) in enumerate(slice_):
        pos    = page * per_page + i
        prefix = medals[pos] if pos < 3 else f"`{pos+1}.`"
        member = guild.get_member(int(uid))
        name   = member.display_name if member else f"Joueur ({uid})"
        rank, _ = get_rank(data["elo"])
        wr     = round(data["wins"] / data["matches"] * 100) if data["matches"] else 0
        lines.append(f"{prefix} **{name}** — {rank} `{data['elo']}` | {data['wins']}W/{data['losses']}L ({wr}%)")

    embed = discord.Embed(
        title="🏆 Classement ELO — 6-Man RL",
        description="\n".join(lines) or "*Aucun match joué pour l'instant.*",
        color=0xFFD700, timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=f"Page {page+1}/{pages} • {total} joueurs classés")
    return embed

# ══════════════════════════════════════════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Rejoindre", style=discord.ButtonStyle.success, custom_id="join_queue")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_join(interaction)

    @discord.ui.button(label="❌ Quitter", style=discord.ButtonStyle.danger, custom_id="leave_queue")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave(interaction)

    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.secondary, custom_id="list_queue")
    async def list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        players_str = "\n".join(f"{i+1}. {p.display_name}" for i, p in enumerate(queue)) or "Aucun joueur."
        await interaction.response.send_message(
            f"**File actuelle ({len(queue)}/{MAX_PLAYERS}) :**\n{players_str}", ephemeral=True,
        )

class LeaderboardView(discord.ui.View):
    def __init__(self, guild: discord.Guild, page: int = 0):
        super().__init__(timeout=60)
        self.guild = guild
        self.page  = page

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await interaction.response.edit_message(embed=build_leaderboard_embed(self.guild, self.page), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await interaction.response.edit_message(embed=build_leaderboard_embed(self.guild, self.page), view=self)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def log(guild: discord.Guild, message: str):
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if channel:
        await channel.send(f"📋 {message}")

async def refresh_panel(channel: discord.TextChannel):
    global queue_message
    embed = build_queue_embed()
    view  = QueueView()
    if queue_message:
        try:
            await queue_message.edit(embed=embed, view=view)
            return
        except discord.NotFound:
            queue_message = None
    queue_message = await channel.send(embed=embed, view=view)
    try:
        await queue_message.pin()
    except discord.Forbidden:
        pass

async def start_match(guild: discord.Guild, channel: discord.TextChannel):
    global queue, active_match
    players = queue.copy()
    # Snake draft par ELO pour équipes équilibrées
    players.sort(key=lambda p: get_player(p.id)["elo"], reverse=True)
    orange, blue = [], []
    for i, p in enumerate(players):
        (orange if i % 4 in (0, 3) else blue).append(p)

    maps = [
        "DFH Stadium", "Mannfield", "Champions Field",
        "Neo Tokyo", "Wasteland", "Aquadome",
        "Beckwith Park", "Utopia Coliseum", "Forbidden Temple", "Salty Shores",
    ]
    chosen_map   = random.choice(maps)
    active_match = {"orange": orange, "blue": blue, "map": chosen_map}
    queue.clear()

    await channel.send(embed=build_match_embed(orange, blue, chosen_map))
    await log(guild, f"Match lancé — Orange: {[p.display_name for p in orange]} | Blue: {[p.display_name for p in blue]} | Map: {chosen_map}")
    await asyncio.sleep(1)
    await refresh_panel(channel)

# ══════════════════════════════════════════════════════════════════════════════
# JOIN / LEAVE
# ══════════════════════════════════════════════════════════════════════════════

async def handle_join(interaction: discord.Interaction):
    global queue
    member = interaction.user
    if member in queue:
        return await interaction.response.send_message("⚠️ Tu es déjà dans la file !", ephemeral=True)
    if len(queue) >= MAX_PLAYERS:
        return await interaction.response.send_message("⚠️ La file est déjà pleine.", ephemeral=True)
    get_player(member.id)
    queue.append(member)
    prof = get_player(member.id)
    rank, _ = get_rank(prof["elo"])
    await interaction.response.send_message(
        f"✅ **{member.display_name}** ({rank} `{prof['elo']}`) a rejoint la file ! ({len(queue)}/{MAX_PLAYERS})",
        delete_after=6,
    )
    await log(interaction.guild, f"{member.display_name} a rejoint la file ({len(queue)}/{MAX_PLAYERS})")
    await refresh_panel(interaction.channel)
    if len(queue) >= MAX_PLAYERS:
        await asyncio.sleep(2)
        await start_match(interaction.guild, interaction.channel)

async def handle_leave(interaction: discord.Interaction):
    global queue
    member = interaction.user
    if member not in queue:
        return await interaction.response.send_message("⚠️ Tu n'es pas dans la file.", ephemeral=True)
    queue.remove(member)
    await interaction.response.send_message(
        f"👋 **{member.display_name}** a quitté la file. ({len(queue)}/{MAX_PLAYERS})", delete_after=5,
    )
    await log(interaction.guild, f"{member.display_name} a quitté la file ({len(queue)}/{MAX_PLAYERS})")
    await refresh_panel(interaction.channel)

# ══════════════════════════════════════════════════════════════════════════════
# COMMANDES SLASH
# ══════════════════════════════════════════════════════════════════════════════

@tree.command(name="join",  description="Rejoindre la file 6-man")
async def slash_join(interaction: discord.Interaction):
    await handle_join(interaction)

@tree.command(name="leave", description="Quitter la file 6-man")
async def slash_leave(interaction: discord.Interaction):
    await handle_leave(interaction)

@tree.command(name="queue", description="Afficher la file actuelle")
async def slash_queue(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_queue_embed(), ephemeral=True)

@tree.command(name="setup", description="[Admin] Créer le panneau de file dans ce salon")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_setup(interaction: discord.Interaction):
    await interaction.response.send_message("🔧 Création du panneau…", ephemeral=True)
    await refresh_panel(interaction.channel)

@tree.command(name="clear", description="[Admin] Vider la file")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_clear(interaction: discord.Interaction):
    global queue
    queue.clear()
    await interaction.response.send_message("🗑️ File vidée.")
    await refresh_panel(interaction.channel)
    await log(interaction.guild, f"File vidée par {interaction.user.display_name}")

@tree.command(name="kick", description="[Admin] Retirer un joueur de la file")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(membre="Le joueur à retirer")
async def slash_kick(interaction: discord.Interaction, membre: discord.Member):
    global queue
    if membre not in queue:
        return await interaction.response.send_message(f"⚠️ {membre.display_name} n'est pas dans la file.", ephemeral=True)
    queue.remove(membre)
    await interaction.response.send_message(f"🦵 **{membre.display_name}** retiré de la file.")
    await refresh_panel(interaction.channel)
    await log(interaction.guild, f"{membre.display_name} retiré par {interaction.user.display_name}")

@tree.command(name="add", description="[Admin] Ajouter un joueur à la file")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(membre="Le joueur à ajouter")
async def slash_add(interaction: discord.Interaction, membre: discord.Member):
    global queue
    if membre in queue:
        return await interaction.response.send_message(f"⚠️ {membre.display_name} est déjà dans la file.", ephemeral=True)
    if len(queue) >= MAX_PLAYERS:
        return await interaction.response.send_message("⚠️ La file est pleine.", ephemeral=True)
    get_player(membre.id)
    queue.append(membre)
    await interaction.response.send_message(f"➕ **{membre.display_name}** ajouté. ({len(queue)}/{MAX_PLAYERS})")
    await refresh_panel(interaction.channel)
    if len(queue) >= MAX_PLAYERS:
        await asyncio.sleep(2)
        await start_match(interaction.guild, interaction.channel)

@tree.command(name="shuffle", description="[Admin] Forcer un tirage")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_shuffle(interaction: discord.Interaction):
    if len(queue) < MAX_PLAYERS:
        return await interaction.response.send_message(f"⚠️ Il faut {MAX_PLAYERS} joueurs.", ephemeral=True)
    await interaction.response.send_message("🔀 Tirage en cours…")
    await start_match(interaction.guild, interaction.channel)

@tree.command(name="win", description="Reporter le résultat du match et mettre à jour les ELO")
@app_commands.describe(equipe="L'équipe gagnante")
@app_commands.choices(equipe=[
    app_commands.Choice(name="Orange 🟠", value="orange"),
    app_commands.Choice(name="Bleue 🔵",  value="blue"),
])
async def slash_win(interaction: discord.Interaction, equipe: app_commands.Choice[str]):
    global active_match
    if not active_match:
        return await interaction.response.send_message("⚠️ Aucun match actif.", ephemeral=True)
    orange  = active_match["orange"]
    blue    = active_match["blue"]
    winner  = equipe.value
    team_a  = orange if winner == "orange" else blue
    team_b  = blue   if winner == "orange" else orange
    changes = compute_elo_changes(team_a, team_b, "a")
    apply_elo_changes(changes, orange + blue)
    await interaction.response.send_message(embed=build_result_embed(winner, orange, blue, changes))
    winners_names = ", ".join(p.display_name for p in team_a)
    await log(interaction.guild, f"Match terminé — Vainqueur : {equipe.name} ({winners_names}) — ELO mis à jour")
    active_match = None

@tree.command(name="rank", description="Afficher ton profil ELO")
@app_commands.describe(membre="Le joueur dont tu veux voir le profil (optionnel)")
async def slash_rank(interaction: discord.Interaction, membre: Optional[discord.Member] = None):
    await interaction.response.send_message(embed=build_rank_embed(membre or interaction.user))

@tree.command(name="leaderboard", description="Classement ELO du serveur")
async def slash_leaderboard(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=build_leaderboard_embed(interaction.guild, 0),
        view=LeaderboardView(interaction.guild, 0),
    )

@tree.command(name="resetelo", description="[Admin] Réinitialiser l'ELO d'un joueur")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(membre="Le joueur à réinitialiser")
async def slash_resetelo(interaction: discord.Interaction, membre: discord.Member):
    elo_db[str(membre.id)] = {
        "elo": ELO_DEFAULT, "wins": 0, "losses": 0,
        "matches": 0, "streak": 0, "peak_elo": ELO_DEFAULT, "history": [],
    }
    save_elo(elo_db)
    await interaction.response.send_message(f"🔄 ELO de **{membre.display_name}** réinitialisé à `{ELO_DEFAULT}`.")
    await log(interaction.guild, f"ELO de {membre.display_name} réinitialisé par {interaction.user.display_name}")

@tree.command(name="setelo", description="[Admin] Définir manuellement l'ELO d'un joueur")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(membre="Le joueur", valeur="La nouvelle valeur ELO")
async def slash_setelo(interaction: discord.Interaction, membre: discord.Member, valeur: int):
    if valeur < 0:
        return await interaction.response.send_message("⚠️ L'ELO doit être positif.", ephemeral=True)
    prof = get_player(membre.id)
    prof["elo"]      = valeur
    prof["peak_elo"] = max(prof["peak_elo"], valeur)
    elo_db[str(membre.id)] = prof
    save_elo(elo_db)
    rank, _ = get_rank(valeur)
    await interaction.response.send_message(f"✏️ ELO de **{membre.display_name}** défini à `{valeur}` ({rank}).")
    await log(interaction.guild, f"ELO de {membre.display_name} → {valeur} par {interaction.user.display_name}")

# ══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    bot.add_view(QueueView())
    try:
        synced = await tree.sync()
        print(f"🔄 {len(synced)} commandes slash synchronisées.")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Permission refusée.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)

# ══════════════════════════════════════════════════════════════════════════════
bot.run(BOT_TOKEN)
