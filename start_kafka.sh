#!/bin/bash
# start_kafka.sh — Start ZooKeeper and the Kafka broker
#
# Run this once at the beginning of your session.
# Keep this terminal open (or run with & to background it).

KAFKA_DIR="$HOME/kafka_2.13-3.7.0"

if [ ! -d "$KAFKA_DIR" ]; then
    echo "[ERROR] Kafka not found at $KAFKA_DIR"
    echo "Run setup.sh first."
    exit 1
fi

echo "Starting ZooKeeper..."
$KAFKA_DIR/bin/zookeeper-server-start.sh $KAFKA_DIR/config/zookeeper.properties &
ZOOKEEPER_PID=$!
echo "ZooKeeper PID: $ZOOKEEPER_PID"

# Give ZooKeeper 5 seconds to fully start before starting Kafka
sleep 5

echo "Starting Kafka broker..."
$KAFKA_DIR/bin/kafka-server-start.sh $KAFKA_DIR/config/server.properties &
KAFKA_PID=$!
echo "Kafka broker PID: $KAFKA_PID"

# Save PIDs so stop_kafka.sh can kill them cleanly
echo $ZOOKEEPER_PID > /tmp/zookeeper.pid
echo $KAFKA_PID     > /tmp/kafka.pid

sleep 5
echo ""
echo "Kafka is running on localhost:9092"
echo "To stop: bash stop_kafka.sh"

# Keep script alive so both background processes stay up
wait
