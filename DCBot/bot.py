import asyncio
import logging
from datetime import datetime
import discord
from discord.ext import commands
from . import botconfig

logger = logging.getLogger("discord_bot")

class VerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Verify",
            style=discord.ButtonStyle.green,
            custom_id="verify_member_button"
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = botconfig.DISCORD_MEMBER_ROLE_ID
        if not role_id:
            await interaction.response.send_message(
                "Error: The member role ID is not configured.", ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                f"Error: Role with ID `{role_id}` was not found in this server.",
                ephemeral=True
            )
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                "Verification successful! You have been granted the member role.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Error: The bot does not have permission to assign this role. "
                "Ensure the bot's role is positioned higher than the target role in Server Settings.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Error assigning role: {e}", ephemeral=True
            )

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(VerifyButton())

class EchoDiscordBot(commands.Bot):
    def __init__(self, app_instance=None):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.invites = True

        super().__init__(command_prefix="!", intents=intents)
        self.app = app_instance
        self.invite_cache = {}

    async def setup_hook(self):
        self.add_view(VerifyView())

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name}#{self.user.discriminator}")
        print(f"Discord Bot online: {self.user}")

        # Update app UI state if running
        if self.app:
            self.app.call_from_thread(self.app._update_discord_status, "Active")

        # Cache server invites for invite tracking
        for guild in self.guilds:
            try:
                self.invite_cache[guild.id] = await guild.invites()
            except discord.Forbidden:
                logger.warning(f"No permissions to read invites in guild {guild.name}")
            except Exception as e:
                logger.error(f"Error caching invites for {guild.name}: {e}")

        # Sync slash commands
        try:
            if botconfig.DISCORD_GUILD_ID:
                guild = discord.Object(id=botconfig.DISCORD_GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Slash commands synced instantly to Guild ID: {botconfig.DISCORD_GUILD_ID}")
            else:
                await self.tree.sync()
                logger.info("Slash commands synced globally.")
        except Exception as e:
            logger.error(f"Error syncing tree: {e}")

    async def on_member_join(self, member: discord.Member):
        welcome_channel_id = botconfig.DISCORD_WELCOME_CHANNEL_ID
        if not welcome_channel_id:
            return

        channel = member.guild.get_channel(welcome_channel_id)
        if not channel:
            return

        # Attempt to track inviter
        inviter_username = "Unknown"
        guild_id = member.guild.id
        try:
            current_invites = await member.guild.invites()
            cached_invites = self.invite_cache.get(guild_id, [])

            for cached_inv in cached_invites:
                for cur_inv in current_invites:
                    if cached_inv.code == cur_inv.code and cur_inv.uses > cached_inv.uses:
                        inviter_username = cur_inv.inviter.name
                        break
                if inviter_username != "Unknown":
                    break

            # Update cache
            self.invite_cache[guild_id] = current_invites
        except Exception as e:
            logger.error(f"Error tracking invite for joining member: {e}")

        # Create Welcome Embed
        embed = discord.Embed(
            title=f"Welcome to $echo {member.name}!",
            description=(
                f"Welcome to **$echo**, we are an open source personal assistant software, "
                f"with tutorials and documentation to help new users get started!"
            ),
            color=0x8BFF7A
        )
        embed.add_field(name="Invited By", value=inviter_username, inline=True)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)

        try:
            await channel.send(content=member.mention, embed=embed)
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

# ── Command setup ─────────────────────────────────────────────────────────────

bot = EchoDiscordBot()

@bot.tree.command(name="uptime", description="Displays the current uptime of the $echo session.")
async def uptime(interaction: discord.Interaction):
    if not bot.app:
        await interaction.response.send_message(
            "Uptime: `$echo application is not running.`", ephemeral=True
        )
        return

    elapsed = datetime.now() - bot.app._start_time
    h, rem = divmod(int(elapsed.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    await interaction.response.send_message(
        f"⏳ **Uptime:** `{h:02d}:{m:02d}:{s:02d}`", ephemeral=True
    )

@bot.tree.command(name="info", description="Detailed information about $echo and its capabilities.")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="$echo",
        description=(
            "An open-source, local-first personal AI assistant built for developer productivity "
            "and command-line convenience."
        ),
        color=0x8BFF7A
    )
    embed.add_field(
        name="What it is",
        value=(
            "**$echo** combines a Textual-based terminal UI (TUI) with local LLMs (via Ollama) "
            "to automate system tasks entirely on your local machine."
        ),
        inline=False
    )
    embed.add_field(
        name="What it does",
        value=(
            "• **File Management**: Create, edit, list, and read files safely.\n"
            "• **Shell Automations**: Execute and verify console scripts.\n"
            "• **Tool Integrations**: Manage calendar tasks, email draft creation, and code debugging.\n"
            "• **Total Privacy**: Built from the ground up to keep data on your local workspace."
        ),
        inline=False
    )
    embed.add_field(
        name="Get Started",
        value="View documentation, tutorials, and contribute at the official open-source repository.",
        inline=False
    )

    # Simple components v2 style: a view containing helper links
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="GitHub Repository",
        url="https://github.com/Josh/personal-assistant",
        style=discord.ButtonStyle.link
    ))
    view.add_item(discord.ui.Button(
        label="Get Support",
        url="https://github.com/Josh/personal-assistant/issues",
        style=discord.ButtonStyle.link
    ))

    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="owner", description="Learn about the creator of $echo and why it was built.")
async def owner(interaction: discord.Interaction):
    embed = discord.Embed(
        title="$echo Creator ── Josh",
        description=(
            "Josh is a software developer committed to open-source developer tooling "
            "and modular terminal solutions."
        ),
        color=0x8BFF7A
    )
    embed.add_field(
        name="Why I Built $echo",
        value=(
            "I wanted a personal assistant that lives where I spend most of my time: the terminal. "
            "It is designed to bridge local AI models with script/automation tasks, keeping "
            "private project files and automation steps fully local, offline, and secure."
        ),
        inline=False
    )
    embed.add_field(
        name="System Stack",
        value="Powered by Arch Linux workflows, Python, Ollama, Textual, and discord.py.",
        inline=False
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="docs", description="Show links to documentation and tutorials.")
async def docs(interaction: discord.Interaction):
    embed = discord.Embed(
        title="$echo Documentation",
        description="Access guides and tutorials for getting started with $echo.",
        color=0x8BFF7A
    )
    embed.add_field(
        name="Tutorials",
        value="Check out the repository README and Wiki pages for tool setup instructions.",
        inline=False
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="Guides & Wiki",
        url="https://github.com/Josh/personal-assistant#readme",
        style=discord.ButtonStyle.link
    ))
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="features", description="List active and planned assistant features.")
async def features(interaction: discord.Interaction):
    embed = discord.Embed(
        title="$echo Features Roadmap",
        description="Features active in this build and upcoming development goals.",
        color=0x8BFF7A
    )
    embed.add_field(
        name="Active Features",
        value=(
            "• Local Ollama agent loop (`qwen3:8b`)\n"
            "• Responsive Textual terminal interface (TUI)\n"
            "• Live session statistics and background warmup\n"
            "• Safe shell execution confirmation gate\n"
            "• Background Discord bot helper interface"
        ),
        inline=False
    )
    embed.add_field(
        name="Planned Roadmap",
        value=(
            "• Custom bash autocomplete bindings\n"
            "• Advanced semantic search for local workspaces\n"
            "• Local database task syncing module"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Generate a server invite link for the bot.")
async def invite(interaction: discord.Interaction):
    permissions = discord.Permissions(
        manage_roles=True,
        manage_channels=True,
        manage_guild=True,
        send_messages=True,
        embed_links=True
    )
    invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions, scopes=["bot", "applications.commands"])
    await interaction.response.send_message(
        f"🔗 Add the **$echo** assistant bot to your server: [Invite Link]({invite_url})",
        ephemeral=True
    )

@bot.tree.command(name="verify", description="Send the official verification button embed (Admin only).")
async def verify(interaction: discord.Interaction):
    # Check permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Error: You must be a server Administrator to run this command.", ephemeral=True
        )
        return

    verify_channel_id = botconfig.DISCORD_VERIFY_CHANNEL_ID
    if not verify_channel_id:
        await interaction.response.send_message(
            "Error: Verification channel ID is not set in `botconfig.py`.", ephemeral=True
        )
        return

    channel = interaction.guild.get_channel(verify_channel_id)
    if not channel:
        await interaction.response.send_message(
            f"Error: Channel with ID `{verify_channel_id}` was not found in this server.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="$echo",
        description="Please press the button below to verify and gain the member role.",
        color=0x8BFF7A
    )

    try:
        await channel.send(embed=embed, view=VerifyView())
        await interaction.response.send_message(
            f"Verification embed posted successfully in <#{verify_channel_id}>.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error posting verification embed: {e}", ephemeral=True
        )

class SuggestionModal(discord.ui.Modal, title="Submit a Suggestion"):
    suggestion_title = discord.ui.TextInput(
        label="Suggestion Title / Feature",
        placeholder="e.g. Add a calendar shortcut widget",
        required=True,
        max_length=100
    )
    suggestion_details = discord.ui.TextInput(
        label="Details & Use Case",
        style=discord.TextStyle.paragraph,
        placeholder="Please detail your suggestion here...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Log to the Textual app console log in real-time
        if bot.app:
            msg = (
                f"\n  [bold #8BFF7A]Suggestion Received[/] [dim #666666]from {interaction.user.name}[/]\n"
                f"  [#666666]Title:[/] {self.suggestion_title.value}\n"
                f"  [#666666]Details:[/] {self.suggestion_details.value}\n"
            )
            bot.app.call_from_thread(bot.app._log.write, msg)

        # 2. Post to the configured suggestion channel
        channel_id = botconfig.DISCORD_SUGGESTIONS_CHANNEL_ID
        if channel_id:
            channel = None
            for guild in bot.guilds:
                channel = guild.get_channel(channel_id)
                if channel:
                    break

            if channel:
                embed = discord.Embed(
                    title=f"💡 Suggestion: {self.suggestion_title.value}",
                    description=self.suggestion_details.value,
                    color=0x8BFF7A,
                    timestamp=datetime.now()
                )
                embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
                try:
                    await channel.send(embed=embed)
                    await interaction.response.send_message(
                        "Thank you! Your suggestion has been submitted successfully.",
                        ephemeral=True
                    )
                    return
                except Exception as e:
                    logger.error(f"Error posting suggestion: {e}")

        # Fallback if channel not found or error occurred
        await interaction.response.send_message(
            "Thank you! Your suggestion has been logged to the $echo application.",
            ephemeral=True
        )

@bot.tree.command(name="suggestions", description="Submit a suggestion for $echo (DM only).")
@discord.app_commands.dm_only()
async def suggestions(interaction: discord.Interaction):
    await interaction.response.send_modal(SuggestionModal())


# ── Bot Loop runner ───────────────────────────────────────────────────────────

def start_discord_bot(app_instance, token: str):
    """Entrypoint to start the bot in a separate event loop (for threading)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot.app = app_instance
    try:
        loop.run_until_complete(bot.start(token))
    except Exception as e:
        logger.error(f"Discord Bot terminated unexpectedly: {e}")
    finally:
        loop.close()
