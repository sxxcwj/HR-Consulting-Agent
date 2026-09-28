"""Small maintenance CLI for the local V0.6 RAG index."""

from __future__ import annotations

import argparse
import json

from .rag import RAGService


def main() -> None:
    parser = argparse.ArgumentParser(description="HR Consultant 本地 RAG 索引工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="重建全部已登记文档的索引")
    build.add_argument("--chunk-size", type=int, default=500)
    build.add_argument("--overlap", type=int, default=80)
    subparsers.add_parser("status", help="查看索引状态")
    search = subparsers.add_parser("search", help="执行本地语义检索")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    service = RAGService()
    if args.command == "build":
        result = service.build_index(chunk_size=args.chunk_size, overlap=args.overlap)
    elif args.command == "status":
        result = service.get_status()
    else:
        result = service.search(args.query, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
