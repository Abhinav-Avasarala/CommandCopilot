# Terminal Error Copilot — VCL Setup & Testing Guide
## (NCSU VCL Reservation: dsa440s26Group2)

---

## VCL vs HPC — What's Different

| | Regular HPC (Henry2) | Your VCL Reservation |
|---|---|---|
| Job scheduling | LSF (`bsub`) required | **Not needed — you own the machine** |
| Compute nodes | Must request one | **Already on one** |
| Multiple terminals | Must SSH to specific node | **Just SSH to the same IP each time** |
| Sudo/admin access | No | **Yes** |
| Java install | `module load java` | `sudo apt install` (if needed) |

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

### Step 3 — Run Setup Script

```bash
bash setup.sh
```

This will:
- Download Kafka 3.7.0 to `/share/dsa440s26/aavasar/`
- Configure it to store data in `/share/dsa440s26/aavasar/kafka-data/`
- Install the `kafka-python` pip package

If the script prompts about Java module and fails, that's fine — you already installed Java via `apt` above. The rest of the script will still run.

> **Note:** If `wget` fails to download Kafka, the VCL machine may not have internet access.
> In that case, download Kafka on your laptop and `scp` it over:
> ```bash
> # Run this on your laptop (not on VCL):
> scp kafka_2.13-3.7.0.tgz <unity_id>@152.14.xx.xx:/share/dsa440s26/aavasar/
> ```
> Then on VCL:
> ```bash
> cd /share/dsa440s26/aavasar
> tar -xzf kafka_2.13-3.7.0.tgz
> ```

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

Now start the consumer worker:
```bash
python3 consumer.py
```

Expected output:
```
10:32:01  [CONSUMER]  Connecting to Kafka broker at localhost:9092 ...
10:32:01  [CONSUMER]  Connected. Listening on topic 'error_stream' ...
10:32:01  [CONSUMER]  Fixes will be sent to topic 'fix_stream'
10:32:01  [CONSUMER]  ──────────────────────────────────────────────────
```

**Leave this terminal open. The consumer waits for errors to arrive.**

---

### Terminal 3 — Test It

```bash
cd /share/dsa440s26/aavasar/terminal-copilot
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

Every time you pipe an error, the consumer logs it:

```
10:35:14  [CONSUMER]  New error received  (id=abc-123-...)
10:35:14  [CONSUMER]    Error preview: ModuleNotFoundError: No module named 'pandas'
10:35:14  [CONSUMER]    Fix determined: pip install pandas
10:35:14  [CONSUMER]    Response sent to 'fix_stream'
10:35:14  [CONSUMER]  ──────────────────────────────────────────────────
```

This is the visual proof that the full Kafka pipeline worked.

---

## Part 5: Troubleshooting

### "No brokers available"
Kafka isn't running. In Terminal 1: `bash start_kafka.sh`

### "Is consumer.py still running?"
Consumer crashed. In Terminal 2: `python3 consumer.py`

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
```bash
pip3 install kafka-python
# or
pip3 install --user kafka-python
```

### VCL reservation expired mid-session
Your work is lost if you didn't save. For future sessions:
- Push code to GitHub before the reservation ends
- Your Kafka data in `/share/dsa440s26/aavasar/kafka-data/` will be gone — just re-run `create_topics.sh` next session

---

## Quick Reference Card

| What | Command | Terminal |
|------|---------|---------|
| Connect to VCL | `ssh <unity_id>@<VCL_IP>` | all 3 |
| Install Java (if needed) | `sudo apt install -y default-jdk` | T1 (once) |
| One-time setup | `bash setup.sh` | T1 (once) |
| Start Kafka | `bash start_kafka.sh` | T1 |
| Create topics (once) | `bash create_topics.sh` | T2 |
| Start consumer | `python3 consumer.py` | T2 |
| Quick test | `echo "error text" \| python3 fixit.py` | T3 |
| Real test | `python3 broken.py 2>&1 \| python3 fixit.py` | T3 |
| Stop everything | `bash stop_kafka.sh` + Ctrl+C in T2 | T1 |
