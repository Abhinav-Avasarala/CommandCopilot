# Terminal Error Copilot — NCSU Henry2 HPC Guide
## (LSF scheduler, login → compute node)

---

## Which guide is right for you?

| Environment | Guide |
|-------------|-------|
| Your laptop (or multiple laptops) | [INSTRUCTIONS.md](INSTRUCTIONS.md) |
| NCSU Henry2 HPC (login → compute node) | **This file** |
| NCSU VCL reservation | [INSTRUCTIONS_VCL.md](INSTRUCTIONS_VCL.md) |

---

## Key Differences from Local / VCL

| | Local | VCL | Henry2 HPC |
|---|---|---|---|
| Internet on compute node | Yes | Limited | No (use `/share` for files) |
| Java | `brew install` | `module load java` | `module load java` |
| Sudo access | Yes | No | No |
| Conda (base env) | Writable | Read-only | Read-only |
| Job scheduler | None | None | **LSF (`bsub`) required** |
| Multiple terminals | Open new tab | SSH to same IP | SSH login → SSH to compute node name |

---

## Part 1: One-Time Setup

### Step 1 — SSH into the login node

```bash
ssh <unity_id>@login.hpc.ncsu.edu
```

> **Do not run Kafka on the login node.** It is a shared gateway — compute-heavy processes
> will be killed. Always get a compute node first (Step 2).

---

### Step 2 — Request an interactive compute node

```bash
bsub -Is -n 4 -W 2:00 -R "rusage[mem=8GB]" bash
```

| Flag | Meaning |
|------|---------|
| `-Is` | Interactive session (gives you a shell on the node) |
| `-n 4` | 4 CPU cores — Kafka + ZooKeeper + consumer all need headroom |
| `-W 2:00` | 2 hour wall-clock limit |
| `-R "rusage[mem=8GB]"` | 8 GB RAM (enough for Kafka + Phi-2 model if using LLM) |

Your prompt changes to show the node name, e.g. `[aavasar@c1234]`.
**Write down that node name — you need it to open more terminals to the same node.**

---

### Step 3 — Load Java

Kafka requires Java. On Henry2 it's a module, not a system install:

```bash
module load java
java -version   # verify
```

> You must run `module load java` in **every new terminal** before starting Kafka.

---

### Step 4 — Clone the project

```bash
cd /share/<your_group>/<unity_id>
git clone <your-repo-url> terminal-copilot
cd terminal-copilot
```

---

### Step 5 — Copy Kafka to Henry2

Henry2 compute nodes have no internet access. Download Kafka on your laptop first,
then `scp` it to Henry2's `/share` directory.

**On your laptop:**
```bash
curl -L -O https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz
ls -lh kafka_2.13-3.7.0.tgz   # verify ~114 MB
scp kafka_2.13-3.7.0.tgz <unity_id>@login.hpc.ncsu.edu:/share/<group>/<unity_id>/
```

---

### Step 6 — Run the Kafka setup script

```bash
cd /share/<your_group>/<unity_id>/terminal-copilot
bash setup.sh
```

This copies Kafka from `/share`, extracts it to `~/`, and configures data directories.

> `setup.sh` expects the Kafka tarball at `/share/dsa440s26/aavasar/kafka_2.13-3.7.0.tgz`.
> Edit the `KAFKA_TGZ_SOURCE` variable in `setup.sh` if your path differs.

---

### Step 7 — Create the shared conda environment

The system-wide `base` conda environment on Henry2 is read-only.
Create a personal environment in `/share` (20 TB quota — do not use `~`, which has 15 GB):

```bash
conda create -p /share/<your_group>/<unity_id>/hpc-env python=3.10 -y
conda activate /share/<your_group>/<unity_id>/hpc-env

# Build tools (needed to compile llama-cpp-python)
conda install -c conda-forge cmake make gxx_linux-64 -y

# Python dependencies
pip install kafka-python
pip install pyspark==3.5.0
CMAKE_ARGS="-DLLAMA_OPENMP=OFF" pip install llama-cpp-python

# Verify
python3 -c "from kafka import KafkaConsumer; print('kafka-python OK')"
python3 -c "from pyspark.sql import SparkSession; print('pyspark OK')"
python3 -c "import llama_cpp; print('llama-cpp-python OK')"
```

> **Spark Kafka connector JARs (Henry2 has no internet):** download the three connector JARs
> on your laptop and `scp` them to `/share/<group>/<uid>/spark-kafka-jars/`.
> See INSTRUCTIONS_VCL.md Part 9 for the exact URLs and `scp` commands — the process is
> identical to downloading the Kafka tarball.

> `-DLLAMA_OPENMP=OFF` avoids linker errors caused by missing `libgomp` (no sudo to install it).

---

### Step 8 — Copy the Phi-2 model (for LLM fallback)

Like Kafka, the model must be transferred from your laptop — no internet on compute nodes.

**On your laptop:**
```bash
# Via Ollama (if installed):
ollama pull phi
BLOB=$(python3 -c "
import json, os
m = json.load(open(os.path.expanduser(
    '~/.ollama/models/manifests/registry.ollama.ai/library/phi/latest')))
d = next(l['digest'] for l in m['layers'] if 'model' in l.get('mediaType',''))
print(os.path.expanduser('~/.ollama/models/blobs/' + d.replace(':', '-')))
")
scp "$BLOB" <unity_id>@login.hpc.ncsu.edu:/share/<group>/<unity_id>/phi-2.Q4_K_M.gguf

# Or via curl:
curl -L -o phi-2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf"
scp phi-2.Q4_K_M.gguf <unity_id>@login.hpc.ncsu.edu:/share/<group>/<unity_id>/phi-2.Q4_K_M.gguf
```

Then update `MODEL_PATH` in `llm_fallback.py` to match your path:
```python
MODEL_PATH = "/share/<your_group>/<unity_id>/phi-2.Q4_K_M.gguf"
```

---

## Part 2: Running the System (Every Session)

You need **3 terminals all connected to the same compute node**.

### How to open multiple terminals to the same compute node

Terminal 1 is already on the compute node (from `bsub -Is`).
For Terminals 2 and 3, SSH into the login node first, then hop to the same node:

```bash
# Terminal 2 and 3 — from your laptop:
ssh <unity_id>@login.hpc.ncsu.edu
ssh c1234    # ← the compute node name from Terminal 1's prompt
module load java
```

---

### Terminal 1 — Start Kafka

```bash
cd /share/<your_group>/<unity_id>/terminal-copilot
module load java
bash start_kafka.sh
```

Expected output:
```
Kafka is running on localhost:9092
```

**Leave this terminal open.**

---

### Terminal 2 — Create Topics + Start Consumer

**First time only:**
```bash
module load java
cd /share/<your_group>/<unity_id>/terminal-copilot
bash create_topics.sh
```

Then start the Spark worker:
```bash
conda activate /share/<your_group>/<unity_id>/hpc-env

KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/<your_group>/<unity_id>/spark-kafka-jars
export SPARK_KAFKA_JARS="$(echo \
  "$JAR_DIR"/spark-sql-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/spark-token-provider-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/commons-pool2-2.11.1.jar \
  "$KAFKA_HOME"/libs/kafka-clients-*.jar \
  "$KAFKA_HOME"/libs/lz4-java-*.jar \
  "$KAFKA_HOME"/libs/snappy-java-*.jar \
  "$KAFKA_HOME"/libs/zstd-jni-*.jar \
| tr ' ' ',')"

python3 spark_consumer.py
```

Expected output:
```
[SPARK]  Streaming query started.
[SPARK]  Reading from : error_stream
[SPARK]  Writing to   : fix_stream
```

**Leave this terminal open.**

---

### Terminal 3 — Test It

```bash
cd /share/<your_group>/<unity_id>/terminal-copilot
conda activate /share/<your_group>/<unity_id>/hpc-env
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas
```

---

## Part 3: Multi-Node Setup (Each Role on a Separate Compute Node)

Each person submits their own `bsub` job and gets a different compute node.

### Step 1 — Get node names and IPs

Each person runs `bsub -Is -n 4 -W 2:00 -R "rusage[mem=8GB]" bash` and notes their node name.
Get the IP of the broker node:

```bash
# On the broker node:
hostname -I | awk '{print $1}'
```

Share that IP with the group.

---

### Step 2 — Broker node

```bash
module load java
cd /share/<group>/<unity_id>/terminal-copilot
bash start_kafka.sh
# Prints: >>> Share this with your teammates: <IP>:9092 <<<
```

Create topics once from the broker node:
```bash
bash create_topics.sh
```

---

### Step 3 — Worker node (Spark)

```bash
conda activate /share/<group>/<unity_id>/hpc-env
export KAFKA_BROKER=<broker_node_IP>:9092

KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/<group>/<unity_id>/spark-kafka-jars
export SPARK_KAFKA_JARS="$(echo \
  "$JAR_DIR"/spark-sql-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/spark-token-provider-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/commons-pool2-2.11.1.jar \
  "$KAFKA_HOME"/libs/kafka-clients-*.jar \
  "$KAFKA_HOME"/libs/lz4-java-*.jar \
  "$KAFKA_HOME"/libs/snappy-java-*.jar \
  "$KAFKA_HOME"/libs/zstd-jni-*.jar \
| tr ' ' ',')"

python3 spark_consumer.py
```

---

### Step 4 — Producer node

```bash
conda activate /share/<group>/<unity_id>/hpc-env
export KAFKA_BROKER=<broker_node_IP>:9092
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

---

## Troubleshooting

### "No brokers available" from a remote node
1. Is `start_kafka.sh` still running on the broker node?
2. Is `KAFKA_BROKER` set to the broker node's IP (not `localhost`)?
3. Test connectivity: `nc -zv <broker_IP> 9092`

### `module load java` fails
```bash
module avail java    # list available java modules
module load java/17  # load whichever version appears
```

### LSF job expired mid-session
Your `bsub -Is` session has a wall-clock limit. Increase it next time:
```bash
bsub -Is -n 4 -W 4:00 -R "rusage[mem=8GB]" bash   # 4 hours
```

### conda install fails with "EnvironmentNotWritableError"
You're trying to install into the system `base` env. Create your personal env first
(Part 1, Step 7) and activate it before installing anything.

### setup.sh can't find the Kafka tarball
```
ERROR: Could not find /share/dsa440s26/aavasar/kafka_2.13-3.7.0.tgz
```
Edit `KAFKA_TGZ_SOURCE` in `setup.sh` to match your actual path, or scp the tarball
to the path it expects.

---

## Quick Reference

| What | Command | Notes |
|------|---------|-------|
| Get compute node | `bsub -Is -n 4 -W 2:00 -R "rusage[mem=8GB]" bash` | Write down node name |
| Hop to same node | `ssh <node_name>` | From login node |
| Load Java | `module load java` | Every new terminal |
| Kafka setup (once) | `bash setup.sh` | From terminal-copilot/ dir |
| Create conda env (once) | `conda create -p /share/<group>/<uid>/hpc-env python=3.10 -y` | |
| Activate env | `conda activate /share/<group>/<uid>/hpc-env` | Before python commands |
| Start Kafka | `bash start_kafka.sh` | Terminal 1 |
| Create topics (once) | `bash create_topics.sh` | Terminal 2 |
| Start Spark worker | `conda activate ... && export SPARK_KAFKA_JARS=... && python3 spark_consumer.py` | Terminal 2 |
| Run test | `conda activate ... && echo "error" \| python3 fixit.py` | Terminal 3 |
| Stop Kafka | `bash stop_kafka.sh` + Ctrl+C in consumer | Terminal 1 |
