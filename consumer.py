"""
consumer.py — The backend worker that runs on HPC.

What it does:
  1. Connects to Kafka as a CONSUMER on the 'error_stream' topic
  2. Waits for error messages to arrive
  3. Runs the error through rules.py to find a fix
  4. Connects to Kafka as a PRODUCER and sends the fix to 'fix_stream'

Run this BEFORE running fixit.py. Keep it running in the background.
Usage: python consumer.py
"""

import json
import logging
import os
import sys
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable
from rules import get_fix, get_error_type

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  [CONSUMER]  %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# ── Kafka config ───────────────────────────────────────────────────────────────
# For multi-node setups: set the KAFKA_BROKER env var to the broker node's IP.
#   export KAFKA_BROKER=152.14.xx.xx:9092
# If not set, defaults to localhost:9092 (single-machine mode).
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BROKER', 'localhost:9092')
INPUT_TOPIC  = 'error_stream'          # Topic we READ from  (errors come in here)
OUTPUT_TOPIC = 'fix_stream'            # Topic we WRITE to   (fixes go out here)


def create_consumer() -> KafkaConsumer:
    """
    KafkaConsumer subscribes to a topic and reads messages from it.

    Key parameters explained:
      bootstrap_servers  — address of the Kafka broker to connect to
      group_id           — consumer group name; Kafka tracks how far each group
                           has read so we never re-process the same message
      auto_offset_reset  — what to do when there is no saved position:
                           'latest'  = only read messages that arrive AFTER we start
                           'earliest'= read everything from the beginning of the topic
      value_deserializer — function to convert raw bytes → Python dict (JSON decode)
    """
    return KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id='copilot-workers',
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda raw: json.loads(raw.decode('utf-8')),
    )


def create_producer() -> KafkaProducer:
    """
    KafkaProducer sends messages to a topic.

    Key parameters explained:
      bootstrap_servers  — same broker address
      value_serializer   — function to convert Python dict → bytes (JSON encode)
                           Kafka only stores raw bytes; serialization is our job
    """
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda data: json.dumps(data).encode('utf-8'),
    )


def main():
    log.info("Connecting to Kafka broker at %s ...", BOOTSTRAP_SERVERS)

    try:
        consumer = create_consumer()
        producer = create_producer()
    except NoBrokersAvailable:
        log.error("Cannot connect to Kafka. Is the broker running? (check: start_kafka.sh)")
        sys.exit(1)

    log.info("Connected. Listening on topic '%s' ...", INPUT_TOPIC)
    log.info("Fixes will be sent to topic '%s'", OUTPUT_TOPIC)
    log.info("─" * 50)

    # This for-loop blocks and waits for messages forever.
    # Each iteration gives us one message from Kafka.
    for kafka_message in consumer:

        # kafka_message.value is already a Python dict (deserialized above)
        payload    = kafka_message.value
        request_id = payload.get('request_id', 'unknown')
        error_text = payload.get('error', '')

        log.info("New error received  (id=%s)", request_id)
        log.info("  Error preview: %s", error_text[:120].replace('\n', ' '))

        # ── Process the error ─────────────────────────────────────────────────
        fix        = get_fix(error_text)
        error_type = get_error_type(error_text)

        log.info("  Fix determined: %s", fix)

        # ── Send fix back to Kafka ────────────────────────────────────────────
        response = {
            'request_id': request_id,    # must match so fixit.py can find ITS response
            'error_type': error_type,
            'fix':        fix,
        }

        # producer.send() is non-blocking; .flush() waits until delivery is confirmed
        producer.send(OUTPUT_TOPIC, value=response)
        producer.flush()

        log.info("  Response sent to '%s'", OUTPUT_TOPIC)
        log.info("─" * 50)


if __name__ == '__main__':
    main()
