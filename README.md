# Terminal Error Copilot

A distributed system that diagnoses terminal errors in real time. Pipe any failing command's output into `fixit.py` and receive an actionable fix — powered by a Kafka message pipeline and a two-tier inference engine (regex rules with a local LLM fallback).

Built and tested on NCSU HPC/VCL infrastructure across 3 separate compute nodes.

---

## How It Works

```
Producer node               Broker node          Consumer/Worker node
─────────────────           ───────────          ────────────────────
<command> 2>&1              Kafka                consumer.py
  | python3 fixit.py  ───► error_stream ───────► 1. regex rules
                                                  2. Phi-2 LLM (fallback)
        ▲                   fix_stream   ◄─────── fix response
        └───────────────────────────────
```

`fixit.py` acts as both producer (sends the error) and consumer (waits for the fix). `consumer.py` is the backend worker — it applies regex rules first, and if nothing matches, runs inference on a local **Phi-2 2.7B** (GGUF Q4) model. The broker node runs a standard Kafka + ZooKeeper setup and has no application logic.

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
| Inference (primary) | Regex rule engine |
| Inference (fallback) | Phi-2 2.7B Q4_K_M via llama-cpp-python |
| Runtime | Python 3.10, conda environment on GPFS |
| Infrastructure | NCSU HPC VCL — 3-node distributed setup |

---

## File Overview

| File | Purpose |
|------|---------|
| `fixit.py` | CLI entry point — reads stdin, sends error to Kafka, prints the fix |
| `consumer.py` | Backend worker — consumes errors, runs inference, produces fixes |
| `rules.py` | Regex rule engine covering Python, Node.js, and shell errors |
| `llm_fallback.py` | Phi-2 LLM fallback — lazy-loaded on first miss, cached per session |
| `start_kafka.sh` | Starts ZooKeeper + Kafka broker; auto-configures `advertised.listeners` for multi-node |
| `stop_kafka.sh` | Gracefully shuts down Kafka and ZooKeeper |
| `create_topics.sh` | Creates the `error_stream` and `fix_stream` Kafka topics |
| `setup.sh` | One-time Kafka installation and configuration per node |

---

## Setup Instructions

Full instructions are in the repo — pick the one that matches your environment:

- **[INSTRUCTIONS_VCL.md](INSTRUCTIONS_VCL.md)** — NCSU VCL reservations (single-node and multi-node). Covers conda environment setup, Kafka install, LLM model download, and the 3-node distributed setup.
- **[INSTRUCTIONS.md](INSTRUCTIONS.md)** — NCSU Henry2 HPC cluster with LSF scheduler (`bsub`).

---

## Design Notes

**Why Kafka?** Decoupling the CLI tool from the inference worker means the producer node never needs the model or its dependencies installed. In a multi-user scenario, many `fixit.py` instances can share a single consumer worker.

**Why regex first?** Common errors (missing modules, port conflicts, syntax errors) have deterministic fixes. Regex handles these in milliseconds. The LLM is only invoked when the pattern is novel, keeping latency low for the majority of cases.

**Why Phi-2?** At 2.7B parameters (Q4, ~1.6 GB), it runs on a CPU-only node with 4 cores and 31 GB RAM in roughly 5 seconds per inference — acceptable for a "regex missed" fallback. It was also trained heavily on code and error-style text, which suits this task better than a general-purpose model of the same size.
