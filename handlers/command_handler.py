"""
Discord bot commands handler
"""
import discord
from discord.ext import commands

from database import Database
from utils import PermissionManager
from handlers.message_handler import MessageHandler


class CommandHandler:
    """Handles all Discord bot commands"""
    
    def __init__(self, bot: commands.Bot, database: Database, message_handler: MessageHandler):
        """
        Initialize command handler
        
        Args:
            bot: Discord bot instance
            database: Database instance
            message_handler: Message handler instance
        """
        self.bot = bot
        self.db = database
        self.message_handler = message_handler
        self._register_commands()
    
    def _register_commands(self):
        """Register all bot commands"""
        
        @self.bot.command(name="clear")
        async def clear_history(ctx):
            """Clear conversation history for the user"""
            print(f"\n🗑️  CLEAR command received")
            print(f"   User: {ctx.author.name} (ID: {ctx.author.id})")
            
            success = self.db.clear_conversation_history(
                str(ctx.author.id),
                str(ctx.channel.id)
            )
            
            if success:
                await ctx.send("✅ Conversation history cleared!")
            else:
                await ctx.send("❌ Error clearing history. Please try again.")
        
        @self.bot.command(name="stats")
        async def stats(ctx):
            """Show conversation statistics"""
            print(f"\n📊 STATS command received")
            print(f"   User: {ctx.author.name} (ID: {ctx.author.id})")
            
            count = self.db.get_conversation_count(str(ctx.author.id))
            
            embed = discord.Embed(
                title="📊 Your Conversation Stats",
                color=discord.Color.blue()
            )
            embed.add_field(name="Total Messages", value=str(count), inline=False)
            embed.set_footer(text=f"User ID: {ctx.author.id}")
            
            await ctx.send(embed=embed)
        
        @self.bot.command(name="mysheet")
        async def my_sheet(ctx):
            """Fetch your own Google Sheet tasks"""
            print(f"\n📊 MYSHEET command received")
            print(f"   User: {ctx.author.name}")
            
            username = str(ctx.author).split('#')[0]
            
            success, message = self.message_handler.fetch_user_sheet_data(username)
            
            # Split long messages if needed
            if len(message) > 2000:
                chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(message)
        
        @self.bot.command(name="sheet")
        @commands.has_permissions(administrator=True)
        async def fetch_sheet(ctx, employee_username: str = None):
            """
            Fetch an employee's Google Sheet tasks (Admin only)
            
            Usage: !sheet <employee_username>
            """
            print(f"\n📊 SHEET command received")
            print(f"   Admin: {ctx.author.name}")
            print(f"   Target: {employee_username}")
            
            requester_username = str(ctx.author).split('#')[0]
            
            if not PermissionManager.is_admin(requester_username):
                await ctx.send("❌ This command is only available to admins.")
                return
            
            if not employee_username:
                await ctx.send("❌ Please specify an employee username. Usage: `!sheet <username>`")
                return
            
            success, message = self.message_handler.fetch_user_sheet_data(
                employee_username,
                requester_username
            )
            
            # Split long messages if needed
            if len(message) > 2000:
                chunks = [message[i:i+2000] for i in range(0, len(message), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(message)
        
        @self.bot.command(name="employees")
        async def list_employees(ctx):
            """List all employees with sheets"""
            print(f"\n👥 EMPLOYEES command received")
            
            username = str(ctx.author).split('#')[0]
            accessible_employees = PermissionManager.get_accessible_employees(username)
            
            if not accessible_employees:
                await ctx.send("❌ You don't have access to any employee sheets.")
                return
            
            embed = discord.Embed(
                title="👥 Employees with Sheets",
                color=discord.Color.green()
            )
            
            employee_list = "\n".join([f"• {emp}" for emp in accessible_employees])
            embed.add_field(name="Accessible Employees", value=employee_list, inline=False)
            
            if PermissionManager.is_admin(username):
                embed.set_footer(text="You can view any employee's sheet using !sheet <username>")
            else:
                embed.set_footer(text="Use !mysheet to view your tasks")
            
            await ctx.send(embed=embed)
        
        @self.bot.command(name="bot_help")
        async def bot_help(ctx):
            """Show bot help information"""
            print(f"\n❓ HELP command received")
            
            username = str(ctx.author).split('#')[0]
            role = PermissionManager.get_user_role(username)
            
            embed = discord.Embed(
                title="🤖 Bot Help - Task Management Assistant",
                description="I help manage sports betting arbitrage tasks!",
                color=discord.Color.green()
            )
            
            # Basic commands for everyone
            embed.add_field(
                name="💬 Chat Commands",
                value="Mention me (@bot) or DM me to chat about tasks and sports betting",
                inline=False
            )
            
            # Employee commands
            if role in ["employee", "admin"]:
                embed.add_field(
                    name="📊 Your Commands",
                    value=(
                        "`!mysheet` - View your task sheet\n"
                        "`!stats` - View your conversation stats\n"
                        "`!clear` - Clear your conversation history\n"
                    ),
                    inline=False
                )
            
            # Admin-only commands
            if role == "admin":
                embed.add_field(
                    name="👑 Admin Commands",
                    value=(
                        "`!sheet <username>` - View any employee's sheet\n"
                        "`!employees` - List all employees\n"
                    ),
                    inline=False
                )
            
            # General commands
            embed.add_field(
                name="🛠️ General Commands",
                value="`!help` - Show this help message",
                inline=False
            )
            
            # Role indicator
            role_emoji = {"admin": "👑", "employee": "👤", "user": "🔵"}
            embed.set_footer(text=f"Your role: {role_emoji.get(role, '🔵')} {role.title()}")
            
            await ctx.send(embed=embed)
