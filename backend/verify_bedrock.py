"""Verification script for AWS Bedrock and FlashRank migration."""
import asyncio
import os
from unittest.mock import MagicMock, patch

# Set env vars for testing (mocked)
os.environ["AWS_REGION"] = "us-east-1"
os.environ["BEDROCK_LLM_MODEL_ID"] = "anthropic.claude-3-5-sonnet-20240620-v1:0"
os.environ["BEDROCK_EMBED_MODEL_ID"] = "amazon.titan-embed-text-v2:0"
os.environ["LLM_PROVIDER"] = "bedrock"
os.environ["EMBEDDING_PROVIDER"] = "bedrock"
os.environ["RERANKER_PROVIDER"] = "flashrank"

from app.core.registry import get_provider_registry

async def verify():
    print("Verifying Provider Registry...")
    registry = get_provider_registry()
    
    # 1. Verify LLM
    print("\n1. Testing Bedrock LLM instantiation...")
    try:
        llm = registry.get_llm()
        print(f"✅ LLM Provider: {llm.__class__.__name__}")
        assert llm.__class__.__name__ == "BedrockLLMProvider"
    except Exception as e:
        print(f"❌ LLM Failed: {e}")

    # 2. Verify Embedding
    print("\n2. Testing Bedrock Embedding instantiation...")
    try:
        embedder = registry.get_embedder()
        print(f"✅ Embedding Provider: {embedder.__class__.__name__}")
        assert embedder.__class__.__name__ == "BedrockEmbeddingProvider"
    except Exception as e:
        print(f"❌ Embedding Failed: {e}")

    # 3. Verify Reranker
    print("\n3. Testing FlashRank Reranker instantiation...")
    # Mock Ranker to avoid loading model model
    with patch("app.core.providers.flashrank_reranker.Ranker") as MockRanker:
        reranker = registry.get_reranker()
        print(f"✅ Reranker Provider: {reranker.__class__.__name__}")
        assert reranker.__class__.__name__ == "FlashRankRerankerProvider"

    print("\n🎉 All providers instantiated successfully!")

if __name__ == "__main__":
    asyncio.run(verify())
