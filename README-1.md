# Discord Bot — Ticket System, Rate Panel & Calculator

## Commands
- `;setup` — Sends the ticket panel (live rates + rules embed with category dropdown) in this channel. Admin only.
- `/update-rates` — Updates a rate (`INR — Crypto` or `Crypto — INR`). Automatically edits the live panel message too. Admin only.
- `;cal` — Opens an interactive button calculator. Enter an amount and see both conversion results using the current live rates.

## How the ticket flow works
1. Admin runs `;setup` in a channel → bot posts the rates/rules panel with a category dropdown.
2. A user picks a category → a form (modal) pops up with 5 questions.
3. On submit, a private ticket channel is created (`i2c-username` or `c2i-username`) inside the matching Discord category, with a ping for the user + Support role, and an embed showing their answers.
4. Staff clicks **Close Ticket** → a transcript is generated and sent to the matching transcript channel, then the ticket channel is deleted.

## Setup Steps

### 1. Create the bot on the Discord Developer Portal
1. Go to https://discord.com/developers/applications
2. **New Application** → give it a name
3. Left sidebar → **Bot** → **Add Bot**
4. Turn ON **MESSAGE CONTENT INTENT** (required for `;setup` and `;cal`)
5. Click **Reset Token** and copy your bot token (never share this with anyone)

### 2. Invite the bot to your server
1. Left sidebar → **OAuth2 → URL Generator**
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Manage Channels`, `Send Messages`, `Embed Links`, `Manage Messages`, `Read Message History`
4. Open the generated URL and add the bot to your server

### 3. Run the bot

```bash
pip install -r requirements.txt

# Set your token as an environment variable
export DISCORD_BOT_TOKEN="your_token_here"

python bot.py
```

Windows CMD:
```
set DISCORD_BOT_TOKEN=your_token_here
```

### 4. Test it
- Run `;setup` in a channel → the panel appears
- Pick a category from the dropdown → fill the form → your ticket channel is created
- Run `/update-rates` → pick a type, enter a value → the panel updates automatically
- Run `;cal` → tap digits, then Enter → see both conversion results

## Already configured in `bot.py`
- Support role ping: `SUPPORT_ROLE_ID`
- INR → Crypto ticket category: Discord category `1542497071213453362`
- Crypto → INR ticket category: Discord category `1542497183524454420`
- INR → Crypto transcripts: channel `1542496878413746248`
- Crypto → INR transcripts: channel `1542496940367941702`
- Custom emojis (`frost_list`, `frost_mart`, `frost_exch`, `frost_caution`, `frost_dot`) — these must exist on your server to render correctly

Rates and the panel message location are saved in `data/store.json`, so they survive a bot restart.

## Note
Never upload your bot token to GitHub or any public place. Using the `DISCORD_BOT_TOKEN` environment variable is the safest approach.
