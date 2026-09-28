"""Local enterprise file knowledge base and V0.6 RAG."""

from .document_loader import Document, load_document
from .document_parser import SUPPORTED_DOCUMENT_TYPES, parse_document
from .knowledge_reader import (
    GET_DOCUMENT_METADATA_TOOL,
    KNOWLEDGE_TOOLS,
    LIST_KNOWLEDGE_DOCUMENTS_TOOL,
    READ_KNOWLEDGE_DOCUMENT_TOOL,
    read_document,
    read_knowledge_document,
    redact_sensitive_text,
)
from .knowledge_registry import (
    REGISTER_KNOWLEDGE_DOCUMENT_TOOL,
    KnowledgeRegistry,
    get_document_metadata,
    list_documents,
    register_document,
    remove_document_from_registry,
)
from .rag import (
    BUILD_KNOWLEDGE_INDEX_TOOL,
    GET_KNOWLEDGE_INDEX_STATUS_TOOL,
    RAG_TOOLS,
    SEARCH_KNOWLEDGE_BASE_TOOL,
    RAGService,
    build_knowledge_index,
    get_knowledge_index_status,
    search_knowledge_base,
)

__all__ = [
    "Document",
    "BUILD_KNOWLEDGE_INDEX_TOOL",
    "GET_DOCUMENT_METADATA_TOOL",
    "GET_KNOWLEDGE_INDEX_STATUS_TOOL",
    "KNOWLEDGE_TOOLS",
    "KnowledgeRegistry",
    "LIST_KNOWLEDGE_DOCUMENTS_TOOL",
    "READ_KNOWLEDGE_DOCUMENT_TOOL",
    "RAGService",
    "RAG_TOOLS",
    "REGISTER_KNOWLEDGE_DOCUMENT_TOOL",
    "SEARCH_KNOWLEDGE_BASE_TOOL",
    "SUPPORTED_DOCUMENT_TYPES",
    "get_document_metadata",
    "get_knowledge_index_status",
    "list_documents",
    "load_document",
    "parse_document",
    "read_document",
    "read_knowledge_document",
    "redact_sensitive_text",
    "register_document",
    "remove_document_from_registry",
    "build_knowledge_index",
    "search_knowledge_base",
]
