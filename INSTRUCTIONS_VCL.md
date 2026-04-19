# Terminal Error Copilot — VCL Setup & Testing Guide
## (NCSU VCL Reservation: dsa440s26Group2)

> **Multi-node?** Jump to [Part 7: Multi-Node Setup (3 separate VCL machines)](#part-7-multi-node-setup-3-separate-vcl-machines).

---

## VCL vs HPC — What's Different

| | Regular HPC (Henry2) | Your VCL Reservation |
|---|---|---|
| Job scheduling | LSF (`bsub`) required | **Not needed — you own the machine** |
| Compute nodes | Must request one | **Already on one** |
| Multiple terminals | Must SSH to specific node | **Just SSH to the same IP each time** |
| Sudo/admin access | No | **No** (system-wide conda is read-only) |
| Java install | `module load java` | `module load java` (same) |

**Bottom line: VCL is simpler. You skip all the `bsub` stuff.**

---

## What the VCL Screen Tells You

When you see the VCL reservation page:
```
[ Connect! ]    dsa440s26Group2    Tuesday, Oct 20, 2026, 4:00 PM EDT
```

- **Connect!** — click this to get your machine's IP address and connection info
- **dsa440s26Group2** — your reservation name (the VM assigned to your group)
- **Oct 20, 2026 4:00 PM** — your reservation expires at this time. **Save your work before then.**

---

## Part 1: Connect to Your VCL Machine

### Step 1 — Get the IP Address

1. Go to `vcl.ncsu.edu` and log in with your Unity ID
2. Find reservation `dsa440s26Group2`
3. Click **Connect!**
4. You'll see something like:
   ```
   Connect via SSH:
   Host: 152.14.xx.xx
   Username: your_unity_id
   ```
5. Write down that IP address — you'll use it for all 3 terminals

---

### Step 2 — Open 3 Terminal Windows

Unlike HPC, you don't need to do anything special. Just open 3 terminal tabs and SSH to the same IP from each:

```bash
# Terminal 1
ssh <unity_id>@152.14.xx.xx

# Terminal 2 (new tab)
ssh <unity_id>@152.14.xx.xx

# Terminal 3 (new tab)
ssh <unity_id>@152.14.xx.xx
```

All three are now connected to the same machine. That's it.

---

## Part 2: One-Time Setup

Do all of this in **Terminal 1**.

### Step 1 — Install Java

Kafka requires Java. Check if it's already installed first:

```bash
java -version
```

If you see a version number, skip to Step 2.

If you see "command not found":
```bash
sudo apt update
sudo apt install -y default-jdk
java -version    # should now show version info
```

---

### Step 2 — Clone the Project

```bash
cd /share/dsa440s26/aavasar
git clone <your-repo-url> terminal-copilot
cd terminal-copilot
```

---

### Step 3 — Download Kafka Manually (VCL has no internet access)

> **Important:** The VCL machine cannot reach the internet, so `wget` inside `setup.sh` will silently fail. You must download Kafka on your laptop and `scp` it to VCL **before** running `setup.sh`.

**On your laptop:**
```bash
# wget is not available on Mac by default — use curl with the -L flag to follow redirects
curl -L -O https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz

# Verify the file is ~114MB (a few hundred bytes means curl got an error page, not the real file)
ls -lh kafka_2.13-3.7.0.tgz
```

> **Common mistake:** Using `curl -O` without `-L` downloads only ~196 bytes (an HTML redirect page), not the actual Kafka archive. Always use `-L`.

Once you have the real file (~114MB), copy it to VCL:
```bash
scp kafka_2.13-3.7.0.tgz <unity_id>@152.7.179.171:/share/dsa440s26/aavasar/
```

You will be prompted for your Unity password and Duo two-factor authentication.

---

### Step 4 — Run Setup Script (Kafka only)

```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash setup.sh
```

This will:
- Load Java (required by Kafka)
- Copy Kafka 3.7.0 from `/share/dsa440s26/aavasar/` into your home directory
- Configure Kafka to store data in `~/kafka-data/`

**What `setup.sh` does NOT do:** install Python packages. Those go into the shared
conda environment created in Step 5 below.

Expected output when successful:
```
[1/3] Loading Java module...        ← Java loads fine
[2/3] Copying Kafka 3.7.0...        ← Copies from shared dir
[3/3] Configuring Kafka...          ← Sets up data directories
Kafka setup complete!
```

> **If the script stops after `[2/3]` with no output**, `kafka_2.13-3.7.0.tgz` is missing
> from `/share/dsa440s26/aavasar/`. Go back to Step 3 and re-scp it.

> **`setup.sh` must be run from inside `terminal-copilot/`**, not from the parent directory.

---

### Step 5 — Create the Shared Conda Environment

The system-wide `base` conda environment on VCL is read-only (you don't own it).
You need a personal environment stored in `/share` where you have write access.
This environment is created once and shared across all 3 nodes via the GPFS filesystem.

```bash
# Create the env in /share (20 TB scratch — not home, which has a 15 GB quota)
conda create -p /share/dsa440s26/aavasar/my-env python=3.10 -y

# Activate it
conda activate /share/dsa440s26/aavasar/my-env

# Install build tools (needed to compile llama-cpp-python)
conda install -c conda-forge cmake make gxx_linux-64 -y

# Install Python packages
pip install kafka-python
pip install pyspark==3.5.0

# Install llama-cpp-python (CPU-only, OpenMP disabled — compiles in ~3-5 min)
CMAKE_ARGS="-DLLAMA_OPENMP=OFF" pip install llama-cpp-python
```

Verify everything installed:
```bash
python3 -c "from kafka import KafkaConsumer; print('kafka-python OK')"
python3 -c "from pyspark.sql import SparkSession; print('pyspark OK')"
python3 -c "import llama_cpp; print('llama-cpp-python OK')"
```

> **This step only needs to be done once.** Any teammate can activate the same env from
> their own VCL node since `/share/dsa440s26/aavasar/` is a shared GPFS filesystem.

> **If `conda create` is slow**, it's downloading packages. Let it run — it only happens once.

---

## Part 3: Running the System (Every Session)

You need all 3 terminals open and SSH'd into the VCL machine.

### Terminal 1 — Start Kafka

```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash start_kafka.sh
```

Expected output:
```
Starting ZooKeeper...
ZooKeeper PID: 1234
Starting Kafka broker...
Kafka broker PID: 5678
Kafka is running on localhost:9092
```

**Leave this terminal open.**

---

### Terminal 2 — Create Topics + Start Consumer

**First time only** — create the topics:
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash create_topics.sh
```

Expected output:
```
Creating topic: error_stream
Created topic error_stream.
Creating topic: fix_stream
Created topic fix_stream.

Done. Verifying topics exist:
error_stream
fix_stream
```

Now activate the conda environment, set the Spark JAR variable, and start the Spark worker:
```bash
conda activate /share/dsa440s26/aavasar/my-env

# Point Spark to the pre-downloaded Kafka connector JARs (Part 9)
KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/dsa440s26/aavasar/spark-kafka-jars
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

Expected output (Spark prints some WARN lines during startup — these are normal):
```
10:32:00  [SPARK]  Starting Spark Structured Streaming worker ...
10:32:00  [SPARK]  Kafka broker: localhost:9092
24/01/15 10:32:01 WARN NativeCodeLoader: ...    ← normal Spark startup warnings
24/01/15 10:32:03 WARN Utils: ...               ← ignore these
10:32:05  [SPARK]  Streaming query started.
10:32:05  [SPARK]  Reading from : error_stream
10:32:05  [SPARK]  Writing to   : fix_stream
10:32:05  [SPARK]  Checkpoint   : /tmp/copilot-spark-checkpoint
10:32:05  [SPARK]  ──────────────────────────────────────────────────
```

**Leave this terminal open. Spark listens continuously for new micro-batches.**

---

### Terminal 3 — Test It

```bash
cd /share/dsa440s26/aavasar/terminal-copilot
conda activate /share/dsa440s26/aavasar/my-env
```

---

## Part 4: Testing

### Test 1 — Python missing module

```bash
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

Expected:
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas

```

---

### Test 2 — Node.js missing module

```bash
echo "Error: Cannot find module 'express'" | python3 fixit.py
```

Expected:
```
Analyzing error...

  Error Type : UnknownError
  Fix        : npm install express

```

---

### Test 3 — Port in use

```bash
echo "Error: listen EADDRINUSE :::3000" | python3 fixit.py
```

Expected:
```
Analyzing error...

  Error Type : EADDRINUSE
  Fix        : Port 3000 is already in use — run: lsof -ti:3000 | xargs kill

```

---

### Test 4 — A real Python crash

```bash
# Create a broken Python script
echo "import pandas" > broken.py

# Run it and pipe the error to fixit
python3 broken.py 2>&1 | python3 fixit.py
```

---

### Test 5 — Unknown error (fallback)

```bash
echo "The flux capacitor overloaded at line 42" | python3 fixit.py
```

Expected:
```
Analyzing error...

  Error Type : UnknownError
  Fix        : No known fix found. Try searching the exact error message on Stack Overflow or the project's GitHub issues.

```

---

### What Terminal 2 Shows During Each Test

Every time you pipe an error, Spark processes the micro-batch and logs it:

```
10:35:15  [SPARK]  Batch 3: processed 1 error(s) → writing to 'fix_stream'
```

This is the visual proof that the full Kafka → Spark → Kafka pipeline worked.
Spark processes in 1-second micro-batches, so the log line appears ~1 second after you
send the error from Terminal 3.

---

## Part 5: Troubleshooting

### "No brokers available"
Kafka isn't running. In Terminal 1: `bash start_kafka.sh`

### "Is consumer.py still running?"
Spark worker crashed or was never started. In Terminal 2: `python3 spark_consumer.py`
(with `SPARK_KAFKA_JARS` set — see Part 9)

### Topics don't exist
```bash
bash create_topics.sh
```

### Check if Kafka is healthy
```bash
/share/dsa440s26/aavasar/kafka_2.13-3.7.0/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
```
Should return `error_stream` and `fix_stream`.

### kafka-python not found
You're not in the conda environment. Activate it first:
```bash
conda activate /share/dsa440s26/aavasar/my-env
python3 consumer.py   # or fixit.py
```

### setup.sh stops after [2/3] with no error
The Kafka tarball is missing from `/share/dsa440s26/aavasar/`. Download it on your laptop with `curl -L` and `scp` it over. See Part 2, Step 3.

### curl downloaded only ~196 bytes
You used `curl -O` without `-L`. The URL redirects to a mirror and without `-L`, curl saves the redirect HTML instead of the actual file. Always use:
```bash
curl -L -O https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz
```

### "bash: setup.sh: No such file or directory"
You're in the wrong directory. The script lives inside `terminal-copilot/`:
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash setup.sh
```

### VCL reservation expired mid-session
Your work is lost if you didn't save. For future sessions:
- Push code to GitHub before the reservation ends
- Your Kafka data in `/share/dsa440s26/aavasar/kafka-data/` will be gone — just re-run `create_topics.sh` next session

---

## Part 7: Multi-Node Setup (3 separate VCL machines)

This section replaces the single-machine setup when each role (broker, consumer, producer) runs on its own VCL node.

### Architecture

```
Node 1 (Broker)          Node 2 (Consumer)              Node 3 (Producer)
─────────────────         ──────────────────             ─────────────────
start_kafka.sh            conda activate my-env          conda activate my-env
                          export KAFKA_BROKER=...        export KAFKA_BROKER=...
                          python3 consumer.py            echo "error" | python3 fixit.py
```

The conda environment at `/share/dsa440s26/aavasar/my-env` is on a shared GPFS filesystem —
all 3 nodes can activate it without any per-node install.

---

### Step 1 — Get all 3 node IPs

Each person reserves their own VCL machine at `vcl.ncsu.edu`. Get the IP for each:
- **Node 1 IP** (Broker): e.g. `152.14.10.1`
- **Node 2 IP** (Consumer): e.g. `152.14.10.2`
- **Node 3 IP** (Producer): e.g. `152.14.10.3`

The only IP all nodes need to know is **Node 1's IP** (the broker).

---

### Step 2 — Set up all 3 nodes

Run `setup.sh` on **each node** (sets up Kafka/Java — run once per node):
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash setup.sh
```

Python packages do **not** need to be installed per-node. The shared conda env at
`/share/dsa440s26/aavasar/my-env` is accessible from all nodes. If you haven't
created it yet, do it once from any node — see Part 2, Step 5.

---

### Step 3 — Start Kafka on Node 1 (Broker)

SSH into Node 1, then:
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
bash start_kafka.sh
```

The script will:
1. Auto-detect its own IP (`hostname -I`)
2. Configure Kafka to advertise that IP (not `localhost`) so remote nodes can reach it
3. Open port 9092 in the firewall
4. Print the address to share with teammates:
   ```
   >>> Share this with your teammates: 152.14.10.1:9092 <<<
   ```

> **If `hostname -I` returns nothing or a wrong IP**, set it manually:
> ```bash
> export KAFKA_BROKER_IP=152.14.10.1   # Node 1's actual IP
> ```
> Then re-run `start_kafka.sh` (the script uses `KAFKA_BROKER_IP` if set).

---

### Step 4 — Create topics from Node 1

Still on Node 1 (topics only need to be created once, from the broker node):
```bash
bash create_topics.sh
```

---

### Step 5 — Start Spark worker on Node 2

SSH into Node 2, then activate the conda env and set the broker + JAR variables:
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
conda activate /share/dsa440s26/aavasar/my-env
export KAFKA_BROKER=152.14.10.1:9092    # ← Node 1's IP

KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/dsa440s26/aavasar/spark-kafka-jars
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
10:32:05  [SPARK]  Streaming query started.
10:32:05  [SPARK]  Reading from : error_stream
10:32:05  [SPARK]  Writing to   : fix_stream
```

---

### Step 6 — Run fixit on Node 3 (Producer)

SSH into Node 3, then:
```bash
cd /share/dsa440s26/aavasar/terminal-copilot
conda activate /share/dsa440s26/aavasar/my-env
export KAFKA_BROKER=152.14.10.1:9092    # ← Node 1's IP
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas

```

---

### Multi-Node Troubleshooting

#### "No brokers available" on Node 2 or Node 3
The producer/consumer can't reach the broker. Check in order:
1. Is `start_kafka.sh` still running on Node 1?
2. Is `KAFKA_BROKER` set to Node 1's IP (not `localhost`)?
   ```bash
   echo $KAFKA_BROKER    # should print 152.14.10.1:9092
   ```
3. Can you reach Node 1's port 9092?
   ```bash
   nc -zv 152.14.10.1 9092    # should print "succeeded"
   ```
4. Is the firewall open on Node 1?
   ```bash
   # On Node 1:
   sudo ufw allow 9092/tcp
   sudo ufw status
   ```

#### Consumer connects but fixit.py times out
The broker connected but consumer.py isn't running, or it's connected to a different broker address. Verify both Node 2 and Node 3 are using the same `KAFKA_BROKER` value.

#### `nc` says "Connection refused" even with firewall open
VCL sometimes blocks inter-node traffic at the network level. Check that both reservations are in the same VCL group, or contact your instructor.

---

### Multi-Node Quick Reference

| Step | Node | Command |
|------|------|---------|
| Setup (once per node) | all 3 | `bash setup.sh` |
| Start broker | Node 1 | `bash start_kafka.sh` |
| Create topics (once) | Node 1 | `bash create_topics.sh` |
| Start Spark worker | Node 2 | `export KAFKA_BROKER=<Node1_IP>:9092 && export SPARK_KAFKA_JARS=... && python3 spark_consumer.py` |
| Run producer test | Node 3 | `export KAFKA_BROKER=<Node1_IP>:9092 && echo "error..." \| python3 fixit.py` |

---

## Quick Reference Card

| What | Command | Terminal |
|------|---------|---------|
| Connect to VCL | `ssh <unity_id>@<VCL_IP>` | all 3 |
| Download Kafka (on laptop) | `curl -L -O https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz` | laptop |
| Copy Kafka to VCL | `scp kafka_2.13-3.7.0.tgz <unity_id>@<VCL_IP>:/share/dsa440s26/aavasar/` | laptop |
| Kafka setup (once) | `bash setup.sh` | T1 (once) |
| Create conda env (once) | `conda create -p /share/dsa440s26/aavasar/my-env python=3.10 -y` | T1 (once) |
| Activate conda env | `conda activate /share/dsa440s26/aavasar/my-env` | T2, T3 |
| Start Kafka | `bash start_kafka.sh` | T1 |
| Create topics (once) | `bash create_topics.sh` | T2 |
| Start Spark worker | `conda activate my-env && export SPARK_KAFKA_JARS=... && python3 spark_consumer.py` | T2 |
| Quick test | `conda activate my-env && echo "error" \| python3 fixit.py` | T3 |
| Stop everything | `bash stop_kafka.sh` + Ctrl+C in T2 | T1 |

---

## Part 9: Spark Kafka Connector Setup (No-Internet / VCL)

Spark Structured Streaming needs extra JARs to talk to Kafka. On a machine **with internet**,
Spark downloads these automatically the first time you run `spark_consumer.py` — no action needed.

On VCL (no internet), you must download the JARs on your laptop and `scp` them over,
exactly like you did for the Kafka tarball and the Phi-2 model.

---

### Which JARs you need

Spark needs three small connector JARs (~2.5 MB total). The rest (kafka-clients, lz4, snappy,
zstd) are already in your Kafka installation at `~/kafka_2.13-3.7.0/libs/`.

---

### Step 1 — Download the connector JARs on your laptop

```bash
mkdir spark-kafka-jars && cd spark-kafka-jars

curl -O "https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar"
curl -O "https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar"
curl -O "https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar"
```

Verify the files are real (not redirect HTML):
```bash
ls -lh *.jar
# Expected sizes: ~1.8 MB, ~60 KB, ~240 KB respectively
```

---

### Step 2 — Copy JARs to VCL

```bash
scp *.jar <unity_id>@<VCL_IP>:/share/dsa440s26/aavasar/spark-kafka-jars/
```

---

### Step 3 — Set the SPARK_KAFKA_JARS environment variable on VCL

`spark_consumer.py` reads this variable to find the JARs instead of downloading them.
Run this in any terminal where you'll launch the Spark worker (or add it to `~/.bashrc`):

```bash
KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/dsa440s26/aavasar/spark-kafka-jars

export SPARK_KAFKA_JARS="$(echo \
  "$JAR_DIR"/spark-sql-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/spark-token-provider-kafka-0-10_2.12-3.5.0.jar \
  "$JAR_DIR"/commons-pool2-2.11.1.jar \
  "$KAFKA_HOME"/libs/kafka-clients-*.jar \
  "$KAFKA_HOME"/libs/lz4-java-*.jar \
  "$KAFKA_HOME"/libs/snappy-java-*.jar \
  "$KAFKA_HOME"/libs/zstd-jni-*.jar \
| tr ' ' ',')"
```

Verify it looks right (a comma-separated list of full paths):
```bash
echo $SPARK_KAFKA_JARS
```

---

### Troubleshooting Spark connector issues

#### `ClassNotFoundException: org.apache.spark.sql.kafka010`
The connector JAR is missing or not on Spark's classpath. Check `SPARK_KAFKA_JARS` is set
and all paths exist: `ls -lh $(echo $SPARK_KAFKA_JARS | tr ',' '\n')`.

#### `FileNotFoundException` for a Kafka lib (lz4, snappy, zstd)
The glob `"$KAFKA_HOME"/libs/lz4-java-*.jar` matched nothing — the file version differs.
Find the actual name: `ls ~/kafka_2.13-3.7.0/libs/ | grep lz4` and hardcode that path.

#### Spark tries to download from Maven and times out
`SPARK_KAFKA_JARS` is not set. Export it in the same terminal before running
`spark_consumer.py`, or add the `export` to `~/.bashrc` and `source ~/.bashrc`.

---

## Part 6: Stopping & Restarting (Every Session)

### Stopping Everything

**Terminal 2** — stop the consumer:
```bash
Ctrl+C
```

**Terminal 1** — stop Kafka:
```bash
bash stop_kafka.sh
```

Close all SSH sessions after that.

---

### Starting Again for a New Session (No Setup Needed)

Setup only runs once. Every future session is just:

**Terminal 1 — Start Kafka:**
```bash
ssh aavasar@<VCL_IP>
cd /share/dsa440s26/aavasar/terminal-copilot
bash start_kafka.sh
```

**Terminal 2 — Start Spark Worker:**
```bash
ssh aavasar@<VCL_IP>
cd /share/dsa440s26/aavasar/terminal-copilot
conda activate /share/dsa440s26/aavasar/my-env

KAFKA_HOME=~/kafka_2.13-3.7.0
JAR_DIR=/share/dsa440s26/aavasar/spark-kafka-jars
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

**Terminal 3 — Run Tests:**
```bash
ssh aavasar@<VCL_IP>
cd /share/dsa440s26/aavasar/terminal-copilot
conda activate /share/dsa440s26/aavasar/my-env
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

> **If you got a new VCL reservation (new IP or expired VM):** run `bash create_topics.sh` in Terminal 2 once before starting `consumer.py`. The Kafka data directory doesn't persist across reservations.

---

---

## Part 8: LLM Fallback Setup (Phi-2 Model)

When an error doesn't match any regex rule, the system now falls back to a local **Phi-2 2.7B** model running on your CPU. This section explains how to get the model onto VCL (no internet on VCL means you scp it from your laptop, same as Kafka).

---

### What you need

| File | Size | Purpose |
|------|------|---------|
| `phi-2.Q4_K_M.gguf` | ~1.6 GB | The model weights (4-bit quantized) |
| `llama-cpp-python` | ~5 MB compiled | Python bindings to run GGUF models on CPU |

---

### Step 1 — Check your Python version on VCL

You need this to download the right wheel. SSH into your VCL node and run:
```bash
python3 --version
# e.g. Python 3.10.14
```
Write down the major.minor version (e.g. `3.10`).

---

### Step 2 — Pull the model using Ollama (on your Mac)

Ollama stores every pulled model as a GGUF blob on disk — you just locate that file
and `scp` it directly. No separate download needed if you already have Ollama installed.

```bash
# On your Mac — pull Phi-2 (Ollama's model name for Phi-2 is "phi"):
ollama pull phi
```

This downloads ~1.6 GB. Once it finishes, find the blob file Ollama saved:

```bash
# Ollama keeps blobs in ~/.ollama/models/blobs/ named by their sha256 hash.
# This one-liner reads the manifest and prints the exact path:
python3 -c "
import json, os
manifest_path = os.path.expanduser(
    '~/.ollama/models/manifests/registry.ollama.ai/library/phi/latest'
)
m = json.load(open(manifest_path))
digest = next(
    l['digest'] for l in m['layers']
    if 'model' in l.get('mediaType', '')
)
print(os.path.expanduser('~/.ollama/models/blobs/' + digest.replace(':', '-')))
"
```

Example output:
```
/Users/yourname/.ollama/models/blobs/sha256-e8a35b5937a5
```

Save that path — you'll use it in Step 3.

> **If the python3 one-liner errors**, Ollama changed its manifest location. Fall back to
> finding the largest blob manually (it's the model weights):
> ```bash
> ls -lhS ~/.ollama/models/blobs/ | head -3
> ```

---

### Step 3 — Copy the model to VCL

```bash
# On your Mac — substitute the blob path from Step 2:
BLOB_PATH=$(python3 -c "
import json, os
m = json.load(open(os.path.expanduser(
    '~/.ollama/models/manifests/registry.ollama.ai/library/phi/latest')))
digest = next(l['digest'] for l in m['layers'] if 'model' in l.get('mediaType',''))
print(os.path.expanduser('~/.ollama/models/blobs/' + digest.replace(':', '-')))
")

scp "$BLOB_PATH" <unity_id>@<CONSUMER_NODE_IP>:/share/dsa440s26/aavasar/phi-2.Q4_K_M.gguf
```

You'll be prompted for your Unity password and Duo 2FA.

> **Why `/share/` and not `~`?**
> NCSU HPC home directories have a **15 GB / 10K file quota** — a 1.6 GB model would consume
> over 10% of your entire home quota. `/share/dsa440s26` has 20 TB of scratch space and is
> the documented location for large data files. This is also where Kafka already lives.

Verify it arrived on VCL:
```bash
# On VCL (consumer node):
ls -lh /share/dsa440s26/aavasar/phi-2.Q4_K_M.gguf
# Expected: ~1.6G
```

---

### Step 4 — Install llama-cpp-python on VCL

`llama-cpp-python` is installed as part of creating the shared conda environment
in Part 2, Step 5. If you followed that step, it's already done.

If you need to install it manually (e.g. the env exists but llama-cpp-python is missing):

```bash
conda activate /share/dsa440s26/aavasar/my-env

# Ensure build tools are present
conda install -c conda-forge cmake make gxx_linux-64 -y

# Install with OpenMP disabled (avoids linker errors on VCL's CPU-only nodes)
CMAKE_ARGS="-DLLAMA_OPENMP=OFF" pip install llama-cpp-python

# Verify:
python3 -c "import llama_cpp; print('OK')"
```

> **Why `DLLAMA_OPENMP=OFF`?** VCL nodes don't provide libgomp (OpenMP runtime) and
> you don't have sudo to install it. Disabling OpenMP means inference uses 1 thread
> instead of 4 — about 2x slower, but it compiles and runs correctly.

> **Why not `pip install --user`?** The system-wide `base` conda env is read-only.
> `--user` installs into `~/.local` which works, but the packages won't be visible
> when you activate the conda env. Always install inside the activated env.

---

### Step 5 — Test the LLM fallback

Restart `spark_consumer.py` after installing (the model loads on the first unmatched error):
```bash
# Terminal 2 on the worker node — Ctrl+C to stop, then:
python3 spark_consumer.py
```

Now send an error that the regex rules don't cover (Terminal 3):
```bash
export KAFKA_BROKER=<broker_IP>:9092   # skip if single-machine
echo "Some Error" | python3 fixit.py
```

Expected output (fix prefixed with `[LLM]`):
```
Analyzing error...

  Error Type : RuntimeError
  Fix        : [LLM] Reduce batch size or use gradient checkpointing to lower GPU memory usage.

```

The first call also prints this to the consumer terminal:
```
[LLM] First LLM call — loading Phi-2 model from ~/phi-2.Q4_K_M.gguf ...
[LLM] This takes ~10s. Subsequent calls this session are instant.
[LLM] Model ready.
```

---

### How the fallback works

```
error text
    │
    ▼
regex rules  (instant — rules.py RULES list)
    │
    ├── match → return fix immediately
    │
    └── no match → llm_fallback.py
                       │
                       ├── model not installed → "No known fix found..."
                       ├── model file missing  → "No known fix found..."
                       └── model loaded → Phi-2 generates fix → "[LLM] ..."
```

The LLM is **optional** — if `phi-2.Q4_K_M.gguf` is missing or `llama-cpp-python`
isn't installed, the system works exactly as before, returning the default "no fix found" message.

---

### LLM Troubleshooting

#### Worker log shows `[LLM] llama-cpp-python not installed`
Run Step 4 above, then restart `spark_consumer.py`.

#### Worker log shows `[LLM] Model file not found`
Run Step 3 above (scp the `.gguf` file to `/share/dsa440s26/aavasar/phi-2.Q4_K_M.gguf`).

#### First inference takes >30 seconds
Normal on 4 CPU cores with a cold start. Subsequent calls in the same session are ~5s.

#### Fix quality is poor
Phi-2 is a small model — it works well for common error patterns but may produce generic
suggestions for very domain-specific errors. Regex rules always win if they match; add
more rules to `rules.py` for patterns you see frequently.

---

### Pre-Demo Checklist

- [ ] VCL reservation is active and won't expire mid-demo (`vcl.ncsu.edu`)
- [ ] Terminal 1: `start_kafka.sh` running with no errors
- [ ] Spark connector JARs exist on the worker node (`ls /share/dsa440s26/aavasar/spark-kafka-jars/`)
- [ ] `SPARK_KAFKA_JARS` is exported in Terminal 2 (run `echo $SPARK_KAFKA_JARS` to verify)
- [ ] Terminal 2: `spark_consumer.py` showing `Streaming query started`
- [ ] Terminal 3: quick test echo returns a fix
- [ ] If new VM: ran `create_topics.sh` before `spark_consumer.py`
- [ ] (LLM) Model exists on worker node (`ls -lh /share/dsa440s26/aavasar/phi-2.Q4_K_M.gguf`)
- [ ] (LLM) `python3 -c "import llama_cpp; print('OK')"` prints OK on worker node