"""
fixit.py — The CLI tool the user runs on HPC.

What it does:
  1. Reads the piped error text from stdin
  2. Connects to Kafka as a CONSUMER on 'fix_stream' (subscribes FIRST)
  3. Connects to Kafka as a PRODUCER and sends the error to 'error_stream'
  4. Waits for a response on 'fix_stream' that matches this request's ID
  5. Prints the fix to the terminal

Usage:
  <any command that fails> 2>&1 | python fixit.py

Examples:
  python train.py 2>&1 | python fixit.py
  npm run dev 2>&1 | python fixit.py
  echo "ModuleNotFoundError: No module named 'pandas'" | python fixit.py
"""

import sys
import json
import os
import uuid
import time

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable

# ── Kafka config ───────────────────────────────────────────────────────────────
# For multi-node setups: set the KAFKA_BROKER env var to the broker node's IP.
#   export KAFKA_BROKER=152.14.xx.xx:9092
# If not set, defaults to localhost:9092 (single-machine mode).
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BROKER', 'localhost:9092')
INPUT_TOPIC       = 'error_stream'    # We PRODUCE to this (send the error)
OUTPUT_TOPIC      = 'fix_stream'      # We CONSUME from this (receive the fix)
TIMEOUT_SECONDS   = 30                # How long to wait for a response


def main():
    # ── Step 1: Read the piped error text ─────────────────────────────────────
    error_text = sys.stdin.read().strip()

    if not error_text:
        print("[fixit] No input received.")
        print("[fixit] Usage: <failing command> 2>&1 | python fixit.py")
        sys.exit(1)

    # Unique ID for this request so we can match the correct response.
    # Multiple people could use the system simultaneously — the ID keeps them separate.
    request_id = str(uuid.uuid4())

    try:
        # ── Step 2: Subscribe to fix_stream BEFORE producing ──────────────────
        # Important: we set up the consumer FIRST so we don't miss the response
        # that arrives right after we send the error.
        #
        # group_id is unique per request (uses the request_id) so:
        #   - each fixit.py call gets its own independent consumer position
        #   - two simultaneous users don't interfere with each other
        #
        # auto_offset_reset='latest' means: start reading from "right now"
        #   — we only care about responses that arrive AFTER we subscribe
        consumer = KafkaConsumer(
            OUTPUT_TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=f'fixit-{request_id}',
            auto_offset_reset='latest',
            value_deserializer=lambda raw: json.loads(raw.decode('utf-8')),
            consumer_timeout_ms=TIMEOUT_SECONDS * 1000,  # StopIteration after timeout
        )

        # Force Kafka to assign partitions to this consumer RIGHT NOW.
        # Without this poll(), the assignment is lazy and we might miss the response.
        consumer.poll(timeout_ms=500)

        # ── Step 3: Produce the error to error_stream ─────────────────────────
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda data: json.dumps(data).encode('utf-8'),
        )

        payload = {
            'request_id': request_id,
            'error':      error_text,
            'timestamp':  time.time(),
        }

        # Send the error message to Kafka
        # .send() is asynchronous — .flush() blocks until Kafka confirms receipt
        producer.send(INPUT_TOPIC, value=payload)
        producer.flush()
        producer.close()

        print("Analyzing error...", flush=True)

        # ── Step 4: Poll fix_stream for our matching response ─────────────────
        # The for-loop reads messages one by one until consumer_timeout_ms is reached.
        # We check each message's request_id — only print OUR response, ignore others.
        for message in consumer:
            response = message.value
            if response.get('request_id') == request_id:
                print()
                print(f"  Error Type : {response.get('error_type', 'Unknown')}")
                print(f"  Fix        : {response['fix']}")
                print()
                consumer.close()
                return

        # If we get here, the for-loop timed out without finding our response
        print("[fixit] Timed out. Is consumer.py still running?")
        consumer.close()

    except NoBrokersAvailable:
        print("[fixit] Cannot connect to Kafka broker.")
        print("[fixit] Make sure Kafka is running: bash start_kafka.sh")
        sys.exit(1)


if __name__ == '__main__':
    main()
