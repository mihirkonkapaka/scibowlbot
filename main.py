import asyncio
import os
import time
import discord
import requests
from discord import app_commands
from dotenv import load_dotenv
from checkAnswer import checkAnswer

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
help_string = """/start - starts the game
/end - ends the game
/debug - checks if the bot is running
/a - answers a Short Answer question
/score - checks your score"""

import json

# Global dictionary to store user points
user_points = {}

# File to save points
POINTS_FILE = 'points.json'

# Load points from file
def load_points():
    global user_points
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, 'r') as f:
            content = f.read().strip()
            if content:
                user_points = json.loads(content)
            else:
                user_points = {}
    else:
        user_points = {}


# Save points to file
def save_points():
    with open(POINTS_FILE, 'w') as f:
        json.dump(user_points, f, indent=4)

# Give points to a user
def add_points(user_id, amount):
    user_id = str(user_id)  # JSON keys must be strings
    user_points[user_id] = user_points.get(user_id, 0) + amount
    save_points()


class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.question_data = None
        self.buzzed_user = None
        self.banned_from_buzzing = set()
        self.timer_task = None
        self.tossup_answerer = None
        self.awaiting_bonus = False

    def is_user_banned(self, user_id):
        return user_id in self.banned_from_buzzing

    def ban_user(self, user_id):
        self.banned_from_buzzing.add(user_id)

    def clear_buzz(self):
        self.buzzed_user = None

    def has_active_question(self):
        return self.question_data is not None


game_state = GameState()


async def start_new_tossup(channel):
    res = requests.get("https://scibowldb.com/api/questions/random")
    data = res.json()["question"]
    game_state.reset()
    game_state.question_data = data

    duration = 7 + len(data["tossup_question"].split()) // 2
    end_timestamp = int(time.time()) + duration  # <-- THIS LINE: calculate the end time

    # Create Embed for the tossup
    embed = discord.Embed(
        title="🔔 Tossup!",
        description=(
            f"{data['tossup_question']}\n\n"
            f"⏳ **You have until <t:{end_timestamp}:R> to buzz and answer!**"
        ),
        color=discord.Color.blurple()
    )

    view = BuzzView()
    await channel.send(embed=embed, view=view)

    game_state.timer_task = asyncio.create_task(tossup_timer(channel, duration))



async def tossup_timer(channel, seconds):
    await asyncio.sleep(seconds)
    if game_state.has_active_question() and not game_state.awaiting_bonus:
        await channel.send(f"⏰ Time's up! Correct tossup answer: **{game_state.question_data['tossup_answer']}**")
        await asyncio.sleep(1)
        await start_new_tossup(channel)


class BuzzView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Buzz!", style=discord.ButtonStyle.success)
    async def buzz(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not game_state.has_active_question():
            await interaction.response.send_message("❌ No active tossup.", ephemeral=True)
            return

        if game_state.is_user_banned(interaction.user.id):
            await interaction.response.send_message("🚫 You can't buzz again on this tossup.", ephemeral=True)
            return

        if game_state.buzzed_user:
            await interaction.response.send_message(f"⚠️ {game_state.buzzed_user.mention} already buzzed.", ephemeral=True)
            return

        game_state.buzzed_user = interaction.user
        button.disabled = True
        await interaction.response.edit_message(view=self)

        if game_state.question_data["tossup_format"] == "Multiple Choice":
            view = MultipleChoiceView(game_state.question_data["tossup_answer"][0], interaction.user, "tossup")
            await interaction.followup.send(f"🔔 {interaction.user.mention} buzzed! Choose your answer:", view=view)
        else:
            await interaction.followup.send(f"🔔 {interaction.user.mention} buzzed! Use `/a <answer>` to respond.")


class MultipleChoiceView(discord.ui.View):
    def __init__(self, correct_letter, allowed_user, phase):
        super().__init__(timeout=None)
        self.correct_letter = correct_letter.strip().upper()[0]
        self.allowed_user = allowed_user
        self.phase = phase

        for choice in ["W", "X", "Y", "Z"]:
            self.add_item(MCButton(choice, self))


class MCButton(discord.ui.Button):
    def __init__(self, label, parent_view):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.allowed_user:
            await interaction.response.send_message("⚠️ You're not allowed to answer now.", ephemeral=True)
            return

        correct = self.label == self.parent_view.correct_letter
        await handle_answer(interaction, correct)


async def handle_answer(interaction, correct):
    channel = interaction.channel
    if game_state.awaiting_bonus:
        if correct:
            await interaction.response.send_message(f"✅ Correct bonus answer! ANSWER: **{game_state.question_data['bonus_answer']}")
            add_points(interaction.user.id, 10)  # for bonus correct, example 4 points
            await interaction.channel.send(f"{interaction.user} has {user_points[str(interaction.user.id)]} points! (+10)")
        else:
            await interaction.response.send_message(f"❌ Incorrect bonus answer. Correct was: **{game_state.question_data['bonus_answer']}**")
        await asyncio.sleep(1)
        await start_new_tossup(interaction.channel)
    else:
        if correct:
            game_state.tossup_answerer = interaction.user
            game_state.awaiting_bonus = True
            if game_state.timer_task:
                game_state.timer_task.cancel()
            await interaction.response.send_message(
                f"✅ Correct tossup by {interaction.user.mention}!\nThe answer was: **{game_state.question_data['tossup_answer']}**"
            )
            duration = 12 + len(game_state.question_data["bonus_question"].split()) // 2
            end_timestamp = int(time.time()) + duration  # <-- THIS LINE: calculate the end time

            # Create Embed for the tossup
            embed = discord.Embed(
                title="🔔 Bonus!",
                description=(
                    f"{game_state.question_data['bonus_question']}\n\n"
                    f"⏳ **You have until <t:{end_timestamp}:R> to buzz and answer!**"
                ),
                color=discord.Color.blurple()
            )
            await channel.send(embed=embed)

            game_state.timer_task = asyncio.create_task(tossup_timer(channel, duration))
            add_points(interaction.user.id, 4)  # for tossup correct, example 4 points
            await interaction.channel.send(f"{interaction.user} has {user_points[str(interaction.user.id)]} points! (+4)")
            if game_state.question_data["bonus_format"] == "Multiple Choice":
                view = MultipleChoiceView(game_state.question_data["bonus_answer"][0], interaction.user, "bonus")
                await interaction.followup.send(view=view)
        else:
            game_state.ban_user(interaction.user.id)
            game_state.clear_buzz()
            await interaction.response.send_message("❌ Incorrect tossup answer. Others may buzz!")
            add_points(interaction.user.id, -1)  # for tossup correct, example 4 points
            await interaction.channel.send(f"{interaction.user} has {user_points[str(interaction.user.id)]} points! (-1)")
@tree.command(name="start", description="Start a new tossup", guild=guild)
async def start(interaction: discord.Interaction):
    if game_state.has_active_question():
        await interaction.response.send_message("⚠️ A tossup is already active.", ephemeral=True)
        return

    await start_new_tossup(interaction.channel)
    await interaction.response.send_message("✅ Tossup posted!", ephemeral=True)


@tree.command(name="a", description="Answer current question", guild=guild)
@app_commands.describe(answer="Your answer")
async def answer(interaction: discord.Interaction, answer: str):
    if not game_state.has_active_question():
        await interaction.response.send_message("❌ No active question.")
        return

    if game_state.awaiting_bonus:
        if interaction.user != game_state.tossup_answerer:
            await interaction.response.send_message("⚠️ Only the tossup winner can answer the bonus.")
            return
        correct = checkAnswer(game_state.question_data["bonus_answer"], answer)
    else:
        if interaction.user != game_state.buzzed_user:
            await interaction.response.send_message("⚠️ You must buzz first.")
            return
        correct = checkAnswer(game_state.question_data["tossup_answer"], answer)

    await handle_answer(interaction, correct)


@tree.command(name="debug", description="Check if bot is running", guild=guild)
async def debug(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot is up and running!")


@tree.command(name="end", description="End current session", guild=guild)
async def end(interaction: discord.Interaction):
    game_state.reset()
    await interaction.response.send_message("✅ Game ended.")

@tree.command(name="score", description="Check your points", guild=guild)
async def score(interaction: discord.Interaction):
    points = user_points.get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"🏆 You have {points} points!", ephemeral=False)

@tree.command(name="help", description="List all commands", guild=guild)
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(help_string, ephemeral=True)

@tree.command(name="leaderboard", description="View the leaderboard!", guild=guild)
async def leaderboard(interaction: discord.Interaction):
    if not user_points:
        await interaction.response.send_message("🏆 No points have been awarded yet!", ephemeral=True)
        return

    # Sort users by points (highest first)
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)

    leaderboard_lines = []
    for rank, (user_id, points) in enumerate(sorted_users[:10], start=1):  # Top 10 players
        user = await interaction.client.fetch_user(user_id)
        leaderboard_lines.append(f"**#{rank}** — {user.name}: {points} points")

    leaderboard_message = "\n".join(leaderboard_lines)

    await interaction.response.send_message(f"🏆 **Leaderboard** 🏆\n\n{leaderboard_message}")



@client.event
async def on_ready():
    await tree.sync(guild=guild)
    load_points()
    print(f"Bot ready! Synced commands to guild {guild.id}")


client.run(TOKEN)
