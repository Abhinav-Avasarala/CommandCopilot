# Terminal Error Copilot

A distributed system that diagnoses terminal errors in real time. Pipe any failing command's output into `fixit.py` and receive an actionable fix — powered by a Kafka message pipeline, Apache Spark Structured Streaming, and a two-tier inference engine (regex rules with a local LLM fallback).

Built and tested on NCSU HPC/VCL infrastructure across 3 separate compute nodes.

---

## How It Works

```
Producer node               Broker node          Worker node (Spark)
─────────────────           ───────────          ───────────────────────────────
<command> 2>&1              Kafka                spark_consumer.py
  | python3 fixit.py  ───► error_stream ───────► Spark Structured Streaming
                                                    │
                                                    ├── UDF: rules.py (regex)
                                                    └── UDF: llm_fallback.py (Phi-2)
        ▲                   fix_stream   ◄───────  fix response
        └───────────────────────────────
```

`fixit.py` acts as both producer (sends the error) and consumer (waits for the fix). `spark_consumer.py` is the backend worker — it reads from Kafka via Spark Structured Streaming, applies regex rules first, and if nothing matches, runs inference on a local **Phi-2 2.7B** (GGUF Q4) model. The broker node runs a standard Kafka + ZooKeeper setup and has no application logic.

**Kafka stays in the architecture.** Spark replaces the old `consumer.py` polling loop — it reads from `error_stream`, processes each error through the inference UDFs, and writes back to `fix_stream`. `fixit.py` is completely unchanged.

---

## Usage

```bash
# Pipe any error directly
<failing command> 2>&1 | python3 fixit.py

# Examples
python3 train.py 2>&1 | python3 fixit.py
npm run dev 2>&1 | python3 fixit.py
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

**Example output:**
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas
```

For an error not covered by the regex rules, the LLM takes over:
```
  Fix        : [LLM] Reduce batch size or use gradient checkpointing to lower GPU memory usage.
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Message broker | Apache Kafka 3.7.0 + ZooKeeper |
| Kafka client | kafka-python 2.0.2 |
| Stream processor | Apache Spark Structured Streaming (PySpark 3.5.0) |
| Inference (primary) | Regex rule engine |
| Inference (fallback) | Phi-2 2.7B Q4_K_M via llama-cpp-python |
| Runtime | Python 3.10, conda environment on GPFS |
| Infrastructure | NCSU HPC VCL — 3-node distributed setup |

---

## File Overview

| File | Purpose |
|------|---------|
| `fixit.py` | CLI entry point — reads stdin, sends error to Kafka, prints the fix |
| `spark_consumer.py` | Spark Structured Streaming worker — consumes errors, runs inference, produces fixes |
| `rules.py` | Regex rule engine covering Python, Node.js, and shell errors |
| `llm_fallback.py` | Phi-2 LLM fallback — lazy-loaded on first miss, cached per session |
| `consumer_legacy.py` | Original kafka-python worker (kept for reference; superseded by `spark_consumer.py`) |
| `start_kafka.sh` | Starts ZooKeeper + Kafka broker; auto-configures `advertised.listeners` for multi-node |
| `stop_kafka.sh` | Gracefully shuts down Kafka and ZooKeeper |
| `create_topics.sh` | Creates the `error_stream` and `fix_stream` Kafka topics |
| `setup.sh` | One-time Kafka installation and configuration per node |

---

## Setup Instructions

Pick the guide that matches your environment:

| Environment | Guide |
|-------------|-------|
| Local laptop or multiple laptops as nodes | [INSTRUCTIONS.md](INSTRUCTIONS.md) |
| NCSU Henry2 HPC (login → compute node, LSF) | [INSTRUCTIONS_HPC.md](INSTRUCTIONS_HPC.md) |
| NCSU VCL reservation (single or multi-node) | [INSTRUCTIONS_VCL.md](INSTRUCTIONS_VCL.md) |

All three guides cover single-node and multi-node configurations, the conda environment setup, the Spark/Kafka connector JAR setup, and the LLM model transfer.

---

## Design Notes

**Why Kafka?** Decoupling the CLI tool from the inference worker means the producer node never needs the model or its dependencies installed. In a multi-user scenario, many `fixit.py` instances can share a single Spark worker.

**Why Spark Structured Streaming?** Spark treats the Kafka `error_stream` topic as an infinite streaming table. Each micro-batch is processed as a standard DataFrame transformation — the same regex and LLM logic runs as Spark UDFs, giving the system a proper distributed stream processing layer on top of the Kafka pipeline.

**Spark Kafka connector JARs:** Spark needs three small connector JARs (~620 KB total) to talk to Kafka. On a machine with open internet access, Spark downloads these automatically via Maven Central on first run. On VCL/HPC where Maven Central is blocked, download them once with `curl` directly on the node (or `scp` from your laptop) and point Spark to them via the `SPARK_KAFKA_JARS` env var. Since all VCL nodes share the same GPFS filesystem (`/share/dsa440s26/aavasar/`), the JARs only need to be downloaded **once** — every node can read them from the same path. See INSTRUCTIONS_VCL.md Part 9 for exact commands.

**Why regex first?** Common errors (missing modules, port conflicts, syntax errors) have deterministic fixes. Regex handles these in milliseconds. The LLM is only invoked when the pattern is novel, keeping latency low for the majority of cases.

**Why Phi-2?** At 2.7B parameters (Q4, ~1.6 GB), it runs on a CPU-only node with 4 cores and 31 GB RAM in roughly 5 seconds per inference — acceptable for a "regex missed" fallback. It was also trained heavily on code and error-style text, which suits this task better than a general-purpose model of the same size.
