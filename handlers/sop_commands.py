"""
SOP Upload - Correct Flow
File is command parameter → dropdown "New or Replace?" → process
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select
import os

from services.document_processor import DocumentProcessor
from services.knowledge_base import KnowledgeBaseService
from utils import PermissionManager


class SOPCommands(commands.Cog):
    """SOP management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.kb = KnowledgeBaseService()
        self.processor = DocumentProcessor()

    @app_commands.command(name="sop_upload", description="Upload an SOP document")
    @app_commands.describe(file="Attach your .txt file")
    async def sop_upload(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload SOP with file as command parameter"""
        username = str(interaction.user).split('#')[0]

        if not PermissionManager.is_admin(username):
            await interaction.response.send_message("❌ Only admins can upload SOPs.", ephemeral=True)
            return

        if not file.filename.endswith('.txt'):
            await interaction.response.send_message("❌ Only .txt files supported!", ephemeral=True)
            return

        # Download file
        os.makedirs('uploads', exist_ok=True)
        file_path = f"uploads/{file.filename}"
        await file.save(file_path)

        # Show action selector
        view = ActionSelectorView(self, file_path, file.filename, username)
        await interaction.response.send_message(
            f"✅ **File received:** {file.filename}\n\n**What would you like to do?**",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="sop_list", description="List all SOP documents")
    async def sop_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        documents = self.kb.list_documents()

        if not documents:
            await interaction.followup.send("📚 No SOPs yet.\nUse `/sop_upload` to add one!")
            return

        embed = discord.Embed(title="📚 SOP Documents", description=f"Total: {len(documents)}", color=discord.Color.blue())

        for doc in documents[:25]:
            embed.add_field(
                name=doc['name_of_file'],
                value=f"{doc['description']}\n*{doc['timestamp'][:10]} by {doc['uploaded_by']}*",
                inline=False
            )

        if len(documents) > 25:
            embed.set_footer(text=f"Showing 25 of {len(documents)}")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="sop_delete", description="Delete an SOP document")
    async def sop_delete(self, interaction: discord.Interaction):
        username = str(interaction.user).split('#')[0]

        if not PermissionManager.is_admin(username):
            await interaction.response.send_message("❌ Only admins can delete SOPs.", ephemeral=True)
            return

        documents = self.kb.list_documents()

        if not documents:
            await interaction.response.send_message("📚 No documents to delete.", ephemeral=True)
            return

        view = DeleteDocumentView(self, documents, username)
        await interaction.response.send_message("**🗑️ Select document to delete:**", view=view, ephemeral=True)

    @app_commands.command(name="sop_info", description="Knowledge base statistics")
    async def sop_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        info = self.cog.kb.get_collection_info()
        documents = self.kb.list_documents()

        embed = discord.Embed(title="📊 Knowledge Base Stats", color=discord.Color.blue())
        embed.add_field(name="Documents", value=str(len(documents)), inline=True)
        embed.add_field(name="Chunks", value=str(info.get('total_points', '?')), inline=True)
        embed.add_field(name="Status", value=info.get('status', '?'), inline=True)

        if documents:
            recent = documents[0]
            embed.add_field(name="Most Recent", value=f"{recent['name_of_file']}\n{recent['timestamp'][:10]}", inline=False)

        await interaction.followup.send(embed=embed)


# ==================== VIEWS ====================

class ActionSelectorView(View):
    """Step 1: Choose New or Replace"""

    def __init__(self, cog, file_path, filename, username):
        super().__init__(timeout=300)
        self.cog = cog
        self.file_path = file_path
        self.filename = filename
        self.username = username

        select = ActionSelect(cog, file_path, filename, username)
        self.add_item(select)

        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    async def cancel(self, interaction: discord.Interaction):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        await interaction.response.edit_message(content="❌ **Cancelled**", view=None)


class ActionSelect(Select):
    """Dropdown: New or Replace"""

    def __init__(self, cog, file_path, filename, username):
        options = [
            discord.SelectOption(label="📄 Upload as New Document", value="new"),
            discord.SelectOption(label="🔄 Replace Existing Document", value="replace")
        ]
        super().__init__(placeholder="Choose action...", options=options)

        self.cog = cog
        self.file_path = file_path
        self.filename = filename
        self.username = username

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]

        if action == "new":
            view = NameDescriptionView(self.cog, self.file_path, self.filename, self.username)
            await interaction.response.edit_message(
                content=f"✅ **Action: Upload New**\n\n**Enter document details:**",
                view=view
            )
        else:  # replace
            documents = self.cog.kb.list_documents()
            if not documents:
                await interaction.response.edit_message(content="❌ No documents to replace!", view=None)
                if os.path.exists(self.file_path):
                    os.remove(self.file_path)
                return

            view = ReplaceDocumentView(self.cog, documents, self.file_path, self.username)
            await interaction.response.edit_message(
                content=f"✅ **Action: Replace**\n\n**Select document:**",
                view=view
            )


class NameDescriptionView(View):
    """Step 2a: Name/Description Options"""

    def __init__(self, cog, file_path, filename, username):
        super().__init__(timeout=300)
        self.cog = cog
        self.file_path = file_path
        self.filename = filename
        self.username = username
        self.doc_name = filename.replace('.txt', '').replace('_', ' ').title()
        self.description = f"SOP: {self.doc_name}"

        use_defaults_btn = Button(label=f"✅ Use Defaults", style=discord.ButtonStyle.success)
        use_defaults_btn.callback = self.use_defaults
        self.add_item(use_defaults_btn)

        manual_btn = Button(label="✏️ Enter Manually", style=discord.ButtonStyle.primary)
        manual_btn.callback = self.manual_entry
        self.add_item(manual_btn)

        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    async def use_defaults(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="⏳ **Processing...**", view=None)
        await self.process_upload(interaction, self.doc_name, self.description)

    async def manual_entry(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=f"📝 **Type in next message:**\n```\nname: Your Name\ndescription: Your description\n```\n5 minutes.",
            view=None
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=300.0)
            content = msg.content
            name = description = None

            for line in content.split('\n'):
                if line.strip().lower().startswith('name:'):
                    name = line.split(':', 1)[1].strip()
                elif line.strip().lower().startswith('description:'):
                    description = line.split(':', 1)[1].strip()

            try:
                await msg.delete()
            except:
                pass

            if not name:
                name = self.doc_name
            if not description:
                description = self.description

            await interaction.edit_original_response(content="⏳ **Processing...**")
            await self.process_upload(interaction, name, description)

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Error: {str(e)}")
            if os.path.exists(self.file_path):
                os.remove(self.file_path)

    async def process_upload(self, interaction, name, description):
        try:
            existing = self.cog.kb.list_documents()
            if any(doc['name_of_file'] == name for doc in existing):
                await interaction.edit_original_response(content=f"❌ **{name}** exists! Use replace.")
                if os.path.exists(self.file_path):
                    os.remove(self.file_path)
                return

            text, chunks = self.cog.processor.process_document(file_path=self.file_path, title=name)
            chunks_stored = self.cog.kb.store_document(
                name_of_file=name,
                description=description,
                chunks=chunks,
                uploaded_by=self.username
            )
            os.remove(self.file_path)

            embed = discord.Embed(title="✅ Document Uploaded", description=f"**{name}**", color=discord.Color.green())
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Chunks", value=str(chunks_stored), inline=True)
            embed.add_field(name="By", value=self.username, inline=True)

            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            await interaction.edit_original_response(content=f"❌ Error: {str(e)}")

    async def cancel(self, interaction: discord.Interaction):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        await interaction.response.edit_message(content="❌ **Cancelled**", view=None)


class ReplaceDocumentView(View):
    """Step 2b: Select Document to Replace"""

    def __init__(self, cog, documents, file_path, username):
        super().__init__(timeout=300)
        select = ReplaceDocumentSelect(cog, documents, file_path, username)
        self.add_item(select)

        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

        self.file_path = file_path

    async def cancel(self, interaction: discord.Interaction):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        await interaction.response.edit_message(content="❌ **Cancelled**", view=None)


class ReplaceDocumentSelect(Select):
    """Dropdown for Replace"""

    def __init__(self, cog, documents, file_path, username):
        options = [
            discord.SelectOption(
                label=doc['name_of_file'][:100],
                description=doc['description'][:100] if doc['description'] else "No description",
                value=doc['name_of_file']
            )
            for doc in documents[:25]
        ]
        super().__init__(placeholder="Choose document...", options=options)

        self.cog = cog
        self.file_path = file_path
        self.username = username

    async def callback(self, interaction: discord.Interaction):
        selected_doc = self.values[0]
        await interaction.response.edit_message(content="⏳ **Replacing...**", view=None)

        try:
            deleted = self.cog.kb.delete_document(selected_doc)
            docs = self.cog.kb.list_documents()
            original = next((d for d in docs if d['name_of_file'] == selected_doc), None)
            description = original['description'] if original else f"SOP: {selected_doc}"

            text, chunks = self.cog.processor.process_document(file_path=self.file_path, title=selected_doc)
            chunks_stored = self.cog.kb.store_document(
                name_of_file=selected_doc,
                description=description,
                chunks=chunks,
                uploaded_by=self.username
            )
            os.remove(self.file_path)

            embed = discord.Embed(title="✅ Document Replaced", description=f"**{selected_doc}**", color=discord.Color.green())
            embed.add_field(name="Old Chunks", value=str(deleted), inline=True)
            embed.add_field(name="New Chunks", value=str(chunks_stored), inline=True)
            embed.add_field(name="By", value=self.username, inline=True)

            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            await interaction.edit_original_response(content=f"❌ Error: {str(e)}")


class DeleteDocumentView(View):
    """Delete Flow"""

    def __init__(self, cog, documents, username):
        super().__init__(timeout=300)
        select = DeleteDocumentSelect(cog, documents, username)
        self.add_item(select)

        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ **Cancelled**", view=None)


class DeleteDocumentSelect(Select):
    """Select to Delete"""

    def __init__(self, cog, documents, username):
        options = [
            discord.SelectOption(
                label=doc['name_of_file'][:100],
                description=doc['description'][:100] if doc['description'] else "No description",
                value=doc['name_of_file']
            )
            for doc in documents[:25]
        ]
        super().__init__(placeholder="Choose document...", options=options)

        self.cog = cog
        self.username = username

    async def callback(self, interaction: discord.Interaction):
        selected_doc = self.values[0]
        view = ConfirmDeleteView(self.cog, selected_doc, self.username)
        await interaction.response.edit_message(
            content=f"⚠️ **Delete {selected_doc}?**\n\nCannot be undone!",
            view=view
        )


class ConfirmDeleteView(View):
    """Confirm Deletion"""

    def __init__(self, cog, document_name, username):
        super().__init__(timeout=60)
        self.cog = cog
        self.document_name = document_name
        self.username = username

        confirm_btn = Button(label="✅ Yes, Delete", style=discord.ButtonStyle.danger)
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)

        cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_btn.callback = self.cancel
        self.add_item(cancel_btn)

    async def confirm(self, interaction: discord.Interaction):
        await interaction.response.defer()
        deleted = self.cog.kb.delete_document(self.document_name)

        embed = discord.Embed(title="✅ Document Deleted", description=f"**{self.document_name}**", color=discord.Color.green())
        embed.add_field(name="Chunks Deleted", value=str(deleted), inline=True)
        embed.add_field(name="By", value=self.username, inline=True)

        await interaction.edit_original_response(content=None, embed=embed, view=None)

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="❌ **Cancelled**", view=None)


async def setup(bot: commands.Bot):
    await bot.add_cog(SOPCommands(bot))