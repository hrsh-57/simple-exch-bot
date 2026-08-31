import os
import json
import datetime
import io
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ============================================================
# CONFIG
# ============================================================
COMMAND_PREFIX = "*"

SUPPORT_ROLE_ID = 1542484433402069003

# ---- Credit & Deliver system ----
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin")
CREDIT_TO_KEYS = 2  # 1 credit = this many stock items

CATEGORY_CONFIG = {
    "i2c": {
        "label": "INR — Crypto",
        "channel_prefix": "i2c",
        "discord_category_id": 1542497071213453362,
        "transcript_channel_id": 1542496878413746248,
        "questions": [
            "Which INR wallet are you using?",
            "Which Crypto wallet are you using?",
            "Amount to be Exchanged",
            "Are you using a third-party payment?",
            "Have you read our ToS?",
        ],
    },
    "c2i": {
        "label": "Crypto — INR",
        "channel_prefix": "c2i",
        "discord_category_id": 1542497183524454420,
        "transcript_channel_id": 1542496940367941702,
        "questions": [
            "Which Crypto wallet are you using?",
            "Which INR wallet are you using?",
            "Amount to be Exchanged",
            "Are you using a third-party payment?",
            "Have you read our ToS?",
        ],
    },
}

# Custom emojis (must exist on your server for these to render)
EMOJI_LIST = "<:frost_list:1542200905301098649>"
EMOJI_MART = "<:frost_mart:1541689796009926676>"
EMOJI_EXCH = "<:frost_exch:1542487530333667409>"
EMOJI_CAUTION = "<:frost_caution:1542183320673321020>"
EMOJI_DOT = "<:frost_dot:1542201046808404008>"
EMOJI_ANNOUNCE = "<:frost_announce:1541688634388910110>"
EMOJI_STOCK = "<:frost_stock:1542183452173148220>"
EMOJI_DOLLARS = "<:frost_dollars:1542184834758352916>"
EMOJI_LINK = "<:frost_link:1542199813700067399>"
EMOJI_INFO = "<:frost_info:1541688560103727155>"
EMOJI_STAR = "<:frost_star:1541688964342349825>"

# ---- SellAuth live stock panel ----
SELLAUTH_SHOP_ID = 0  # TODO: put your SellAuth shop ID here
SELLAUTH_SHOP_URL = "https://your-shop.mysellauth.com"  # TODO: your shop's base URL (no trailing slash)
STOCK_REFRESH_MINUTES = 5

INFO_LINKS = [
    (EMOJI_MART, "https://discord.gg/HmJ3nXRbJr"),
    ("<:frost_telegram:1542185600692781066>", "https://t.me/frostmartt"),
    ("<:frost_website:1542200495949615204>", "https://frostmart.netlify.app"),
]
FROST_OWNER_IDS = [1541264737562533958, 1525240197627777074]

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "store.json")

# ============================================================
# BOT SETUP
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# ============================================================
# PERSISTENT STORAGE
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "rates": {"i2c": 104, "c2i": 101},
            "panel_channel_id": None,
            "panel_message_id": None,
            "stock_channel_id": None,
            "stock_message_id": None,
            "credits": {},
            "stock": {},
        }
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    data.setdefault("credits", {})
    data.setdefault("stock", {})
    return data


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


store = load_data()


# ============================================================
# PANEL EMBED (rates + rules)
# ============================================================
def build_panel_embed() -> discord.Embed:
    rates = store["rates"]
    description = (
        f"{EMOJI_LIST} **__Live Exchange Rates__** {EMOJI_MART}\n\n"
        f"{EMOJI_EXCH} **INR — Crypto: `{rates['i2c']}/$`**\n"
        f"{EMOJI_EXCH} **Crypto — INR: `{rates['c2i']}/$`**\n\n"
        f"{EMOJI_CAUTION} **__Rules__**\n\n"
        f"-# {EMOJI_DOT} Be sure to reply instantly.\n"
        f"-# {EMOJI_DOT} Don't use third-party payments.\n"
        f"-# {EMOJI_DOT} Must check live exchange rates.\n"
        f"-# {EMOJI_DOT} Make sure to fill the form correctly."
    )
    embed = discord.Embed(description=description, color=discord.Color.dark_theme())
    return embed


async def refresh_panel_message():
    """Edits the live panel message (if one exists) after rates change."""
    channel_id = store.get("panel_channel_id")
    message_id = store.get("panel_message_id")
    if not channel_id or not message_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embed=build_panel_embed(), view=TicketPanelView())
    except discord.NotFound:
        pass


# ============================================================
# TICKET MODAL (form shown after selecting a category)
# ============================================================
class TicketModal(discord.ui.Modal):
    def __init__(self, category_key: str):
        config = CATEGORY_CONFIG[category_key]
        super().__init__(title=config["label"])
        self.category_key = category_key
        self.inputs = []
        for question in config["questions"]:
            text_input = discord.ui.TextInput(
                label=question[:45],  # Discord modal label limit
                style=discord.TextStyle.short,
                required=True,
                max_length=200,
            )
            self.inputs.append((question, text_input))
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        config = CATEGORY_CONFIG[self.category_key]
        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(
            guild.text_channels, name=f"{config['channel_prefix']}-{user.name}".lower()
        )
        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}", ephemeral=True
            )
            return

        category = guild.get_channel(config["discord_category_id"])
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"{config['channel_prefix']}-{user.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {user} ({config['label']})",
        )

        ping_line = f"{user.mention}"
        if support_role:
            ping_line += f" {support_role.mention}"

        fields_embed = discord.Embed(title=config["label"], color=discord.Color.blurple())
        for question, text_input in self.inputs:
            fields_embed.add_field(name=question, value=text_input.value or "—", inline=False)

        await channel.send(content=ping_line, embed=fields_embed, view=CloseTicketView(self.category_key))

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
        )


# ============================================================
# PANEL VIEW (dropdown that opens the modal)
# ============================================================
class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=cfg["label"], value=key)
            for key, cfg in CATEGORY_CONFIG.items()
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


# ============================================================
# CLOSE TICKET (transcript + delete)
# ============================================================
class CloseTicketView(discord.ui.View):
    def __init__(self, category_key: str):
        super().__init__(timeout=None)
        self.category_key = category_key
        button = discord.ui.Button(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            custom_id=f"close_ticket_{category_key}",
        )
        button.callback = self.close_ticket
        self.add_item(button)

    async def close_ticket(self, interaction: discord.Interaction):
        await interaction.response.send_message("Closing ticket and saving transcript...", ephemeral=True)

        config = CATEGORY_CONFIG[self.category_key]
        channel = interaction.channel

        lines = []
        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = msg.content or "[embed/attachment]"
            lines.append(f"[{timestamp}] {msg.author}: {content}")
        transcript_text = "\n".join(lines) if lines else "No messages."

        transcript_channel = bot.get_channel(config["transcript_channel_id"])
        if transcript_channel:
            file = discord.File(
                io.BytesIO(transcript_text.encode("utf-8")),
                filename=f"{channel.name}-transcript.txt",
            )
            embed = discord.Embed(
                title="Ticket Transcript",
                description=f"Channel: `#{channel.name}`\nCategory: {config['label']}",
                color=discord.Color.dark_grey(),
                timestamp=datetime.datetime.utcnow(),
            )
            await transcript_channel.send(embed=embed, file=file)

        await channel.delete(reason=f"Ticket closed by {interaction.user}")


# ============================================================
# SELLAUTH LIVE STOCK PANEL
# ============================================================
async def fetch_sellauth_products():
    """Fetches all products from the SellAuth API."""
    api_key = os.getenv("SELLAUTH_API_KEY")
    if not api_key:
        print("SELLAUTH_API_KEY environment variable is not set — skipping stock refresh.")
        return None

    url = f"https://api.sellauth.com/v1/shops/{SELLAUTH_SHOP_ID}/products"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"SellAuth API error {resp.status}: {await resp.text()}")
                return None
            data = await resp.json()
            # Some endpoints paginate under a "data" key — handle both shapes.
            return data.get("data", data) if isinstance(data, dict) else data


def build_stock_embeds(products) -> list[discord.Embed]:
    header = discord.Embed(
        description=f"{EMOJI_MART} **__Sellauth Live Panel__** {EMOJI_ANNOUNCE}",
        color=discord.Color.dark_theme(),
    )

    products_embed = discord.Embed(color=discord.Color.dark_theme())
    for product in products[:25]:  # Discord allows max 25 fields per embed
        name = product.get("name", "Unknown")

        price = product.get("price")
        currency = product.get("currency", "USD")
        stock = product.get("stock_count")

        # Variant-type products keep price/stock on each variant instead of the product itself.
        variants = product.get("variants") or []
        if price is None and variants:
            first_variant = variants[0]
            price = first_variant.get("price")
            stock = first_variant.get("stock_count", stock)

        price_text = price if price is not None else "N/A"
        stock_text = "Out of stock" if not stock else str(stock)
        path = product.get("path", "")
        link = f"{SELLAUTH_SHOP_URL}/product/{path}"

        value = (
            f"{EMOJI_STOCK} Stock: **{stock_text}**\n"
            f"{EMOJI_DOLLARS} Price: **{price_text} {currency}**\n"
            f"{EMOJI_LINK} Link: [Buy Here]({link})"
        )
        products_embed.add_field(name=f"{EMOJI_DOT} {name}", value=value, inline=True)

    info_lines = "\n".join(f"{emoji} {link}" for emoji, link in INFO_LINKS)
    owners = " ".join(f"<@{uid}>" for uid in FROST_OWNER_IDS)
    info_embed = discord.Embed(
        description=(
            f"-# This message updates automatically.\n\n"
            f"{EMOJI_INFO} **__Information__** {EMOJI_STAR}\n\n"
            f"{info_lines}\n\n"
            f"**__Frost Owners__** {EMOJI_MART}\n\n"
            f"{owners}"
        ),
        color=discord.Color.dark_theme(),
    )

    return [header, products_embed, info_embed]


async def refresh_stock_panel():
    channel_id = store.get("stock_channel_id")
    message_id = store.get("stock_message_id")
    if not channel_id or not message_id:
        return

    products = await fetch_sellauth_products()
    if products is None:
        return  # keep showing last successful data rather than wiping it

    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embeds=build_stock_embeds(products))
    except discord.NotFound:
        pass


@tasks.loop(minutes=STOCK_REFRESH_MINUTES)
async def stock_refresh_loop():
    await refresh_stock_panel()


@bot.command(name="stockpanel")
@commands.has_permissions(administrator=True)
async def stockpanel_command(ctx: commands.Context):
    """Sends the live SellAuth stock panel in this channel."""
    products = await fetch_sellauth_products()
    embeds = build_stock_embeds(products or [])
    message = await ctx.send(embeds=embeds)
    store["stock_channel_id"] = message.channel.id
    store["stock_message_id"] = message.id
    save_data(store)
    await ctx.message.delete()

    if not stock_refresh_loop.is_running():
        stock_refresh_loop.start()


@stockpanel_command.error
async def stockpanel_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Only admins can use this command.", delete_after=5)


# ============================================================
# ;setup COMMAND
# ============================================================
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_command(ctx: commands.Context):
    """Sends the ticket panel in this channel."""
    message = await ctx.send(embed=build_panel_embed(), view=TicketPanelView())
    store["panel_channel_id"] = message.channel.id
    store["panel_message_id"] = message.id
    save_data(store)
    await ctx.message.delete()


@setup_command.error
async def setup_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Only admins can use this command.", delete_after=5)


# ============================================================
# /update-rates SLASH COMMAND
# ============================================================
@bot.tree.command(name="update-rates", description="Update a live exchange rate (admin only)")
@app_commands.describe(type="Which rate to update", value="New rate value")
@app_commands.choices(type=[
    app_commands.Choice(name="INR — Crypto", value="i2c"),
    app_commands.Choice(name="Crypto — INR", value="c2i"),
])
async def update_rates(interaction: discord.Interaction, type: app_commands.Choice[str], value: float):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only admins can update rates.", ephemeral=True)
        return

    store["rates"][type.value] = value
    save_data(store)
    await refresh_panel_message()

    await interaction.response.send_message(
        f"**{CATEGORY_CONFIG[type.value]['label']}** rate updated to `{value}/$`.", ephemeral=True
    )


# ============================================================
# ;cal — BUTTON CALCULATOR
# ============================================================
class CalculatorView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.value = ""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This calculator isn't yours — run `*cal` to get your own.", ephemeral=True)
            return False
        return True

    def build_embed(self, result_text: str = None) -> discord.Embed:
        embed = discord.Embed(title="🧮 Rate Calculator", color=discord.Color.gold())
        embed.add_field(name="Amount", value=f"`{self.value or '0'}`", inline=False)
        if result_text:
            embed.add_field(name="Result", value=result_text, inline=False)
        embed.set_footer(text="Amount is treated as USD / crypto units.")
        return embed

    async def refresh(self, interaction: discord.Interaction, result_text: str = None):
        await interaction.response.edit_message(embed=self.build_embed(result_text), view=self)

    async def digit_press(self, interaction: discord.Interaction, digit: str):
        if digit == "." and "." in self.value:
            await self.refresh(interaction)
            return
        if len(self.value) >= 12:
            await self.refresh(interaction)
            return
        self.value += digit
        await self.refresh(interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, row=0)
    async def b1(self, i, b): await self.digit_press(i, "1")

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, row=0)
    async def b2(self, i, b): await self.digit_press(i, "2")

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, row=0)
    async def b3(self, i, b): await self.digit_press(i, "3")

    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, row=1)
    async def b4(self, i, b): await self.digit_press(i, "4")

    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, row=1)
    async def b5(self, i, b): await self.digit_press(i, "5")

    @discord.ui.button(label="6", style=discord.ButtonStyle.secondary, row=1)
    async def b6(self, i, b): await self.digit_press(i, "6")

    @discord.ui.button(label="7", style=discord.ButtonStyle.secondary, row=2)
    async def b7(self, i, b): await self.digit_press(i, "7")

    @discord.ui.button(label="8", style=discord.ButtonStyle.secondary, row=2)
    async def b8(self, i, b): await self.digit_press(i, "8")

    @discord.ui.button(label="9", style=discord.ButtonStyle.secondary, row=2)
    async def b9(self, i, b): await self.digit_press(i, "9")

    @discord.ui.button(label="0", style=discord.ButtonStyle.secondary, row=3)
    async def b0(self, i, b): await self.digit_press(i, "0")

    @discord.ui.button(label=".", style=discord.ButtonStyle.secondary, row=3)
    async def bdot(self, i, b): await self.digit_press(i, ".")

    @discord.ui.button(label="C", style=discord.ButtonStyle.danger, row=3)
    async def bclear(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = ""
        await self.refresh(interaction)

    @discord.ui.button(label="Enter", style=discord.ButtonStyle.success, row=4)
    async def benter(self, interaction: discord.Interaction, button: discord.ui.Button):
        amount = float(self.value) if self.value else 0.0
        rates = store["rates"]
        give_inr = amount * rates["i2c"]
        get_inr = amount * rates["c2i"]
        result_text = (
            f"**INR — Crypto:** {amount}$ → you pay **₹{give_inr:,.2f}**\n"
            f"**Crypto — INR:** {amount}$ → you receive **₹{get_inr:,.2f}**"
        )
        await self.refresh(interaction, result_text)


@bot.command(name="cal")
async def calculator_command(ctx: commands.Context):
    """Opens the interactive rate calculator."""
    view = CalculatorView(ctx.author.id)
    await ctx.send(embed=view.build_embed(), view=view)


# ============================================================
# CREDIT & DELIVER SYSTEM
# ============================================================
def is_admin(user: discord.Member) -> bool:
    if user.guild_permissions.administrator:
        return True
    return any(role.name == ADMIN_ROLE_NAME for role in user.roles)


def get_credits(user_id: int) -> int:
    return store["credits"].get(str(user_id), 0)


def set_credits(user_id: int, amount: int):
    store["credits"][str(user_id)] = max(0, amount)
    save_data(store)


class AddStockModal(discord.ui.Modal, title="Add Stock"):
    keys_input = discord.ui.TextInput(
        label="One key per line",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="key-one\nkey-two\nkey-three",
    )

    def __init__(self, product_name: str):
        super().__init__()
        self.product_name = product_name

    async def on_submit(self, interaction: discord.Interaction):
        lines = [line.strip() for line in self.keys_input.value.splitlines() if line.strip()]
        if not lines:
            await interaction.response.send_message("❌ No valid lines found — nothing was added.", ephemeral=True)
            return

        store["stock"].setdefault(self.product_name, []).extend(lines)
        save_data(store)
        await interaction.response.send_message(
            f"✅ Added **{len(lines)}** key(s) to **{self.product_name}**. "
            f"New stock count: **{len(store['stock'][self.product_name])}**.",
            ephemeral=True,
        )


@bot.tree.command(name="createproduct", description="Create a new product (admin only)")
@app_commands.describe(name="Name of the product")
async def createproduct(interaction: discord.Interaction, name: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        return

    if name in store["stock"]:
        await interaction.response.send_message(f"❌ Product **{name}** already exists.", ephemeral=True)
        return

    store["stock"][name] = []
    save_data(store)
    await interaction.response.send_message(f"✅ Product **{name}** created with 0 stock.", ephemeral=True)


@bot.tree.command(name="addstock", description="Add stock to a product (admin only)")
@app_commands.describe(product="Name of the product")
async def addstock(interaction: discord.Interaction, product: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        return

    if product not in store["stock"]:
        await interaction.response.send_message(f"❌ Product **{product}** doesn't exist. Create it first with `/createproduct`.", ephemeral=True)
        return

    await interaction.response.send_modal(AddStockModal(product))


@bot.tree.command(name="removestock", description="Remove one key from a product's stock (admin only)")
@app_commands.describe(product="Name of the product", key="The exact key to remove")
async def removestock(interaction: discord.Interaction, product: str, key: str):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        return

    if product not in store["stock"]:
        await interaction.response.send_message(f"❌ Product **{product}** doesn't exist.", ephemeral=True)
        return

    if key not in store["stock"][product]:
        await interaction.response.send_message(f"❌ That key wasn't found in **{product}**.", ephemeral=True)
        return

    store["stock"][product].remove(key)
    save_data(store)
    await interaction.response.send_message(f"✅ Removed key from **{product}**. Remaining stock: **{len(store['stock'][product])}**.", ephemeral=True)


@bot.tree.command(name="addcredits", description="Add credits to a user (admin only)")
@app_commands.describe(user="The user to credit", amount="How many credits to add")
async def addcredits(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return

    set_credits(user.id, get_credits(user.id) + amount)
    await interaction.response.send_message(f"✅ Added **{amount}** credit(s) to {user.mention}. New balance: **{get_credits(user.id)}**.", ephemeral=True)


@bot.tree.command(name="removecredits", description="Remove credits from a user (admin only)")
@app_commands.describe(user="The user to deduct from", amount="How many credits to remove")
async def removecredits(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to do that.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return

    set_credits(user.id, get_credits(user.id) - amount)
    await interaction.response.send_message(f"✅ Removed **{amount}** credit(s) from {user.mention}. New balance: **{get_credits(user.id)}**.", ephemeral=True)


@bot.tree.command(name="balance", description="Check your credit balance")
async def balance(interaction: discord.Interaction):
    await interaction.response.send_message(f"💳 You have **{get_credits(interaction.user.id)}** credit(s).", ephemeral=True)


@bot.tree.command(name="stock", description="View all products and their stock counts")
async def stock(interaction: discord.Interaction):
    if not store["stock"]:
        await interaction.response.send_message("There are no products yet.", ephemeral=True)
        return

    embed = discord.Embed(title="📦 Product Stock", color=discord.Color.blurple())
    for product, keys in store["stock"].items():
        embed.add_field(name=product, value=f"**{len(keys)}** in stock", inline=True)
    embed.set_footer(text=f"1 credit = {CREDIT_TO_KEYS} item(s)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="redeem", description="Spend credits to redeem items from a product")
@app_commands.describe(product="Name of the product", credits="How many credits to spend")
async def redeem(interaction: discord.Interaction, product: str, credits: int):
    if credits <= 0:
        await interaction.response.send_message("❌ Credits must be a positive number.", ephemeral=True)
        return

    if product not in store["stock"]:
        await interaction.response.send_message(f"❌ Product **{product}** doesn't exist.", ephemeral=True)
        return

    user_balance = get_credits(interaction.user.id)
    if user_balance < credits:
        await interaction.response.send_message(
            f"❌ You don't have enough credits. Balance: **{user_balance}**, needed: **{credits}**.", ephemeral=True
        )
        return

    items_needed = credits * CREDIT_TO_KEYS
    available = store["stock"][product]
    if len(available) < items_needed:
        await interaction.response.send_message(
            f"❌ Not enough stock for **{product}**. Available: **{len(available)}**, needed: **{items_needed}**.",
            ephemeral=True,
        )
        return

    # Deduct up front
    delivered = available[:items_needed]
    store["stock"][product] = available[items_needed:]
    set_credits(interaction.user.id, user_balance - credits)
    save_data(store)

    keys_block = "\n".join(delivered)
    dm_content = f"✅ Here are your **{product}** keys ({items_needed} item(s)):\n```\n{keys_block}\n```"

    try:
        await interaction.user.send(dm_content)
    except discord.Forbidden:
        # Refund everything since delivery failed
        store["stock"][product] = delivered + store["stock"][product]
        set_credits(interaction.user.id, user_balance)
        save_data(store)
        await interaction.response.send_message(
            "❌ I couldn't DM you (your DMs might be closed). Your credits and stock have been refunded — "
            "please open your DMs and try `/redeem` again.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"✅ Redeemed **{items_needed}** item(s) from **{product}** for **{credits}** credit(s). Check your DMs!",
        ephemeral=True,
    )


# ============================================================
# STARTUP
# ============================================================
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView("i2c"))
    bot.add_view(CloseTicketView("c2i"))

    if store.get("stock_channel_id") and store.get("stock_message_id"):
        if not stock_refresh_loop.is_running():
            stock_refresh_loop.start()

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Slash command sync failed: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN environment variable is not set. See README.md.")
    bot.run(TOKEN)
