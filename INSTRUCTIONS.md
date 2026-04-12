# Terminal Error Copilot — HPC Setup & Testing Guide
## (NCSU Henry2, LSF scheduler)

---

## How the System Works (Read This First)

```
Terminal 1                Terminal 2                Terminal 3 (your work)
──────────────────────────────────────────────────────────────────────────
Kafka broker              consumer.py               fixit.py
(ZooKeeper +              (backend worker)          (CLI tool)
 Kafka server)
      │                         │                         │
      │   ←── listens ──────────┤                         │
      │                         │                         │
      │   ←── error arrives ────────────────── produces ──┤
      │         (error_stream topic)                       │
      │                         │                         │
      │   ── fix produced ─────►│                         │
      │         (fix_stream topic)                         │
      │                                                    │
      │   ── fix received ─────────────────── consumed ──►│
                                                           │
                                               prints fix to screen
```

**Kafka Topics:**
- `error_stream` — fixit.py writes here, consumer.py reads from here
- `fix_stream` — consumer.py writes here, fixit.py reads from here

---

## Part 1: First-Time Setup (do this ONCE)

### Step 1 — SSH into HPC

```bash
ssh <unity_id>@login.hpc.ncsu.edu
```

---

### Step 2 — Get an Interactive Compute Node (LSF)

You need a real compute node (not the login node) to run Kafka.

```bash
bsub -Is -n 4 -W 2:00 -R "rusage[mem=4GB]" bash
```

**What this means:**
- `-Is` — interactive session (gives you a shell on the node)
- `-n 4` — request 4 CPU cores (Kafka + ZooKeeper need breathing room)
- `-W 2:00` — 2 hour time limit
- `-R "rusage[mem=4GB]"` — request 4 GB memory

After this runs, your prompt changes to show the compute node name (e.g., `[you@c0123]`).
**Write down that node name — you'll need it when opening more terminals.**

---

### Step 3 — Clone the project and run setup

```bash
cd ~
git clone <your-repo-url> terminal-copilot
cd terminal-copilot
bash setup.sh
```

`setup.sh` does four things automatically:
1. Loads the Java module (Kafka requires Java)
2. Downloads Kafka 3.7.0 to your home directory
3. Configures Kafka to store data in `~/kafka-data/` (not /tmp)
4. Installs the `kafka-python` pip package

---

## Part 2: Every Time You Want to Run It

You need **3 terminal windows** all connected to the **same compute node**.

### How to open multiple terminals to the same node:

When you `bsub -Is`, you land on a node, e.g., `c0123`.
Open new terminal tabs and SSH directly to that node:

```bash
# In terminal 2 and 3:
ssh <unity_id>@login.hpc.ncsu.edu
ssh c0123       # replace with your actual node name
```

---

### Terminal 1 — Start Kafka

```bash
cd ~/terminal-copilot
module load java    # must do this in every new terminal
bash start_kafka.sh
```

You should see output like:
```
Starting ZooKeeper...
ZooKeeper PID: 12345
Starting Kafka broker...
Kafka broker PID: 12346
Kafka is running on localhost:9092
```

**Leave this terminal open. Do not close it.**

---

### Terminal 2 — Create Topics (first time only) + Start Consumer

```bash
cd ~/terminal-copilot
module load java

# Only needed the very first time:
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

Now start the consumer worker:
```bash
python consumer.py
```

You should see:
```
10:32:01  [CONSUMER]  Connecting to Kafka broker at localhost:9092 ...
10:32:01  [CONSUMER]  Connected. Listening on topic 'error_stream' ...
10:32:01  [CONSUMER]  Fixes will be sent to topic 'fix_stream'
10:32:01  [CONSUMER]  ──────────────────────────────────────────────────
```

**Leave this terminal open. The consumer waits for errors.**

---

### Terminal 3 — Run Your Tests

```bash
cd ~/terminal-copilot
```

---

## Part 3: Testing

### Test 1 — Python missing module

```bash
echo "ModuleNotFoundError: No module named 'pandas'" | python fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : ModuleNotFoundError
  Fix        : pip install pandas

```

---

### Test 2 — Node.js missing module

```bash
echo "Error: Cannot find module 'express'" | python fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : UnknownError
  Fix        : npm install express

```

---

### Test 3 — Port in use

```bash
echo "Error: listen EADDRINUSE :::3000" | python fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : EADDRINUSE
  Fix        : Port 3000 is already in use — run: lsof -ti:3000 | xargs kill

```

---

### Test 4 — A real Python crash

Create a broken script and pipe its error:

```bash
echo "import pandas" > broken.py
python broken.py 2>&1 | python fixit.py
```

---

### Test 5 — An unrecognized error (fallback message)

```bash
echo "Something went horribly wrong with the flux capacitor" | python fixit.py
```

Expected output:
```
Analyzing error...

  Error Type : UnknownError
  Fix        : No known fix found. Try searching the exact error message on Stack Overflow or the project's GitHub issues.

```

---

### What You Should See in Terminal 2 (consumer) During Tests

Every time you pipe an error, the consumer logs the activity:

```
10:35:14  [CONSUMER]  New error received  (id=abc-123-...)
10:35:14  [CONSUMER]    Error preview: ModuleNotFoundError: No module named 'pandas'
10:35:14  [CONSUMER]    Fix determined: pip install pandas
10:35:14  [CONSUMER]    Response sent to 'fix_stream'
10:35:14  [CONSUMER]  ──────────────────────────────────────────────────
```

This confirms the full Kafka flow worked:
- fixit.py → `error_stream` → consumer.py → `fix_stream` → fixit.py

---

## Part 4: Troubleshooting

### "No brokers available" error
Kafka isn't running. Go to Terminal 1 and run `bash start_kafka.sh`.

### "Is consumer.py still running?" message
The consumer crashed or isn't started. Go to Terminal 2 and run `python consumer.py`.

### Topics don't exist error
```bash
bash create_topics.sh
```

### Java not found
```bash
module avail java      # see what java modules are available
module load java/17    # load whichever version shows up
```

### consumer.py can't find rules.py
Make sure you're running from inside the project directory:
```bash
cd ~/terminal-copilot
python consumer.py
```

### Check if Kafka is actually running
```bash
~/kafka_2.13-3.7.0/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
```
If this returns `error_stream` and `fix_stream`, Kafka is healthy.

---

## Part 5: Shutting Down

When done, in Terminal 1:
- Press `Ctrl+C` to stop `start_kafka.sh`
- Then run: `bash stop_kafka.sh`

In Terminal 2:
- Press `Ctrl+C` to stop `consumer.py`

---

## Quick Reference Card

| What | Command | Terminal |
|------|---------|---------|
| Get compute node | `bsub -Is -n 4 -W 2:00 -R "rusage[mem=4GB]" bash` | any |
| Start Kafka | `bash start_kafka.sh` | T1 |
| Create topics (once) | `bash create_topics.sh` | T2 |
| Start consumer | `python consumer.py` | T2 |
| Test | `echo "error text" \| python fixit.py` | T3 |
| Real test | `python broken.py 2>&1 \| python fixit.py` | T3 |
| Stop everything | `bash stop_kafka.sh` + Ctrl+C | T1, T2 |
