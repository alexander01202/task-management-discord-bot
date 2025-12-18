"""
Knowledge base service using Qdrant Cloud - FIXED
Handles document storage, search, and deletion with metadata
"""
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from openai import OpenAI
from config.config import QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY


class KnowledgeBaseService:
    """Manages knowledge base using Qdrant Cloud"""

    COLLECTION_NAME = "sop_documents"

    def __init__(self):
        """Initialize Qdrant Cloud and OpenAI clients"""
        print("🔌 Connecting to Qdrant Cloud...")

        try:
            # Connect to Qdrant Cloud
            self.qdrant = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
            )

            # Initialize OpenAI for embeddings
            self.openai = OpenAI(api_key=OPENAI_API_KEY)

            # Ensure collection exists
            self._ensure_collection_exists()

            print("   ✅ Qdrant Cloud connected successfully")

        except Exception as e:
            print(f"   ❌ Qdrant initialization failed: {e}")
            raise

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            # Try to get collection info
            self.qdrant.get_collection(self.COLLECTION_NAME)
            print(f"   ✅ Collection '{self.COLLECTION_NAME}' exists")

        except Exception:
            # Collection doesn't exist, create it
            print(f"   📦 Creating collection '{self.COLLECTION_NAME}'...")

            self.qdrant.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=1536,  # OpenAI text-embedding-3-small dimension
                    distance=Distance.COSINE
                )
            )

            # Create payload indexes for efficient filtering
            self.qdrant.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="name_of_file",
                field_schema="keyword"
            )

            self.qdrant.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="timestamp",
                field_schema="datetime"
            )

            print(f"   ✅ Collection created with indexes")

    def store_document(
            self,
            name_of_file: str,
            description: str,
            chunks: List[Dict],
            uploaded_by: str
    ) -> int:
        """
        Store document chunks in Qdrant Cloud

        Args:
            name_of_file: Document name/title
            description: Brief description of document
            chunks: List of chunks with embeddings
            uploaded_by: Discord username of uploader

        Returns:
            Number of chunks stored
        """
        print(f"\n💾 Storing document in Qdrant Cloud...")
        print(f"   Document: {name_of_file}")
        print(f"   Chunks: {len(chunks)}")

        try:
            timestamp = datetime.now().isoformat()
            points = []

            for i, chunk in enumerate(chunks):
                # Create unique point ID
                point_id = str(uuid.uuid4())

                # Create point with metadata
                points.append(PointStruct(
                    id=point_id,
                    vector=chunk['embedding'],
                    payload={
                        'name_of_file': name_of_file,
                        'description': description,
                        'timestamp': timestamp,
                        'uploaded_by': uploaded_by,
                        'chunk_index': i,
                        'chunk_content': chunk['content'],
                        'token_count': chunk['token_count']
                    }
                ))

            # Upload to Qdrant in batch
            self.qdrant.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points
            )

            print(f"   ✅ Stored {len(chunks)} chunks successfully")
            return len(chunks)

        except Exception as e:
            print(f"   ❌ Error storing document: {e}")
            raise

    def delete_document(self, name_of_file: str) -> int:
        """
        Delete all chunks belonging to a document

        Args:
            name_of_file: Document name to delete

        Returns:
            Number of chunks deleted
        """
        print(f"\n🗑️  Deleting document from Qdrant...")
        print(f"   Document: {name_of_file}")

        try:
            # First, count how many chunks exist
            count_result = self.qdrant.count(
                collection_name=self.COLLECTION_NAME,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="name_of_file",
                            match=MatchValue(value=name_of_file)
                        )
                    ]
                )
            )

            chunks_count = count_result.count

            if chunks_count == 0:
                print(f"   ⚠️  No chunks found for '{name_of_file}'")
                return 0

            # Delete all points with this name_of_file
            self.qdrant.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="name_of_file",
                            match=MatchValue(value=name_of_file)
                        )
                    ]
                )
            )

            print(f"   ✅ Deleted {chunks_count} chunks")
            return chunks_count

        except Exception as e:
            print(f"   ❌ Error deleting document: {e}")
            raise

    def list_documents(self) -> List[Dict[str, str]]:
        """
        Get list of all unique documents in knowledge base

        Returns:
            List of documents with metadata
        """
        print(f"\n📚 Listing all documents...")

        try:
            # Scroll through all points to get unique documents
            offset = None
            documents = {}

            while True:
                records, offset = self.qdrant.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )

                if not records:
                    break

                # Extract unique documents
                for record in records:
                    payload = record.payload
                    name = payload['name_of_file']

                    # Keep only the most recent version of each document
                    if name not in documents or payload['timestamp'] > documents[name]['timestamp']:
                        documents[name] = {
                            'name_of_file': name,
                            'description': payload['description'],
                            'timestamp': payload['timestamp'],
                            'uploaded_by': payload['uploaded_by']
                        }

                if offset is None:
                    break

            doc_list = list(documents.values())
            doc_list.sort(key=lambda x: x['timestamp'], reverse=True)

            print(f"   ✅ Found {len(doc_list)} unique documents")
            return doc_list

        except Exception as e:
            print(f"   ❌ Error listing documents: {e}")
            return []

    def search(
            self,
            query: str,
            top_k: int = 5,
            score_threshold: float = 0.5
    ) -> List[Dict]:
        """
        Search knowledge base for relevant chunks

        Args:
            query: User's question or search query
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of relevant chunks with metadata
        """
        print(f"\n🔍 Searching knowledge base...")
        print(f"   Query: {query[:50]}...")

        try:
            # Generate query embedding first
            query_embedding = self._generate_query_embedding(query)

            # Search in Qdrant using query_points()
            # This is the standard method for vector similarity search in Qdrant 1.12+
            search_results = self.qdrant.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False  # We don't need vectors in response, just metadata
            )

            # query_points() returns QueryResponse with .points list
            results = []

            # Access results from .points attribute
            points = search_results.points if hasattr(search_results, 'points') else search_results

            for result in points:
                # Extract payload and score
                payload = result.payload if hasattr(result, 'payload') else result.get('payload', {})
                score = result.score if hasattr(result, 'score') else result.get('score', 0.0)

                results.append({
                    'document_name': payload.get('name_of_file', 'Unknown'),
                    'description': payload.get('description', ''),
                    'chunk_content': payload.get('chunk_content', ''),
                    'chunk_index': payload.get('chunk_index', 0),
                    'similarity': score,
                    'timestamp': payload.get('timestamp', ''),
                    'uploaded_by': payload.get('uploaded_by', '')
                })

            print(f"   ✅ Found {len(results)} relevant chunks")

            if results:
                print(f"   Top result: {results[0]['document_name']} ({results[0]['similarity']:.0%} match)")

            return results

        except Exception as e:
            print(f"   ❌ Error searching: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            print(f"   Full traceback:")
            traceback.print_exc()

            # Try to provide helpful debugging info
            print(f"\n   Debug info:")
            print(f"   - Collection: {self.COLLECTION_NAME}")
            print(f"   - Query embedding type: {type(query_embedding)}")
            print(f"   - Query embedding length: {len(query_embedding) if hasattr(query_embedding, '__len__') else 'N/A'}")
            print(f"   - Top K: {top_k}")
            print(f"   - Score threshold: {score_threshold}")

            return []

    def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query"""
        response = self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=[query]
        )
        return response.data[0].embedding

    def get_collection_info(self) -> Dict:
        """Get collection statistics"""
        try:
            info = self.qdrant.get_collection(self.COLLECTION_NAME)
            return {
                'total_points': info.points_count,
                'status': info.status
            }
        except Exception as e:
            print(f"   ❌ Error getting collection info: {e}")
            return {}