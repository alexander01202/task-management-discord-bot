"""
Discord AI Bot - Main Entry Point
Milestone 2: Autonomous AI Agent with Google Sheets Tool Calling
"""
import discord
from discord.ext import commands

from config import config
from database import Database
from services import AIService, GoogleSheetsService, ReminderScheduler
from handlers import MessageHandler


def setup_bot():
    """Initialize and configure the Discord bot"""

    print("=" * 60)
    print("🤖 Discord AI Agent - Initializing...")
    print("=" * 60)

    # Validate configuration
    print("\n📋 Validating configuration...")
    try:
        config.validate_config()
        print("   ✅ All configuration valid")
    except ValueError as e:
        print(f"   ❌ {e}")
        exit(1)

    # Initialize services
    print("\n🔌 Initializing services...")
    database = Database()
    sheets_service = GoogleSheetsService()
    ai_service = AIService(sheets_service)  # Pass sheets service to AI for tool calling
    print("   ✅ All services initialized")

    # Configure Discord intents
    print("\n🔐 Configuring Discord intents...")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True
    intents.guild_messages = True
    intents.dm_messages = True
    print("   ✅ Intents configured")

    # Initialize bot (no commands, pure AI agent)
    bot = commands.Bot(command_prefix="!", intents=intents)
    print(f"   ✅ Bot initialized")

    # Initialize message handler
    print("\n🔧 Initializing message handler...")
    message_handler = MessageHandler(database, ai_service)
    print("   ✅ Handler initialized")

    # Initialize reminder scheduler
    print("\n⏰ Initializing reminder scheduler...")
    reminder_scheduler = ReminderScheduler(bot, sheets_service)
    print("   ✅ Scheduler initialized")


    # Register events
    @bot.event
    async def on_ready():
        """Event triggered when bot connects to Discord"""
        print("\n" + "=" * 60)
        print("🎉 AI AGENT SUCCESSFULLY CONNECTED TO DISCORD!")
        print("=" * 60)
        print(f"   Bot Name: {bot.user.name}")
        print(f"   Bot ID: {bot.user.id}")
        print(f"   Connected to {len(bot.guilds)} server(s)")

        for guild in bot.guilds:
            print(f"      - {guild.name} (ID: {guild.id})")

        print("=" * 60)

        # Set bot status
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="task sheets 📊"
            )
        )
        print("✅ Bot status set: Watching task sheets 📊")

        # Start reminder scheduler
        reminder_scheduler.start()

        print("\n🤖 AI Agent is now ready - just mention me and ask about tasks!")
        print("=" * 60)

    @bot.event
    async def on_message(message):
        """Event triggered when a message is sent"""

        # Ignore messages from the bot itself
        if message.author == bot.user:
            return

        # Check if bot is explicitly mentioned (not just replied to)
        is_mentioned = bot.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_mentioned or is_dm:
            print("\n" + "=" * 60)
            print("📨 NEW MESSAGE RECEIVED")
            print("=" * 60)
            print(f"   From: {message.author.name} (ID: {message.author.id})")
            print(f"   Channel: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}")

            # Remove bot mention from message content
            content = message.content.replace(f'<@{bot.user.id}>', '').strip()
            print(f"   Message: \"{content}\"")

            # Handle empty messages
            if not content:
                print("   ⚠️  Empty message detected")
                await message.channel.send("Hey! Ask me about tasks and I'll check the sheets for you!")
                return

            # Show typing indicator
            print("   ⌨️  Showing typing indicator...")
            async with message.channel.typing():
                try:
                    # Process message through AI agent
                    ai_message = await message_handler.process_message(message, content)

                    # Split long messages if needed (Discord 2000 char limit)
                    if len(ai_message) > 2000:
                        print(f"   ✂️  Message too long - splitting into chunks")
                        chunks = [ai_message[i:i+2000] for i in range(0, len(ai_message), 2000)]
                        print(f"   📤 Sending {len(chunks)} message chunks...")
                        for idx, chunk in enumerate(chunks, 1):
                            await message.channel.send(chunk)
                            print(f"      ✅ Chunk {idx}/{len(chunks)} sent")
                    else:
                        print(f"   📤 Sending response...")
                        await message.channel.send(ai_message)
                        print(f"   ✅ Response sent successfully!")

                    print("=" * 60)

                except Exception as e:
                    print(f"   ❌ ERROR processing message: {e}")
                    import traceback
                    traceback.print_exc()
                    print("=" * 60)
                    await message.channel.send("Sorry, I encountered an error. Please try again.")

    return bot


def main():
    """Main entry point"""

    print("\n" + "=" * 60)
    print("🔍 PERFORMING PRE-FLIGHT CHECKS")
    print("=" * 60)

    # Setup bot
    bot = setup_bot()

    # All checks passed - start the bot
    print("\n" + "=" * 60)
    print("✅ ALL PRE-FLIGHT CHECKS PASSED")
    print("=" * 60)
    print("\n🚀 Starting Discord AI Agent...")
    print("⏳ Connecting to Discord... (this may take a few seconds)")
    print("\n" + "=" * 60)

    try:
        bot.run(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("\n❌ LOGIN FAILED - Invalid Discord token!")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
