"""
Discord AI Bot with Conversational Memory - Milestone 1
Uses Langraph for conversation flow, Anthropic Claude for AI, and Supabase for memory storage

This bot provides conversational AI assistance with memory, focusing on sports betting and arbitrage.
It remembers past conversations and provides contextual responses.
"""

import os
import discord
from discord.ext import commands
from anthropic import Anthropic
from supabase import create_client, Client
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== Configuration ====================
print("=" * 60)
print("🤖 Discord AI Bot - Initializing...")
print("=" * 60)

# Load environment variables
print("\n📋 Loading environment variables...")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_PUBLIC_KEY")

# Verify all credentials are present
if DISCORD_TOKEN:
    print("   ✅ Discord token loaded")
else:
    print("   ❌ Discord token missing!")

if ANTHROPIC_API_KEY:
    print("   ✅ Anthropic API key loaded")
else:
    print("   ❌ Anthropic API key missing!")

if SUPABASE_URL:
    print("   ✅ Supabase URL loaded")
else:
    print("   ❌ Supabase URL missing!")

if SUPABASE_KEY:
    print("   ✅ Supabase key loaded")
else:
    print("   ❌ Supabase key missing!")

# Initialize clients
print("\n🔌 Connecting to services...")
try:
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    print("   ✅ Anthropic client initialized")
except Exception as e:
    print(f"   ❌ Anthropic client failed: {e}")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("   ✅ Supabase client initialized")
except Exception as e:
    print(f"   ❌ Supabase client failed: {e}")

# ==================== LangGraph State Definition ====================
"""
State schema for LangGraph conversation management.
This defines what information is tracked throughout each conversation.
"""
class State(TypedDict):
    messages: Annotated[list, add_messages]  # List of conversation messages
    user_id: str  # Discord user ID (unique identifier)
    channel_id: str  # Discord channel ID (for context separation)


# ==================== System Prompt ====================
"""
This system prompt defines the bot's personality and focus areas.
It's sent with every API call to Claude to maintain consistent behavior.
"""
SYSTEM_PROMPT = """You are a helpful AI assistant for a sports betting and arbitrage team. 

Your primary focus is to be highly responsive and knowledgeable about:
- Sports betting strategies and odds
- Arbitrage opportunities in sports betting
- Risk management and bankroll management
- Sports analytics and statistics
- Betting market analysis

While you can engage in general conversation, you should always steer discussions back to sports betting and arbitrage when relevant. Be proactive, analytical, and help team members make informed decisions.

Keep your responses concise but informative. Be friendly and professional."""

print("\n✅ System prompt loaded - Focus: Sports betting & arbitrage")


# ==================== Conversation Memory Functions ====================

def save_conversation_to_supabase(user_id: str, channel_id: str, message: str, response: str):
    """
    Save conversation history to Supabase database for persistent memory.

    Args:
        user_id: Discord user ID
        channel_id: Discord channel ID
        message: User's message
        response: Bot's response
    """
    print(f"\n💾 Saving conversation to database...")
    print(f"   User: {user_id}")
    print(f"   Channel: {channel_id}")
    print(f"   Message length: {len(message)} chars")
    print(f"   Response length: {len(response)} chars")

    try:
        # Prepare data for database insertion
        data = {
            "user_id": user_id,
            "channel_id": channel_id,
            "user_message": message,
            "bot_response": response,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Insert into Supabase table
        result = supabase.table("conversation_history").insert(data).execute()
        print(f"   ✅ Conversation saved successfully (ID: {result.data[0]['id'] if result.data else 'unknown'})")

    except Exception as e:
        print(f"   ❌ Error saving to Supabase: {e}")
        # Don't crash the bot if database save fails - just log it


def get_conversation_history(user_id: str, channel_id: str, limit: int = 10):
    """
    Retrieve recent conversation history from Supabase.
    This provides context for the AI to remember past conversations.

    Args:
        user_id: Discord user ID
        channel_id: Discord channel ID
        limit: Maximum number of conversations to retrieve (default: 10)

    Returns:
        List of conversation dictionaries in chronological order
    """
    print(f"\n📖 Retrieving conversation history...")
    print(f"   User: {user_id}")
    print(f"   Channel: {channel_id}")
    print(f"   Limit: {limit} conversations")

    try:
        # Query Supabase for this user's conversation history in this channel
        response = supabase.table("conversation_history")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("channel_id", channel_id)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()

        # Reverse to get chronological order (oldest to newest)
        history = list(reversed(response.data)) if response.data else []

        print(f"   ✅ Retrieved {len(history)} past conversations")
        return history

    except Exception as e:
        print(f"   ❌ Error retrieving from Supabase: {e}")
        return []  # Return empty list if database query fails


# ==================== LangGraph AI Node ====================

def call_ai_model(state: State):
    """
    Call Anthropic Claude API with conversation history for context.
    This is the core AI function that generates intelligent responses.

    Args:
        state: LangGraph state containing messages, user_id, and channel_id

    Returns:
        Dictionary with AI response message
    """
    print(f"\n🤖 Calling AI model (Claude Sonnet 4)...")

    # Get conversation history from Supabase for context
    history = get_conversation_history(state["user_id"], state["channel_id"])

    # Build context messages from history (last 5 conversations for token efficiency)
    context_messages = []
    history_to_use = history[-5:]  # Use only last 5 conversations

    print(f"   📚 Building context from {len(history_to_use)} past conversations")

    for entry in history_to_use:
        # Add user message
        context_messages.append({
            "role": "user",
            "content": entry["user_message"]
        })
        # Add bot response
        context_messages.append({
            "role": "assistant",
            "content": entry["bot_response"]
        })

    # Add current message to context
    current_message = state["messages"][-1]["content"]
    context_messages.append({
        "role": "user",
        "content": current_message
    })

    print(f"   💬 Current message: \"{current_message[:50]}{'...' if len(current_message) > 50 else ''}\"")
    print(f"   📊 Total context messages: {len(context_messages)}")

    try:
        # Call Anthropic API with context
        print(f"   ⏳ Waiting for Claude API response...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",  # Using Claude Sonnet 4
            max_tokens=1000,  # Maximum response length
            system=SYSTEM_PROMPT,  # Sports betting focused system prompt
            messages=context_messages
        )

        # Extract AI response text
        ai_response = response.content[0].text
        print(f"   ✅ AI response received ({len(ai_response)} chars)")
        print(f"   💭 Response preview: \"{ai_response[:80]}{'...' if len(ai_response) > 80 else ''}\"")

        # Save conversation to database for future context
        save_conversation_to_supabase(
            state["user_id"],
            state["channel_id"],
            current_message,
            ai_response
        )

        # Return response in LangGraph format
        return {
            "messages": [{"role": "assistant", "content": ai_response}]
        }

    except Exception as e:
        print(f"   ❌ Error calling Anthropic API: {e}")
        # Return error message instead of crashing
        error_msg = "Sorry, I encountered an error processing your request. Please try again."
        return {
            "messages": [{"role": "assistant", "content": error_msg}]
        }


# ==================== Build LangGraph ====================

def create_conversation_graph():
    """
    Create the LangGraph workflow for managing conversation state.
    This creates a state machine that handles the conversation flow.

    Returns:
        Compiled LangGraph application with memory
    """
    print("\n🔧 Building LangGraph workflow...")

    # Initialize the state graph with our State schema
    workflow = StateGraph(State)

    # Add the AI response node (our main processing function)
    workflow.add_node("ai_response", call_ai_model)
    print("   ✅ Added AI response node")

    # Set the entry point (where conversations start)
    workflow.set_entry_point("ai_response")
    print("   ✅ Set entry point")

    # Add edge to end (after AI response, conversation ends)
    workflow.add_edge("ai_response", END)
    print("   ✅ Added end edge")

    # Compile with memory saver for state persistence
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    print("   ✅ Compiled with memory saver")

    return app


# Initialize the graph
print("\n🚀 Initializing conversation graph...")
conversation_graph = create_conversation_graph()
print("✅ Conversation graph ready!")


# ==================== Discord Bot Setup ====================

# Configure Discord intents (permissions for what the bot can see/do)
print("\n🔐 Configuring Discord intents...")
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.messages = True  # Required to receive messages
intents.guilds = True  # Required to access server information
print("   ✅ Intents configured (message_content, messages, guilds)")

# Initialize Discord bot with command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)
print("   ✅ Discord bot initialized with prefix '!'")


@bot.event
async def on_ready():
    """
    Event triggered when bot successfully connects to Discord.
    This runs once when the bot starts up.
    """
    print("\n" + "=" * 60)
    print("🎉 BOT SUCCESSFULLY CONNECTED TO DISCORD!")
    print("=" * 60)
    print(f"   Bot Name: {bot.user.name}")
    print(f"   Bot ID: {bot.user.id}")
    print(f"   Connected to {len(bot.guilds)} server(s)")

    # List all servers the bot is in
    for guild in bot.guilds:
        print(f"      - {guild.name} (ID: {guild.id})")

    print("=" * 60)

    # Set bot status/activity (what users see under the bot's name)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="sports betting markets 📊"
        )
    )
    print("✅ Bot status set: Watching sports betting markets 📊")
    print("\n🤖 Bot is now ready to receive messages!")
    print("=" * 60)


@bot.event
async def on_message(message):
    """
    Event triggered when any message is sent in channels the bot can see.
    This is the main message handler for the bot.

    Args:
        message: Discord message object containing all message info
    """
    # Ignore messages from the bot itself to prevent infinite loops
    if message.author == bot.user:
        return

    # Only respond when bot is mentioned or in DMs
    is_mentioned = bot.user.mentioned_in(message)
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_mentioned or is_dm:
        print("\n" + "=" * 60)
        print("📨 NEW MESSAGE RECEIVED")
        print("=" * 60)
        print(f"   From: {message.author.name} (ID: {message.author.id})")
        print(f"   Channel: {message.channel.name if hasattr(message.channel, 'name') else 'DM'} (ID: {message.channel.id})")
        print(f"   Mentioned: {is_mentioned}")
        print(f"   DM: {is_dm}")

        # Remove bot mention from message content
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        print(f"   Message: \"{content}\"")

        # Handle empty messages (just a mention with no text)
        if not content:
            print("   ⚠️  Empty message detected - sending help prompt")
            await message.channel.send("Hey! How can I help you with sports betting or arbitrage today?")
            return

        # Show typing indicator while processing
        print("   ⌨️  Showing typing indicator...")
        async with message.channel.typing():
            try:
                print("   🔄 Processing message through LangGraph...")

                # Prepare state for LangGraph
                state = {
                    "messages": [{"role": "user", "content": content}],
                    "user_id": str(message.author.id),
                    "channel_id": str(message.channel.id)
                }

                # Create unique thread ID for this user/channel combination
                thread_id = f"{message.author.id}_{message.channel.id}"
                config = {"configurable": {"thread_id": thread_id}}

                print(f"   🧵 Thread ID: {thread_id}")

                # Run through LangGraph (this calls the AI and saves to database)
                result = conversation_graph.invoke(state, config)

                # Get AI response from result
                ai_message = result["messages"][-1]["content"]

                print(f"   ✅ Response generated ({len(ai_message)} chars)")

                # Discord has a 2000 character limit per message
                # Split long messages into chunks if needed
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
                print("=" * 60)
                await message.channel.send("Sorry, I encountered an error processing your message. Please try again.")

    # Process other commands (like !help, !clear, !stats)
    await bot.process_commands(message)


@bot.command(name="clear")
async def clear_history(ctx):
    """
    Command to clear conversation history for the user.
    Usage: !clear

    This deletes all past conversations from the database for this user in this channel.
    """
    print(f"\n🗑️  CLEAR command received")
    print(f"   User: {ctx.author.name} (ID: {ctx.author.id})")
    print(f"   Channel: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'} (ID: {ctx.channel.id})")

    try:
        # Delete all conversations for this user in this channel
        print(f"   🔄 Deleting conversation history from database...")
        supabase.table("conversation_history")\
            .delete()\
            .eq("user_id", str(ctx.author.id))\
            .eq("channel_id", str(ctx.channel.id))\
            .execute()

        print(f"   ✅ Conversation history cleared successfully")
        await ctx.send("✅ Conversation history cleared!")

    except Exception as e:
        print(f"   ❌ Error clearing history: {e}")
        await ctx.send(f"❌ Error clearing history: {e}")


@bot.command(name="stats")
async def stats(ctx):
    """
    Command to show conversation statistics for the user.
    Usage: !stats

    Shows how many messages the user has sent to the bot in this channel.
    """
    print(f"\n📊 STATS command received")
    print(f"   User: {ctx.author.name} (ID: {ctx.author.id})")
    print(f"   Channel: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'DM'} (ID: {ctx.channel.id})")

    try:
        # Query database for conversation count
        print(f"   🔄 Querying database for conversation count...")
        response = supabase.table("conversation_history")\
            .select("*", count="exact")\
            .eq("user_id", str(ctx.author.id))\
            .execute()

        # Count total conversations
        count = len(response.data) if response.data else 0
        print(f"   📈 Found {count} conversations")

        # Create embed (fancy formatted message)
        embed = discord.Embed(
            title="📊 Your Conversation Stats",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Messages", value=str(count), inline=False)
        embed.set_footer(text=f"User ID: {ctx.author.id}")

        print(f"   📤 Sending stats embed...")
        await ctx.send(embed=embed)
        print(f"   ✅ Stats sent successfully")

    except Exception as e:
        print(f"   ❌ Error fetching stats: {e}")
        await ctx.send(f"❌ Error fetching stats: {e}")


@bot.command(name="bot_help")
async def help_command(ctx):
    """
    Command to show help information about the bot.
    Usage: !help

    Displays all available commands and how to use the bot.
    """
    print(f"\n❓ HELP command received")
    print(f"   User: {ctx.author.name} (ID: {ctx.author.id})")

    # Create detailed help embed
    embed = discord.Embed(
        title="🤖 Bot Help - Sports Betting AI Assistant",
        description="I'm here to help with sports betting and arbitrage!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="💬 How to Chat",
        value="Just mention me (@bot) or DM me to start a conversation!",
        inline=False
    )

    embed.add_field(
        name="📋 Commands",
        value=(
            "`!clear` - Clear your conversation history\n"
            "`!stats` - View your conversation statistics\n"
            "`!help` - Show this help message"
        ),
        inline=False
    )

    embed.add_field(
        name="🎯 What I'm Good At",
        value=(
            "• Sports betting strategies\n"
            "• Arbitrage opportunities\n"
            "• Odds analysis\n"
            "• Risk management\n"
            "• Bankroll management"
        ),
        inline=False
    )

    print(f"   📤 Sending help embed...")
    await ctx.send(embed=embed)
    print(f"   ✅ Help sent successfully")


# ==================== Run Bot ====================

if __name__ == "__main__":
    """
    Main entry point for the Discord bot.
    This runs when you execute: python discord_bot.py
    """
    print("\n" + "=" * 60)
    print("🔍 PERFORMING PRE-FLIGHT CHECKS")
    print("=" * 60)

    # Check that all required environment variables are present
    missing_vars = []

    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        missing_vars.append("DISCORD_BOT_TOKEN")
    else:
        print("✅ Discord token found")

    if not ANTHROPIC_API_KEY:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set!")
        missing_vars.append("ANTHROPIC_API_KEY")
    else:
        print("✅ Anthropic API key found")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERROR: SUPABASE_URL and SUPABASE_KEY environment variables not set!")
        if not SUPABASE_URL:
            missing_vars.append("SUPABASE_URL")
        if not SUPABASE_KEY:
            missing_vars.append("SUPABASE_KEY")
    else:
        print("✅ Supabase credentials found")

    # If any variables are missing, exit with error
    if missing_vars:
        print("\n" + "=" * 60)
        print("❌ STARTUP FAILED - Missing environment variables:")
        for var in missing_vars:
            print(f"   • {var}")
        print("\nPlease set these in your .env file (local) or Heroku config (production)")
        print("=" * 60)
        exit(1)

    # All checks passed - start the bot!
    print("\n" + "=" * 60)
    print("✅ ALL PRE-FLIGHT CHECKS PASSED")
    print("=" * 60)
    print("\n🚀 Starting Discord bot...")
    print("⏳ Connecting to Discord... (this may take a few seconds)")
    print("\n" + "=" * 60)

    try:
        # Run the bot (this blocks until bot disconnects)
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("\n❌ LOGIN FAILED - Invalid Discord token!")
        print("Please check your DISCORD_BOT_TOKEN in your environment variables")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        exit(1)