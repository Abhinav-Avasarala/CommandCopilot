#!/bin/bash
# stop_kafka.sh — Gracefully shut down Kafka and ZooKeeper

KAFKA_DIR="$HOME/kafka_2.13-3.7.0"

echo "Stopping Kafka..."
$KAFKA_DIR/bin/kafka-server-stop.sh

sleep 2

echo "Stopping ZooKeeper..."
$KAFKA_DIR/bin/zookeeper-server-stop.sh

echo "Done."
