"""
Document processing service for RAG knowledge base
Handles chunking and embedding generation
"""
from typing import List, Dict, Tuple
import tiktoken
from openai import OpenAI
from config.config import OPENAI_API_KEY


class DocumentProcessor:
    """Handles document processing: chunking and embedding generation"""

    def __init__(self):
        """Initialize OpenAI client and tokenizer"""
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.encoding = tiktoken.get_encoding("cl100k_base")  # For counting tokens

        # Chunking parameters
        self.chunk_size = 1500  # tokens
        self.chunk_overlap = 150  # tokens

    def read_text_file(self, file_path: str) -> str:
        """
        Read text from file

        Args:
            file_path: Path to text file

        Returns:
            File contents as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoding.encode(text))

    def chunk_text(self, text: str) -> List[Dict[str, any]]:
        """
        Split text into chunks based on section separators (---) and token limits WITH OVERLAP

        Strategy:
        1. Split by "---" (section separators)
        2. Group sections into chunks up to chunk_size
        3. Maintain overlap between chunks for context (last N tokens of previous chunk)

        Args:
            text: Full document text

        Returns:
            List of chunks with metadata
        """
        print(f"\n📄 Chunking document with {self.chunk_overlap} token overlap...")
        print(f"   Using '---' as section separator")

        # Split by section separator (---)
        sections = [s.strip() for s in text.split('---') if s.strip()]
        print(f"   Found {len(sections)} sections")

        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        previous_overlap_text = ""  # Track text to carry over

        for section in sections:
            section_tokens = self.count_tokens(section)

            # If single section exceeds chunk_size, split it by paragraphs as fallback
            if section_tokens > self.chunk_size:
                print(f"   ⚠️  Section too large ({section_tokens} tokens), splitting by paragraphs...")

                # Split large section by paragraphs
                paragraphs = [p.strip() for p in section.split('\n\n') if p.strip()]

                for para in paragraphs:
                    para_tokens = self.count_tokens(para)

                    # If even a paragraph is too large, split by sentences
                    if para_tokens > self.chunk_size:
                        sentences = para.split('. ')
                        for sentence in sentences:
                            sentence = sentence.strip() + '. '
                            sentence_tokens = self.count_tokens(sentence)

                            if current_tokens + sentence_tokens < self.chunk_size:
                                current_chunk += sentence
                                current_tokens += sentence_tokens
                            else:
                                if current_chunk:
                                    chunks.append({
                                        'index': chunk_index,
                                        'content': current_chunk.strip(),
                                        'token_count': current_tokens
                                    })
                                    chunk_index += 1

                                    # Get overlap text from end of current chunk
                                    previous_overlap_text = self._get_overlap_text(current_chunk)

                                # Start new chunk with overlap from previous
                                current_chunk = previous_overlap_text + sentence
                                current_tokens = self.count_tokens(current_chunk)

                    # Normal paragraph handling
                    elif current_tokens + para_tokens < self.chunk_size:
                        current_chunk += para + "\n\n"
                        current_tokens += para_tokens
                    else:
                        if current_chunk:
                            chunks.append({
                                'index': chunk_index,
                                'content': current_chunk.strip(),
                                'token_count': current_tokens
                            })
                            chunk_index += 1

                            # Get overlap text from end of current chunk
                            previous_overlap_text = self._get_overlap_text(current_chunk)

                        # Start new chunk with overlap + new paragraph
                        current_chunk = previous_overlap_text + para + "\n\n"
                        current_tokens = self.count_tokens(current_chunk)

            # Normal case: section fits within token limits
            elif current_tokens + section_tokens < self.chunk_size:
                # Add section separator if not first section in chunk
                if current_chunk:
                    current_chunk += "\n---\n\n"
                current_chunk += section
                current_tokens = self.count_tokens(current_chunk)

            # Start new chunk with overlap
            else:
                if current_chunk:
                    chunks.append({
                        'index': chunk_index,
                        'content': current_chunk.strip(),
                        'token_count': current_tokens
                    })
                    chunk_index += 1

                    # Get overlap text from end of current chunk
                    previous_overlap_text = self._get_overlap_text(current_chunk)

                # Start new chunk with overlap + new section
                current_chunk = previous_overlap_text + section
                current_tokens = self.count_tokens(current_chunk)

        # Add final chunk
        if current_chunk:
            chunks.append({
                'index': chunk_index,
                'content': current_chunk.strip(),
                'token_count': current_tokens
            })

        print(f"   ✅ Created {len(chunks)} chunks")
        print(f"   Average chunk size: {sum(c['token_count'] for c in chunks) / len(chunks):.0f} tokens")

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """
        Extract the last N tokens from text to use as overlap for next chunk

        Args:
            text: Text to extract overlap from

        Returns:
            Text containing approximately chunk_overlap tokens from the end
        """
        tokens = self.encoding.encode(text)

        if len(tokens) <= self.chunk_overlap:
            # If text is shorter than overlap size, return entire text
            return text + "\n\n"

        # Get last chunk_overlap tokens
        overlap_tokens = tokens[-self.chunk_overlap:]
        overlap_text = self.encoding.decode(overlap_tokens)

        # Try to start at a sentence boundary for cleaner overlap
        # Find the first '. ' or start of text
        sentence_start = overlap_text.find('. ')
        if sentence_start != -1 and sentence_start < len(overlap_text) // 2:
            # Start after the period if it's in the first half
            overlap_text = overlap_text[sentence_start + 2:]

        return overlap_text + "\n\n"

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for text chunks using OpenAI

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        print(f"\n🔮 Generating embeddings for {len(texts)} chunks...")

        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",  # 1536 dimensions, cheap
                input=texts
            )

            embeddings = [item.embedding for item in response.data]
            print(f"   ✅ Generated {len(embeddings)} embeddings")

            return embeddings

        except Exception as e:
            print(f"   ❌ Error generating embeddings: {e}")
            raise

    def process_document(
        self,
        file_path: str,
        title: str,
        category: str = None,
        description: str = None
    ) -> Tuple[str, List[Dict]]:
        """
        Complete document processing pipeline

        Args:
            file_path: Path to document file
            title: Document title
            category: Optional category
            description: Optional description

        Returns:
            Tuple of (full_text, chunks_with_embeddings)
        """
        print(f"\n{'='*60}")
        print(f"📚 Processing Document: {title}")
        print(f"{'='*60}")

        # Read file
        text = self.read_text_file(file_path)
        print(f"   Document size: {len(text)} characters, {self.count_tokens(text)} tokens")

        # Chunk text
        chunks = self.chunk_text(text)

        # Generate embeddings (batch for efficiency)
        chunk_texts = [chunk['content'] for chunk in chunks]
        embeddings = self.generate_embeddings(chunk_texts)

        # Combine chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding

        print(f"✅ Document processing complete!")
        print(f"{'='*60}\n")

        return text, chunks