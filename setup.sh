#!/bin/bash
# setup.sh — One-time setup: download Kafka and install Python dependencies
#
# Run this ONCE when you first log into HPC.
set -e  # stop on any error
echo "========================================"
echo "  Terminal Error Copilot — HPC Setup"
echo "========================================"
# ── Step 1: Load Java (required by Kafka) ─────────────────────────────────────
echo ""
echo "[1/4] Loading Java module..."
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
echo "[2/4] Kafka already extracted at $KAFKA_DIR — skipping."
else
echo ""
echo "[2/4] Copying Kafka $KAFKA_VERSION from shared directory..."
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
echo "[3/4] Configuring Kafka data directories..."
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
# ── Step 4: Install Python package ────────────────────────────────────────────
echo ""
echo "[4/4] Installing Python package: kafka-python..."
# Try conda first (common on HPC), fall back to pip --user
if command -v conda &> /dev/null; then
conda install -y kafka-python 2>/dev/null || pip install --user kafka-python
else
pip install --user kafka-python
fi
echo ""
echo "========================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. bash start_kafka.sh     (in terminal 1 — keep it open)"
echo "    2. bash create_topics.sh   (in terminal 2 — run once)"
echo "    3. python consumer.py      (in terminal 2 — keep it running)"
echo "    4. Test: echo 'ModuleNotFoundError: No module named pandas' | python fixit.py"
echo "========================================"