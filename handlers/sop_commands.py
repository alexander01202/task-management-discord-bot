"""
Discord slash commands for SOP document management
Handles upload, replace, list, and delete operations with Qdrant
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os

from services.document_processor import DocumentProcessor
from services.knowledge_base import KnowledgeBaseService
from utils import PermissionManager


class SOPCommands(commands.Cog):
    """Discord slash commands for SOP management"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.kb = KnowledgeBaseService()
        self.processor = DocumentProcessor()

        # Store temporary state for multi-step interactions
        self.upload_state = {}

    @app_commands.command(name="sop_upload", description="Upload or replace an SOP document")
    @app_commands.describe(
        action="Choose whether to upload a new document or replace an existing one",
        file="The .txt file to upload",
        name="Name of the document (e.g., 'Betano Verification Process')",
        description="Brief description of what this document covers"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Upload New Document", value="new"),
        app_commands.Choice(name="Replace Existing Document", value="replace")
    ])
    async def sop_upload(
            self,
            interaction: discord.Interaction,
            action: app_commands.Choice[str],
            file: discord.Attachment,
            name: Optional[str] = None,
            description: Optional[str] = None
    ):
        """
        Main slash command for uploading/replacing SOPs
        """
        # Check admin permission
        username = str(interaction.user).split('#')[0]
        if not PermissionManager.is_admin(username):
            await interaction.response.send_message(
                "❌ Only admins can upload SOPs.",
                ephemeral=True
            )
            return

        # Validate file type
        if not file.filename.endswith('.txt'):
            await interaction.response.send_message(
                "❌ Only .txt files are supported. Please upload a plain text file.",
                ephemeral=True
            )
            return

        # Use filename as name if not provided
        if not name:
            name = file.filename.replace('.txt', '').replace('_', ' ').title()

        if not description:
            description = f"SOP document: {name}"

        # Handle based on action
        if action.value == "new":
            await self._handle_new_upload(interaction, file, name, description, username)
        else:  # replace
            await self._handle_replace_upload(interaction, file, name, description, username)

    async def _handle_new_upload(
            self,
            interaction: discord.Interaction,
            file: discord.Attachment,
            name: str,
            description: str,
            username: str
    ):
        """Handle uploading a new document"""
        await interaction.response.defer(thinking=True)

        try:
            # Check if document with this name already exists
            existing_docs = self.kb.list_documents()
            if any(doc['name_of_file'] == name for doc in existing_docs):
                await interaction.followup.send(
                    f"⚠️ A document named **{name}** already exists!\n\n"
                    f"Use the 'Replace Existing Document' option if you want to update it."
                )
                return

            # Download and process
            chunks_stored = await self._process_and_upload(
                file, name, description, username
            )

            # Success message
            embed = discord.Embed(
                title="✅ New Document Uploaded",
                description=f"**{name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Chunks Created", value=str(chunks_stored), inline=True)
            embed.add_field(name="Uploaded By", value=username, inline=True)
            embed.set_footer(text="Employees can now ask questions about this document!")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error uploading document: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Error uploading document: {str(e)}"
            )

    async def _handle_replace_upload(
            self,
            interaction: discord.Interaction,
            file: discord.Attachment,
            name: str,
            description: str,
            username: str
    ):
        """Handle replacing an existing document"""
        await interaction.response.defer(thinking=True)

        try:
            # Check if document exists
            existing_docs = self.kb.list_documents()
            doc_exists = any(doc['name_of_file'] == name for doc in existing_docs)

            if not doc_exists:
                await interaction.followup.send(
                    f"⚠️ No document named **{name}** found.\n\n"
                    f"Use the 'Upload New Document' option to create it."
                )
                return

            # Delete old version
            deleted_chunks = self.kb.delete_document(name)

            # Upload new version
            chunks_stored = await self._process_and_upload(
                file, name, description, username
            )

            # Success message
            embed = discord.Embed(
                title="✅ Document Replaced",
                description=f"**{name}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Old Chunks Deleted", value=str(deleted_chunks), inline=True)
            embed.add_field(name="New Chunks Created", value=str(chunks_stored), inline=True)
            embed.add_field(name="Updated By", value=username, inline=True)
            embed.set_footer(text="Document has been updated successfully!")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error replacing document: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Error replacing document: {str(e)}"
            )

    async def _process_and_upload(
            self,
            file: discord.Attachment,
            name: str,
            description: str,
            username: str
    ) -> int:
        """
        Download file, process it, and upload to Qdrant

        Returns:
            Number of chunks stored
        """
        # Create uploads directory
        os.makedirs('uploads', exist_ok=True)

        # Download file
        file_path = f"uploads/{file.filename}"
        await file.save(file_path)
        print(f"   📥 File saved to: {file_path}")

        # Process document (chunk + embed)
        text, chunks = self.processor.process_document(
            file_path=file_path,
            title=name
        )

        # Store in Qdrant
        chunks_stored = self.kb.store_document(
            name_of_file=name,
            description=description,
            chunks=chunks,
            uploaded_by=username
        )

        # Clean up temp file
        os.remove(file_path)

        return chunks_stored

    @app_commands.command(name="sop_list", description="List all SOP documents")
    async def sop_list(self, interaction: discord.Interaction):
        """List all documents in knowledge base"""
        await interaction.response.defer(thinking=True)

        try:
            documents = self.kb.list_documents()

            if not documents:
                await interaction.followup.send(
                    "📚 No SOPs in knowledge base yet.\n"
                    "Admins can upload with `/sop_upload`"
                )
                return

            # Create embed
            embed = discord.Embed(
                title="📚 SOP Documents",
                description=f"Total: {len(documents)} document(s)",
                color=discord.Color.blue()
            )

            # Add up to 25 documents (Discord limit)
            for doc in documents[:25]:
                # Format timestamp
                timestamp = doc['timestamp'][:10]  # Just the date

                value = f"**Description:** {doc['description']}\n"
                value += f"**Uploaded:** {timestamp} by {doc['uploaded_by']}"

                embed.add_field(
                    name=doc['name_of_file'],
                    value=value,
                    inline=False
                )

            if len(documents) > 25:
                embed.set_footer(text=f"Showing 25 of {len(documents)} documents")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error listing documents: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}")

    @app_commands.command(name="sop_delete", description="Delete an SOP document")
    @app_commands.describe(name="Name of the document to delete")
    async def sop_delete(
            self,
            interaction: discord.Interaction,
            name: str
    ):
        """Delete a document from knowledge base"""
        # Check admin permission
        username = str(interaction.user).split('#')[0]
        if not PermissionManager.is_admin(username):
            await interaction.response.send_message(
                "❌ Only admins can delete SOPs.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            # Delete from Qdrant
            deleted_chunks = self.kb.delete_document(name)

            if deleted_chunks == 0:
                await interaction.followup.send(
                    f"⚠️ No document named **{name}** found."
                )
            else:
                embed = discord.Embed(
                    title="✅ Document Deleted",
                    description=f"**{name}**",
                    color=discord.Color.red()
                )
                embed.add_field(name="Chunks Deleted", value=str(deleted_chunks), inline=True)
                embed.add_field(name="Deleted By", value=username, inline=True)

                await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error deleting document: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}")

    @app_commands.command(name="sop_info", description="Get information about the knowledge base")
    async def sop_info(self, interaction: discord.Interaction):
        """Get knowledge base statistics"""
        await interaction.response.defer(thinking=True)

        try:
            # Get collection info
            info = self.kb.get_collection_info()
            documents = self.kb.list_documents()

            embed = discord.Embed(
                title="📊 Knowledge Base Statistics",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Total Documents",
                value=str(len(documents)),
                inline=True
            )

            embed.add_field(
                name="Total Chunks",
                value=str(info.get('total_points', 'Unknown')),
                inline=True
            )

            embed.add_field(
                name="Status",
                value=info.get('status', 'Unknown'),
                inline=True
            )

            if documents:
                # Get most recent document
                recent = documents[0]
                embed.add_field(
                    name="Most Recent Upload",
                    value=f"**{recent['name_of_file']}**\n{recent['timestamp'][:10]} by {recent['uploaded_by']}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error getting info: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}")

    @sop_upload.autocomplete('name')
    async def name_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str
    ) -> list[app_commands.Choice[str]]:
        """
        Autocomplete for document names when replacing
        Only shows options if action is 'replace'
        """
        try:
            # Get all documents
            documents = self.kb.list_documents()

            # Filter based on current input
            if current:
                filtered = [
                    doc['name_of_file']
                    for doc in documents
                    if current.lower() in doc['name_of_file'].lower()
                ]
            else:
                filtered = [doc['name_of_file'] for doc in documents]

            # Return as choices (max 25)
            return [
                app_commands.Choice(name=name, value=name)
                for name in filtered[:25]
            ]

        except Exception:
            return []

    @sop_delete.autocomplete('name')
    async def delete_name_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for document names when deleting"""
        try:
            documents = self.kb.list_documents()

            if current:
                filtered = [
                    doc['name_of_file']
                    for doc in documents
                    if current.lower() in doc['name_of_file'].lower()
                ]
            else:
                filtered = [doc['name_of_file'] for doc in documents]

            return [
                app_commands.Choice(name=name, value=name)
                for name in filtered[:25]
            ]

        except Exception:
            return []


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(SOPCommands(bot))
