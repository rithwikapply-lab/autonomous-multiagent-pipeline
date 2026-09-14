import json
import asyncio
import time
from app.models.schemas import DocumentIngestRequest, QueryRequest
from app.api.ingest import ingest_document, IN_MEMORY_CHUNKS
from app.api.query import query_pipeline

async def run_benchmark_suite():
    print("=" * 70)
    print("⚡ RUNNING AUTONOMOUS MULTI-AGENT EVALUATION BENCHMARK")
    print("=" * 70)

    with open("evals/test_dataset.json", "r") as f:
        dataset = json.load(f)

    # 1. Ingest Documents
    print("\n📂 Step 1: Ingesting Benchmark Documents...")
    for item in dataset:
        req = DocumentIngestRequest(
            doc_id=item["doc_id"],
            title=item["title"],
            text_content=item["content"]
        )
        resp = await ingest_document(req, session=None)
        print(f"  ✓ Ingested '{item['title']}' -> {resp.chunks_created} chunks")

    # 2. Run Evaluation Queries
    print("\n🔍 Step 2: Executing Queries & Measuring Metrics...")
    total_queries = 0
    passed_verifications = 0
    total_latency_ms = 0
    metric_accuracy_hits = 0
    total_metrics_expected = 0

    for item in dataset:
        for q_obj in item["eval_questions"]:
            total_queries += 1
            query = q_obj["query"]
            print(f"\n[Query {total_queries}]: {query}")

            start = time.perf_counter()
            q_req = QueryRequest(query=query, top_k=3, enable_reranking=True, enable_verification=True)
            res = await query_pipeline(q_req, session=None)
            duration = (time.perf_counter() - start) * 1000
            total_latency_ms += duration

            # Verify faith & claims
            is_faithful = res.verification.is_faithful if res.verification else True
            if is_faithful:
                passed_verifications += 1

            # Check expected metrics
            extracted_text = json.dumps(res.analysis.model_dump())
            for exp in q_obj["expected_metrics"]:
                total_metrics_expected += 1
                if exp["expected_value"].lower() in extracted_text.lower():
                    metric_accuracy_hits += 1

            print(f"  • Latency: {duration:.2f}ms")
            print(f"  • Faithfulness: {'PASS' if is_faithful else 'FAIL'}")
            print(f"  • Executive Summary: {res.analysis.executive_summary[:100]}...")
            print(f"  • Extracted Metrics: {len(res.analysis.key_metrics)}")

    avg_latency = total_latency_ms / max(total_queries, 1)
    faithfulness_rate = (passed_verifications / max(total_queries, 1)) * 100
    metric_precision = (metric_accuracy_hits / max(total_metrics_expected, 1)) * 100

    print("\n" + "=" * 70)
    print("📊 BENCHMARK EVALUATION SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Queries Evaluated:    {total_queries}")
    print(f"Average Pipeline Latency:   {avg_latency:.2f} ms")
    print(f"Faithfulness Score:         {faithfulness_rate:.1f}%")
    print(f"Metric Extraction Accuracy: {metric_precision:.1f}%")
    print(f"Hallucination Rate:         {100.0 - faithfulness_rate:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_benchmark_suite())
