# eval_ragas.py
import os
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

# RAGAS Wrappers for LangChain components
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# LangChain components pointing to local instances
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings

# 1. Point LLM to your local LM Studio instance
lm_studio_url = os.getenv("SRE_AGENT_LLM_URL", "http://localhost:1234/v1")
lm_studio_key = os.getenv("SRE_AGENT_LLM_KEY", "lm-studio")

local_llm = ChatOpenAI(
    base_url=lm_studio_url,
    api_key=lm_studio_key,
    model="liquid/lfm2.5-1.2b",  # Or your loaded LM Studio model identifier
    temperature=0.1
)

# 2. Setup local embeddings (matches your vector store model)
local_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 3. Wrap models into RAGAS interfaces
evaluator_llm = LangchainLLMWrapper(local_llm)
evaluator_embeddings = LangchainEmbeddingsWrapper(local_embeddings)

# Ground-truth test dataset for SRE incident benchmarks
eval_dataset_dict = {
    "question": [
        "Redis connection pool exhausted for payment service"
    ],
    "contexts": [
        ["Runbook Redis: Increase maxclients or clear idle connections using maxmemory-policy volatile-lru."]
    ],
    "answer": [
        "The Redis connection pool is exhausted. Execute volatile-lru eviction policy or increase maxclients."
    ],
    "ground_truth": [
        "Increase Redis maxclients or set maxmemory-policy to volatile-lru."
    ]
}

def run_evaluation():
    dataset = Dataset.from_dict(eval_dataset_dict)
    
    results = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision
        ],
        llm=evaluator_llm,             # Overrides OpenAI GPT-4 with LM Studio
        embeddings=evaluator_embeddings # Overrides OpenAI Embeddings
    )
    
    print("\n=== RAGAS EVALUATION METRICS (LOCAL LLM) ===")
    print(results)
    return results

if __name__ == "__main__":
    run_evaluation()