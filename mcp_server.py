from __future__ import annotations

from .config import get_settings
from .db import list_documents, search_documents
from .intelligence import answer_question, expand_query


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install DocPilot with the 'mcp' extra first: pip install -e '.[mcp]'") from exc

    settings = get_settings()
    mcp = FastMCP("DocPilot")

    @mcp.tool()
    def search_documents_local(query: str, limit: int = 20) -> list[dict]:
        """Search the local DocPilot index. No document is uploaded anywhere."""
        return search_documents(settings, expand_query(query), limit=limit)

    @mcp.tool()
    def ask_documents(question: str) -> dict:
        """Answer a factual question from locally indexed DocPilot documents."""
        return answer_question(question, list_documents(settings, limit=1000))

    mcp.run()


if __name__ == "__main__":
    main()
