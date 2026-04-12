#!/bin/bash
# setup.sh — One-time Kafka setup: extract and configure the broker
#
# Run this ONCE on every node that needs to run start_kafka.sh.
# Python packages (kafka-python, llama-cpp-python) are managed separately
# via the shared conda environment — see INSTRUCTIONS_VCL.md Part 2, Step 5.
set -e  # stop on any error
echo "========================================"
echo "  Terminal Error Copilot — Kafka Setup"
echo "========================================"

# ── Step 1: Load Java (required by Kafka) ─────────────────────────────────────
echo ""
echo "[1/3] Loading Java module..."
module load java 2>/dev/null || module load jdk 2>/dev/null || {
echo "  WARNING: Could not auto-load java module."
echo "  Run: module avail java   and load the correct one manually."
echo "  Then re-run this script."
}
java -version

# ── Step 2: Copy Kafka from shared directory ───────────────────────────────────
KAFKA_VERSION="3.7.0"
KAFKA_SCALA="2.13"
KAFKA_DIR="$HOME/kafka_${KAFKA_SCALA}-${KAFKA_VERSION}"
KAFKA_TGZ="kafka_${KAFKA_SCALA}-${KAFKA_VERSION}.tgz"
KAFKA_TGZ_SOURCE="/share/dsa440s26/aavasar/${KAFKA_TGZ}"

if [ -d "$KAFKA_DIR" ]; then
echo ""
echo "[2/3] Kafka already extracted at $KAFKA_DIR — skipping."
else
echo ""
echo "[2/3] Copying Kafka $KAFKA_VERSION from shared directory..."
cd $HOME
if [ -f "$KAFKA_TGZ_SOURCE" ]; then
    cp "$KAFKA_TGZ_SOURCE" "$KAFKA_TGZ"
    tar -xzf "$KAFKA_TGZ"
    rm "$KAFKA_TGZ"
    echo "  Kafka extracted to $KAFKA_DIR"
else
    echo "  ERROR: Could not find $KAFKA_TGZ_SOURCE"
    echo "  Please scp the Kafka tarball to /share/dsa440s26/aavasar/ and re-run."
    exit 1
fi
fi

# ── Step 3: Configure Kafka to store data in home dir (not /tmp) ───────────────
echo ""
echo "[3/3] Configuring Kafka data directories..."
KAFKA_DATA="$HOME/kafka-data"
mkdir -p "$KAFKA_DATA/zookeeper"
mkdir -p "$KAFKA_DATA/kafka-logs"
# Point ZooKeeper data to home dir
sed -i "s|dataDir=.*|dataDir=$KAFKA_DATA/zookeeper|" \
"$KAFKA_DIR/config/zookeeper.properties"
# Point Kafka logs to home dir
sed -i "s|log.dirs=.*|log.dirs=$KAFKA_DATA/kafka-logs|" \
"$KAFKA_DIR/config/server.properties"
echo "  Data will be stored in $KAFKA_DATA"

echo ""
echo "========================================"
echo "  Kafka setup complete!"
echo ""
echo "  Next: create the shared conda environment (Step 5 in INSTRUCTIONS_VCL.md)"
echo "  That installs kafka-python and llama-cpp-python — do it before running"
echo "  consumer.py or fixit.py."
echo "========================================"
