# Terminal Error Copilot — Local Setup Guide
## (Single laptop or multiple laptops as nodes)

---

## Which guide is right for you?

| Environment | Guide |
|-------------|-------|
| Your laptop (or multiple laptops) | **This file** |
| NCSU Henry2 HPC (login → compute node) | [INSTRUCTIONS_HPC.md](INSTRUCTIONS_HPC.md) |
| NCSU VCL reservation | [INSTRUCTIONS_VCL.md](INSTRUCTIONS_VCL.md) |

---

## Prerequisites

Install these before starting:

```bash
# Java (required by Kafka)
java -version    # if this works, you're good
# Mac: brew install openjdk
# Ubuntu/Debian: sudo apt install -y default-jdk

# Python 3.8+
python3 --version

# pip packages
pip3 install kafka-python
pip3 install llama-cpp-python    # for LLM fallback (optional — see Part 4)
```

---

## Part 1: Download and Configure Kafka

```bash
# Download Kafka
curl -L -O https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz
tar -xzf kafka_2.13-3.7.0.tgz
mv kafka_2.13-3.7.0 ~/kafka_2.13-3.7.0
rm kafka_2.13-3.7.0.tgz

# Configure data directories
mkdir -p ~/kafka-data/zookeeper ~/kafka-data/kafka-logs
sed -i "" "s|dataDir=.*|dataDir=$HOME/kafka-data/zookeeper|" \
    ~/kafka_2.13-3.7.0/config/zookeeper.properties
sed -i "" "s|log.dirs=.*|log.dirs=$HOME/kafka-data/kafka-logs|" \
    ~/kafka_2.13-3.7.0/config/server.properties
```

> **Linux:** use `sed -i` (no empty string after `-i`)

---

## Part 2: Running the System (Single Machine)

Open 3 terminal windows.

### Terminal 1 — Start Kafka

```bash
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
bash create_topics.sh
```

Then start the worker:
```bash
python3 consumer.py
```

Expected output:
```
[CONSUMER]  Connected. Listening on topic 'error_stream' ...
```

**Leave this terminal open.**

---

### Terminal 3 — Test It

```bash
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas
```

---

## Part 3: Multi-Machine Setup (Multiple Laptops as Nodes)

Each laptop takes one role. The only thing that changes from the single-machine setup
is that the broker's IP address must be shared with the other machines.

### Machine 1 — Broker

Run `start_kafka.sh` as normal. It will print:
```
>>> Share this with your teammates: 192.168.x.x:9092 <<<
```

Share that IP with everyone.

---

### Machine 2 — Consumer/Worker

```bash
export KAFKA_BROKER=192.168.x.x:9092   # ← Machine 1's IP
python3 consumer.py
```

---

### Machine 3 — Producer

```bash
export KAFKA_BROKER=192.168.x.x:9092   # ← Machine 1's IP
echo "ModuleNotFoundError: No module named 'pandas'" | python3 fixit.py
```

> **Firewall:** Make sure port `9092` is open on Machine 1.
> Mac: System Settings → Firewall → allow incoming on 9092.
> Linux: `sudo ufw allow 9092/tcp`

---

## Part 4: LLM Fallback Setup (Optional)

When no regex rule matches, the system falls back to a local Phi-2 model (~1.6 GB).
This only needs to be set up on the **consumer/worker machine**.

### Step 1 — Download the model

**Via Ollama (if installed):**
```bash
ollama pull phi

# Find and copy the blob to the expected path
BLOB=$(python3 -c "
import json, os
m = json.load(open(os.path.expanduser(
    '~/.ollama/models/manifests/registry.ollama.ai/library/phi/latest')))
d = next(l['digest'] for l in m['layers'] if 'model' in l.get('mediaType',''))
print(os.path.expanduser('~/.ollama/models/blobs/' + d.replace(':', '-')))
")
cp "$BLOB" ~/phi-2.Q4_K_M.gguf
```

**Via curl:**
```bash
curl -L -o ~/phi-2.Q4_K_M.gguf \
  "https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf"
```

### Step 2 — Update the model path

Open `llm_fallback.py` and change `MODEL_PATH` to:
```python
MODEL_PATH = os.path.expanduser("~/phi-2.Q4_K_M.gguf")
```

### Step 3 — Verify

```bash
python3 -c "import llama_cpp; print('OK')"
ls -lh ~/phi-2.Q4_K_M.gguf
```

Then restart `consumer.py`. On the first unmatched error, you'll see:
```
[LLM] Loading Phi-2 model ... (takes ~10s first time)
```

---

## Troubleshooting

### "No brokers available"
Kafka isn't running. Start it in Terminal 1: `bash start_kafka.sh`

### "Timed out. Is consumer.py still running?"
Consumer crashed or isn't started. Restart it in Terminal 2.

### Topics don't exist
```bash
bash create_topics.sh
```

### Port 9092 already in use
```bash
lsof -ti:9092 | xargs kill
```

### Check Kafka health
```bash
~/kafka_2.13-3.7.0/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
# Should return: error_stream, fix_stream
```

---

## Quick Reference

| What | Command |
|------|---------|
| Start Kafka | `bash start_kafka.sh` |
| Create topics (once) | `bash create_topics.sh` |
| Start consumer | `python3 consumer.py` |
| Run test | `echo "error" \| python3 fixit.py` |
| Stop Kafka | `bash stop_kafka.sh` + Ctrl+C in consumer terminal |
| Multi-machine broker | `export KAFKA_BROKER=<IP>:9092` on consumer + producer |
