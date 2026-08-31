# Discord Bot — Tickets, Rate Panel, SellAuth Stock & Credit System

## Prefix commands (prefix: `*`)
- `*setup` — Sends the ticket panel (live rates + rules embed with category dropdown). Admin only.
- `*cal` — Interactive button calculator using the current live rates.
- `*stockpanel` — Sends the live SellAuth stock panel in this channel. Admin only.

## Slash commands
- `/update-rates` — Updates a rate (`INR — Crypto` or `Crypto — INR`) and auto-edits the live panel. Admin only.
- `/createproduct name:<string>` — Creates a new product with empty stock. Admin only.
- `/addstock product:<string>` — Opens a form (modal) with a multi-line box — each line becomes one stock key. Admin only.
- `/removestock product:<string> key:<string>` — Removes one specific key from a product. Admin only.
- `/addcredits user:<Member> amount:<int>` — Adds credits to a user. Admin only.
- `/removecredits user:<Member> amount:<int>` — Removes credits from a user (floors at 0). Admin only.
- `/balance` — Shows your own credit balance (ephemeral).
- `/stock` — Shows all products and their stock counts (ephemeral).
- `/redeem product:<string> credits:<int>` — Spends credits to redeem items (**1 credit = 2 items**). Delivers keys via DM; refunds automatically if your DMs are closed.

"Admin only" means you either have the **Administrator** permission, or a role named exactly what's set in `ADMIN_ROLE_NAME` (see below).

## Setup Steps

### 1. Create the bot on the Discord Developer Portal
1. Go to https://discord.com/developers/applications
2. **New Application** → give it a name
3. Left sidebar → **Bot** → **Add Bot**
4. Turn ON **MESSAGE CONTENT INTENT** (required for `*setup`, `*cal`, `*stockpanel`)
5. Click **Reset Token** and copy your bot token (never share this with anyone)

### 2. Invite the bot to your server
1. Left sidebar → **OAuth2 → URL Generator**
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Manage Channels`, `Send Messages`, `Embed Links`, `Manage Messages`, `Read Message History`
4. Open the generated URL and add the bot to your server

### 3. Environment variables
Set these wherever you host the bot (Railway → Variables, or a local `.env` file):

| Variable | Required | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Yes | Your bot token from step 1 |
| `SELLAUTH_API_KEY` | Only for `*stockpanel` | From dash.sellauth.com/api |
| `ADMIN_ROLE_NAME` | No (defaults to `Admin`) | Role name that counts as admin for credit commands, besides real Administrator permission |

### 4. Run the bot

```bash
pip install -r requirements.txt
export DISCORD_BOT_TOKEN="your_token_here"
python bot.py
```

Windows CMD:
```
set DISCORD_BOT_TOKEN=your_token_here
```

## Already configured in `bot.py`
- Support role ping: `SUPPORT_ROLE_ID`
- INR → Crypto ticket category / transcripts, Crypto → INR ticket category / transcripts (Discord IDs)
- SellAuth: `SELLAUTH_SHOP_ID`, `SELLAUTH_SHOP_URL`
- Credit ratio: `CREDIT_TO_KEYS` (currently 2 — i.e. 1 credit = 2 items)
- Custom emojis (`frost_*`) — must exist on your server to render correctly

All data (rates, panel message locations, credits, and product stock) is saved in `data/store.json`, so it survives a bot restart.

## Note
Never upload your bot token or API keys to GitHub or any public place. Using environment variables is the safest approach.
