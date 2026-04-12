#!/bin/bash
# start_kafka.sh — Start ZooKeeper and the Kafka broker
#
# Run this on the BROKER NODE only.
# Keep this terminal open (or run with & to background it).
#
# For multi-node setups: this script auto-detects the node's IP and
# configures Kafka to advertise it so other nodes can connect remotely.

KAFKA_DIR="$HOME/kafka_2.13-3.7.0"

if [ ! -d "$KAFKA_DIR" ]; then
    echo "[ERROR] Kafka not found at $KAFKA_DIR"
    echo "Run setup.sh first."
    exit 1
fi

# ── Detect this node's IP for multi-node access ────────────────────────────────
# hostname -I returns all IPs; take the first non-loopback one.
NODE_IP=$(hostname -I | awk '{print $1}')
if [ -z "$NODE_IP" ]; then
    echo "[ERROR] Could not detect node IP via 'hostname -I'."
    echo "Set it manually: export KAFKA_BROKER_IP=<your_ip>  then re-run."
    exit 1
fi

echo "Broker node IP: $NODE_IP"

# Set advertised.listeners so remote nodes (producer/consumer on other VCL nodes)
# can reach this broker. Without this, Kafka advertises 'localhost' and remote
# connections get immediately redirected to an unreachable address.
sed -i "s|^#*advertised.listeners=.*|advertised.listeners=PLAINTEXT://$NODE_IP:9092|" \
    "$KAFKA_DIR/config/server.properties"

# Also ensure listeners binds to all interfaces (not just loopback)
sed -i "s|^#*listeners=PLAINTEXT://.*|listeners=PLAINTEXT://0.0.0.0:9092|" \
    "$KAFKA_DIR/config/server.properties"

# Open port 9092 in the local firewall (VCL Ubuntu uses ufw; ignore if not active)
sudo ufw allow 9092/tcp 2>/dev/null && echo "Firewall: port 9092 opened." || true

# Write the broker address to a shared file so teammates can read it
echo "$NODE_IP:9092" > /tmp/kafka_broker_addr.txt
echo "Broker address saved to /tmp/kafka_broker_addr.txt"
echo ""
echo "  >>> Share this with your teammates: $NODE_IP:9092 <<<"
echo ""

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
echo "Kafka is running on $NODE_IP:9092"
echo "To stop: bash stop_kafka.sh"

# Keep script alive so both background processes stay up
wait
