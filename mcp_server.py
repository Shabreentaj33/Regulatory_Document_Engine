import sys
import traceback
from pathlib import Path
from backend.vector_store import VectorStore
from backend.memory import PersistentMemory
from backend.mcpserver import init, mcp_qa

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    # from mcp.server.fastmcp import FastMCP
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        try:
            from mcp.server import FastMCP
        except ImportError:
            from mcp import FastMCP
    

    vs = VectorStore()
    init(vs)
    memory = PersistentMemory()
    mcp = FastMCP("Regulatory Document Search")

    @mcp.tool()
    def search_documents(query: str) -> str:
        """
        Search the regulatory document database and return relevant context chunks.
        Use this when answering questions about uploaded clinical or regulatory documents
        such as drug dosage, contraindications, warnings, ingredients, or any medical info.
        """
        return mcp_qa(query)

    mcp.run()
    @mcp.tool()
    def list_documents() -> str:
        """
        List all uploaded documents available in the system.
        Shows filename, summary, and whether they are indexed.
        """
        try:
            docs = memory.load_all_documents()
            
            if not docs:
                return "No documents found in the system."

            result = []
            for doc in docs:
                filename = doc.get("filename", "unknown")
                summary = doc.get("summary", "No summary available")[:150]

                result.append(f"📄 {filename}\n   Summary: {summary}\n")

            return "\n".join(result)
        except Exception as e:
            return f"Error retrieving documents: {str(e)}"
except Exception as e:
        print(f"STARTUP ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
