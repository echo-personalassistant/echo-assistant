import os
from pathlib import Path
import ollama
from config import EMBEDDING_MODEL

class ConversationMemory:
    def __init__(self):
        self.db_path = Path(__file__).parent.parent / "memory" / "chroma_db"
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self.client = None
        self.collection = None
        self.enabled = False

        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            self.collection = self.client.get_or_create_collection(name="conversations")
            self.enabled = True
        except Exception as e:
            # Fallback gracefully if chromadb is not installed or errors
            print(f"Memory system failed to initialize: {e}")

    def _get_embedding(self, text: str) -> list[float]:
        try:
            response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
            return response["embedding"]
        except Exception:
            return []

    def store(self, user_msg: str, assistant_reply: str, message_id: str) -> None:
        if not self.enabled or not self.collection:
            return
        
        # Prepare context text to store
        text_content = f"User: {user_msg}\nAssistant: {assistant_reply}"
        embedding = self._get_embedding(text_content)
        if not embedding:
            return

        try:
            self.collection.add(
                embeddings=[embedding],
                documents=[text_content],
                ids=[message_id],
                metadatas=[{"timestamp": os.getenv("CURRENT_TIME", "unknown")}]
            )
        except Exception:
            pass

    def retrieve(self, query: str, n_results: int = 3) -> str:
        if not self.enabled or not self.collection:
            return ""
        
        embedding = self._get_embedding(query)
        if not embedding:
            return ""

        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results
            )
            documents = results.get("documents")
            if documents and documents[0]:
                context = "\n---\n".join(documents[0])
                return f"\nRelevant past conversation memories:\n{context}\n"
        except Exception:
            pass
        return ""
