import discord
import random
import json
import os
import datetime
from collections import deque
from config import TOKEN
from discord import app_commands
from discord.ui import View, Button

WELCOME_CHANNEL_ID = 1417152242817044550
GOODBYE_CHANNEL_ID = 1417152314476859422
BOOST_CHANNEL_ID = 1417152381291860118
BOOSTER_ROLE_ID = 1437740399786459247    
AUTO_ROLE_ID = 1438899323336130802
RULES_CHANNEL_ID = 1459140957932093652
LEVEL_UP_CHANNEL_ID = 1467701484102619257  # GANTI ke channel rank-up

LEVEL_ROLES = {
    5: 1467711658934927461,   # GANTI ID role
    10: 1467711802870599946,
    20: 1467711915177541847,
    30: 1467712000367792330,
    40: 1467712170119921908,
    60: 1467712247987179581,
    75: 1467712305323184172,
    85: 1467712397807587452,
    100: 1467712463435989068

}

BADGES = {
    5: "🥉 Bocil Baru",
    10: "🥈 Tukang Ngobrol",
    20: "🥇 Anak Voice",
    30: "🎮 Anak Mabar",
    40: "🔥 warga asli",
    60: "💎 Sesepuh",
    75: "👑 Penguasa Tongkrongan",
    85: "🐐 Sepuh Abadi",
    100: "🐐 GOAT"

}

XP_FILE = "xp_data.json"
DAILY_XP = 50

voice_join_time = {}
daily_claims = {}
last_message_time = {}
XP_COOLDOWN = 60  # detik

spam_records = {}            # user_id -> deque of timestamps
SPAM_WINDOW = 10             # detik jendela waktu untuk hitung spam
SPAM_THRESHOLD = 5           # jumlah pesan dalam SPAM_WINDOW dianggap spam

if os.path.exists(XP_FILE):
    with open(XP_FILE, "r") as f:
        xp_data = json.load(f)
else:
    xp_data = {}

def save_xp():
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f)

# ================= FIXED BUTTON ROLE =================

class RoleButton(discord.ui.Button):
    def __init__(self, label: str, role_id: int, custom_id: str):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=custom_id
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)

        if role is None:
            await interaction.response.send_message("Role tidak ditemukan.", ephemeral=True)
            return

        member = interaction.user

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"❌ Role **{role.name}** dihapus dari kamu.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Role **{role.name}** berhasil diberikan!", ephemeral=True)


class RolePanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleButton("Mobile Legends", 1449602863687794789, "role_ml"))
        self.add_item(RoleButton("Among Us", 1449603295046930443, "role_among"))
        self.add_item(RoleButton("Roblox", 1449603377150562354, "role_roblox"))


class LeaderboardView(View):
    def __init__(self, author_id: int, guild: discord.Guild, sorted_users, per_page: int = 10):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.guild = guild
        self.per_page = per_page
        self.entries = []
        self.page = 0
        self.message = None

        rank_no = 1
        for user_id, data in sorted_users:
            member = guild.get_member(int(user_id))
            if not member:
                continue
            level = data["level"]
            xp = data["xp"]
            badge = BADGES.get(level, "Pemula")
            self.entries.append((rank_no, member, level, xp, badge))
            rank_no += 1

        self.total_pages = max(1, (len(self.entries) + self.per_page - 1) // self.per_page)
        author_index = next((i for i, item in enumerate(self.entries) if item[1].id == self.author_id), None)
        if author_index is not None:
            self.page = author_index // self.per_page

        self._update_buttons()

    def _make_embed(self) -> discord.Embed:
        start = self.page * self.per_page
        end = start + self.per_page
        page_entries = self.entries[start:end]

        lines = []
        for rank_no, member, level, xp, badge in page_entries:
            marker = ">> " if member.id == self.author_id else ""
            lines.append(f"{marker}**#{rank_no}. {member.name}** - Level {level} | {xp} XP | {badge}")

        description = "\n".join(lines) if lines else "Belum ada data"
        embed = discord.Embed(
            title="Leaderboard Server",
            description=description,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Halaman {self.page + 1}/{self.total_pages} | Total user: {len(self.entries)}")
        return embed

    def _update_buttons(self):
        at_start = self.page <= 0
        at_end = self.page >= self.total_pages - 1
        self.first_page.disabled = at_start
        self.prev_page.disabled = at_start
        self.next_page.disabled = at_end
        self.last_page.disabled = at_end
        self.page_info.label = f"{self.page + 1}/{self.total_pages}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Tombol ini cuma buat yang jalankan command !top.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary, row=0)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_info(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary, row=0)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.page = self.total_pages - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

class Client(discord.Client):
    def __init__(self, *, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged on as {self.user}!')

        # Register persistent view DI SINI
        try:
            self.add_view(RolePanel())
            print("Persistent RolePanel loaded")
        except Exception as e:
            print("Gagal load RolePanel:", e)

        
        
    # ===== XP FUNCTION =====
    def add_xp(self, member, amount):
        user_id = str(member.id)

        if user_id not in xp_data:
            xp_data[user_id] = {"xp": 0, "level": 1}

        xp_data[user_id]["xp"] += amount
        level = xp_data[user_id]["level"]
        xp_needed = level * 100

        if xp_data[user_id]["xp"] >= xp_needed:
            xp_data[user_id]["xp"] -= xp_needed
            xp_data[user_id]["level"] += 1
            save_xp()
            return True

        save_xp()
        return False

    # ================= VOICE XP =================
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None:
            voice_join_time[member.id] = datetime.datetime.now()

        elif before.channel is not None and after.channel is None:
            if member.id in voice_join_time:
                join_time = voice_join_time.pop(member.id)
                duration = (datetime.datetime.now() - join_time).total_seconds()
                xp_earned = int(duration // 120)  # 2 menit = 1 XP

                if xp_earned > 0:
                    leveled_up = self.add_xp(member, xp_earned)

                    if leveled_up:
                        new_level = xp_data[str(member.id)]["level"]
                        channel = member.guild.get_channel(LEVEL_UP_CHANNEL_ID)

                        if channel:
                            embed = discord.Embed(
                                title="🎉 LEVEL UP!",
                                description=f"{member.mention} naik ke **Level {new_level}** 🔥 (Voice Activity)",
                                color=discord.Color.gold()
                            )
                            await channel.send(embed=embed)

                        if new_level in LEVEL_ROLES:
                            role = member.guild.get_role(LEVEL_ROLES[new_level])
                            if role:
                                try:
                                    await member.add_roles(role)
                                except:
                                    pass

    # ================= WELCOME =================
    async def on_member_join(self, member):
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

        if channel:
            embed = discord.Embed(
                title="🎉 WELCOME!",
                description=f"Halo {member.mention}, selamat datang di **{member.guild.name}**!",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_image(url="https://i.imgur.com/OfeFMXC.png")

            await channel.send(embed=embed)

        role = member.guild.get_role(AUTO_ROLE_ID)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print("Tidak punya izin kasih role")

        try:
            await member.send(f"Hai {member.name}, selamat datang di {member.guild.name}! 🎊")
        except:
            pass

        rules_channel = member.guild.get_channel(RULES_CHANNEL_ID)

        if rules_channel:
            try:
                embed = discord.Embed(
                    title=f"Selamat datang di {member.guild.name} 🎉",
                    description=(
                        f"Halo {member.name}! Senang kamu bergabung 💖\n\n"
                        f"📜 Sebelum mulai, wajib baca rules server ya:\n"
                        f"👉 {rules_channel.mention}\n\n"
                        f"Semoga betah dan have fun! di Dpnp 🎮✨"
                    ),
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)

                await member.send(embed=embed)
            except:
                print(f"Gagal kirim DM ke {member.name}")

    # ================= GOODBYE =================
    async def on_member_remove(self, member):
        channel = member.guild.get_channel(GOODBYE_CHANNEL_ID)

        if channel:
            embed = discord.Embed(
                title="👋 GOODBYE!",
                description=f"{member.name} telah keluar dari **{member.guild.name}**.\nSemoga kita ketemu lagi ya!",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_image(url="https://i.imgur.com/k3II9KX.jpeg")

            await channel.send(embed=embed)
              
        try:
            dm_embed = discord.Embed(
                title="Terima kasih sudah pernah jadi bagian dari kami 🤍",
                description=(
                    f"Hai {member.name},\n\n"
                    f"Terima kasih sudah pernah bergabung di **{member.guild.name}**.\n"
                    f"Semoga betah di tempat baru dan semoga hal-hal baik selalu datang ke kamu.\n\n"
                    f"Pintu kami selalu terbuka kalau suatu saat mau kembali ✨"
                ),
                color=discord.Color.dark_blue()
            )
            dm_embed.set_footer(text="Salam dari komunitas DPNP")

            await member.send(embed=dm_embed)

        except discord.Forbidden:
            # User menutup DM dari server
            print(f"Tidak bisa kirim DM ke {member.name}")

    # ================= Booster =================
    async def on_member_update(self, before, after):
        # Seseorang baru saja boost
        if before.premium_since is None and after.premium_since is not None:
            channel = after.guild.get_channel(BOOST_CHANNEL_ID)

            if channel:
                embed = discord.Embed(
                    title="🚀 SERVER BOOST!",
                    description=f"Terima kasih {after.mention} sudah boost **{after.guild.name}**! 💜",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Total Boost Server", value=after.guild.premium_subscription_count)
                embed.set_thumbnail(url=after.display_avatar.url)

                await channel.send(embed=embed)

            # 🎁 Kasih role Booster
            role = after.guild.get_role(BOOSTER_ROLE_ID)
            if role:
                try:
                    await after.add_roles(role)
                except discord.Forbidden:
                    print("Tidak punya izin kasih role booster")

            # 💌 Kirim DM ke booster
            try:
                await after.send(f"Terima kasih sudah boost {after.guild.name}! Kamu dapat role spesial 💜")
            except:
                pass

        # Server naik level boost
        if before.guild.premium_tier < after.guild.premium_tier:
            channel = after.guild.get_channel(BOOST_CHANNEL_ID)
            if channel:
                await channel.send(
                    f"@everyone 🎉 Server naik ke **LEVEL {after.guild.premium_tier}** berkat para booster! Terima kasih 💜"
              )


    # ================= COMMAND =================
    async def on_message(self, message):
        if message.author == self.user:
            return
        
        # Skip semua bot
        if message.author.bot:
            return

        msg = message.content.lower()
        
        # ===== XP SYSTEM CHAT =====
        now = datetime.datetime.now().timestamp()
        last_time = last_message_time.get(message.author.id, 0)
        
        # Deteksi kata rahasia
        secret_word_detected = "bran baik dan ganteng" in message.content.lower()
        xp_multiplier = 2 if secret_word_detected else 1

        if now - last_time >= XP_COOLDOWN:
            last_message_time[message.author.id] = now

            xp_gain = random.randint(5, 15) * xp_multiplier
            leveled_up = self.add_xp(message.author, xp_gain)

            if leveled_up:
                new_level = xp_data[str(message.author.id)]["level"]
                channel = message.guild.get_channel(LEVEL_UP_CHANNEL_ID)

                if channel:
                    embed = discord.Embed(
                        title="🎉 LEVEL UP!",
                        description=f"{message.author.mention} naik ke **Level {new_level}** 🔥",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)

                if new_level in LEVEL_ROLES:
                    role = message.guild.get_role(LEVEL_ROLES[new_level])
                    if role:
                        try:
                            await message.author.add_roles(role)
                        except:
                            pass

        if msg == '!halo':
            await message.channel.send('Halo juga! 👋')
        
        elif msg == '!pagi':
            await message.channel.send('morning jga udh sarapan blm')
        
        elif msg == '!turu':
            await message.channel.send('tidur ya jaga kesehatan mu')

        elif msg == '!ping':
            await message.channel.send('Pong! 🏓')

        elif msg == '!among':
            await message.channel.send('@everyone  Ayo Among Us!')

        elif msg == '!roblox':
            await message.channel.send('@everyone  Langsung aja Roblox!')

        elif msg == '!yuka':
            await message.channel.send('hallo kak cantik gmn kabarnya')
        
        elif msg == '!ryan':
            await message.channel.send('Hallo Ganteng')
        
        elif msg == '!kiwi':
            await message.channel.send('Apeeeeeeeeee')
        
        elif msg == '!ml':
            await message.channel.send('@everyone  Langsung aja ml yg mau ikut!')

        elif msg == '!gg':
            await message.channel.send('infokan mancing fish it')

        elif msg == '!brann':
            await message.channel.send('Hallo owner baik dan ganteng')
        
        elif msg == '!king':
            await message.channel.send('diatas owner masih ada king')

        elif msg == '!maul':
            await message.channel.send('maul berak celana di sekolah')
        
        elif msg == '!yeay':
            await message.channel.send('adik terbaik sedipienpi ')

        elif msg == '!wann':
            await message.channel.send('wann Login ada yang mau minta gendong tuh')

        elif msg == '!itik':
            await message.channel.send('info roblox/ml  brannn')

        elif msg == '!putra':
            await message.channel.send('ytta')

        elif msg == '!diyana':
            await message.channel.send('Apakabar anak anak absen dlu satu satu')
        
        elif msg == '!bii':
            await message.channel.send('Hallo my Kisah 📖')
        
        elif msg == '!melar':
            await message.channel.send('di sok sok an lu')
        
        elif msg == '!caci':
            await message.channel.send('iri bilang boss')
          
        elif msg == '!mile':
            await message.channel.send('Ketua gengster, bikin gemeter🫦🫦')
        
        elif msg == '!wahyu':
            await message.channel.send('sehat sehat all, banyak olahraga')
        
        elif msg == '!natan':
            await message.channel.send('jarvis apakan dlu le biar ga apa kali')
        
        elif msg == '!amour':
            await message.channel.send('infokan among us gais')
        
        elif msg == '!malam':
            await message.channel.send('@everyone good night guys, mimpi indah semoga sehat selalu,  mimpiin aku yaaa')
        
        elif msg == '!rin':
            await message.channel.send('omakkkkk')
        
        elif msg == '!jikan':
            await message.channel.send('p info voice yg girls')
        
        elif msg == '!vann':
            await message.channel.send('pria ganteng idaman 😘😘😘')
        
        elif msg.startswith('!profile'):
            member = message.mentions[0] if message.mentions else message.author

            roles = [role.mention for role in member.roles if role.name != "@everyone"]
            roles_text = ", ".join(roles) if roles else "Tidak punya role"

            embed = discord.Embed(
                title=f"👤 Profil {member.name}",
                color=member.color if member.color != discord.Color.default() else discord.Color.blue()
            )

            embed.set_thumbnail(url=member.display_avatar.url)
            level = xp_data.get(str(member.id), {}).get("level", 1)
            badge = BADGES.get(level, "Pemula")

            embed.add_field(name="🏅 Badge", value=badge, inline=False)
            embed.add_field(name="⭐ Level", value=level, inline=False)
            embed.add_field(name="🆔 User ID", value=member.id, inline=False)
            embed.add_field(name="📛 Username", value=member.name, inline=False)
            embed.add_field(name="📅 Akun Dibuat", value=member.created_at.strftime("%d %B %Y"), inline=False)
            embed.add_field(name="📆 Gabung Server", value=member.joined_at.strftime("%d %B %Y"), inline=False)
            embed.add_field(name="🎭 Roles", value=roles_text, inline=False)

            await message.channel.send(embed=embed)

        elif msg.startswith('!kiss'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = random.choice([
                    "https://media1.tenor.com/m/1fNT0SY5cjwAAAAd/nene-nene-amano.gif",
                    "https://media1.tenor.com/m/Fvwt33eN3hUAAAAC/anime-cute.gif",
                    "https://media1.tenor.com/m/iDQT9BjSSXsAAAAC/kimsoohyun-kimjiwon.gif"
                ])
                embed = discord.Embed(
                    description=f"{message.author.mention} mencium {target.mention} 😘",
                    color=discord.Color.pink()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg.startswith('!slap'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = random.choice([
                    "https://media1.tenor.com/m/bO1H2Zv_5doAAAAC/mai-mai-san.gif",
                    "https://media1.tenor.com/m/WYmal-WAnksAAAAd/yuzuki-mizusaka-nonoka-komiya.gif"
                ])
                embed = discord.Embed(
                    description=f"{message.author.mention} menampar {target.mention} 🖐️",
                    color=discord.Color.red()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg.startswith('!hug'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = "https://media1.tenor.com/m/G_IvONY8EFgAAAAC/aharen-san-anime-hug.gif"
                embed = discord.Embed(
                    description=f"{message.author.mention} memeluk {target.mention} 🤗",
                    color=discord.Color.green()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg.startswith('!bite'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = "https://c.tenor.com/8YpRZ4H7dWkAAAAC/anime-bite.gif"
                embed = discord.Embed(
                    description=f"{message.author.mention} menggigit {target.mention} 😈",
                    color=discord.Color.orange()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg.startswith('!pat'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = "https://c.tenor.com/LUqLUEvFZ8kAAAAC/anime-head-pat.gif"
                embed = discord.Embed(
                    description=f"{message.author.mention} menepuk kepala {target.mention} 🥰",
                    color=discord.Color.blurple()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg.startswith('!kill'):
            if message.mentions:
                target = message.mentions[0]
                gif_url = random.choice([
                    "https://media.tenor.com/HqHu-BqxJUEAAAAi/anime-xd.gif",
                    "https://media1.tenor.com/m/230mTazmYVYAAAAC/anime-anime-boy.gif"
                ])
                embed = discord.Embed(
                    description=f"{message.author.mention} menyerang {target.mention} ⚔️",
                    color=discord.Color.dark_red()
                )
                embed.set_image(url=gif_url)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("Tag orangnya dulu ya 😉")

        elif msg == '!daily':
            today = datetime.date.today()
            last_claim = daily_claims.get(message.author.id)

            if last_claim == today:
                await message.channel.send("Kamu sudah ambil daily XP hari ini 🎁")
            else:
                daily_claims[message.author.id] = today
                self.add_xp(message.author, DAILY_XP)
                await message.channel.send(f"🎁 Kamu dapat {DAILY_XP} XP hari ini!")

        elif msg == '!top':
            # Sort semua user berdasarkan level (tertinggi) lalu XP (tertinggi)
            sorted_users = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)

            view = LeaderboardView(message.author.id, message.guild, sorted_users, per_page=10)
            sent_message = await message.channel.send(embed=view._make_embed(), view=view)
            view.message = sent_message

        elif msg.startswith('!rank'):
            member = message.mentions[0] if message.mentions else message.author
            user_id = str(member.id)
            
            if user_id not in xp_data:
                await message.channel.send(f"{member.mention} belum punya data XP 📊")
                return
            
            data = xp_data[user_id]
            level = data["level"]
            current_xp = data["xp"]
            xp_needed = level * 100
            
            # Hitung progress bar
            progress_percent = int((current_xp / xp_needed) * 100) if xp_needed > 0 else 0
            filled = "█" * (progress_percent // 10)
            empty = "░" * (10 - (progress_percent // 10))
            progress_bar = f"{filled}{empty} {progress_percent}%"
            
            badge = BADGES.get(level, "Pemula")
            
            # Hitung rank di leaderboard
            sorted_users = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
            rank = 1
            for idx, (uid, udata) in enumerate(sorted_users, start=1):
                if uid == user_id:
                    rank = idx
                    break
            
            embed = discord.Embed(
                title=f"📊 Rank {member.name}",
                color=member.color if member.color != discord.Color.default() else discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="🏆 Ranking Global", value=f"#{rank} dari {len(xp_data)}", inline=False)
            embed.add_field(name="🏅 Badge", value=badge, inline=False)
            embed.add_field(name="⭐ Level", value=level, inline=False)
            embed.add_field(name="✨ XP Progress", value=f"{current_xp} / {xp_needed} XP", inline=False)
            embed.add_field(name="📈 Progress Bar", value=progress_bar, inline=False)
            
            await message.channel.send(embed=embed)


        # ===== Spam Detection =====
        now_ts = datetime.datetime.now().timestamp()
        dq = spam_records.setdefault(message.author.id, deque())
        dq.append(now_ts)
        # hapus timestamp yang lebih tua dari window
        while dq and now_ts - dq[0] > SPAM_WINDOW:
            dq.popleft()

        if len(dq) >= SPAM_THRESHOLD:
            try:
                await message.channel.send(f"Hey {message.author.mention}, tolong jangan spam dong 🙏, Berisik Ganggu gw lagi Drakoran")
            except:
                pass
            dq.clear()
            return


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

client = Client(intents=intents)
# ===== SLASH COMMAND KIRIM PANEL ROLE =====
@client.tree.command(name="rolepanel", description="Kirim panel ambil role")
async def rolepanel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🎮 **Ambil Role Disini**\nKlik tombol di bawah untuk ambil atau hapus role kamu:",
        view=RolePanel()
    )
client.run(TOKEN)

