#!/bin/bash
# create_topics.sh — Create the two Kafka topics needed for this project
#
# Topics are like named channels. Messages are published to a topic
# and consumers subscribe to read from it.
#
# error_stream — fixit.py sends errors here; consumer.py reads from here
# fix_stream   — consumer.py sends fixes here; fixit.py reads from here
#
# Run this ONCE after starting Kafka.

KAFKA_DIR="$HOME/kafka_2.13-3.7.0"
BROKER="localhost:9092"

echo "Creating topic: error_stream"
$KAFKA_DIR/bin/kafka-topics.sh \
    --create \
    --topic error_stream \
    --bootstrap-server $BROKER \
    --partitions 1 \
    --replication-factor 1

echo "Creating topic: fix_stream"
$KAFKA_DIR/bin/kafka-topics.sh \
    --create \
    --topic fix_stream \
    --bootstrap-server $BROKER \
    --partitions 1 \
    --replication-factor 1

echo ""
echo "Done. Verifying topics exist:"
$KAFKA_DIR/bin/kafka-topics.sh --list --bootstrap-server $BROKER
