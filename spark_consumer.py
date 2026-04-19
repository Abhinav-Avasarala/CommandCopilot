"""
spark_consumer.py — Spark Structured Streaming worker (replaces consumer.py).

What it does:
  1. Reads error messages from Kafka's 'error_stream' via Spark Structured Streaming
  2. Applies rules.py (regex rules → Phi-2 LLM fallback) as Spark UDFs
  3. Writes fix responses back to Kafka's 'fix_stream'

fixit.py and all Kafka topics are completely unchanged — this is a drop-in
replacement for consumer.py that adds Spark's distributed stream processing.

Run this BEFORE running fixit.py. Keep it running in the background.

Usage:
  python3 spark_consumer.py

Kafka connector JARs:
  On a machine WITH internet: Spark auto-downloads from Maven Central (no setup needed).
  On VCL/HPC (no internet): set SPARK_KAFKA_JARS to a comma-separated list of
  pre-downloaded JAR paths. See INSTRUCTIONS_VCL.md Part 9.
"""

import os
import logging

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json, to_json, struct, udf
from pyspark.sql.types import StringType, StructType, StructField

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  [SPARK]  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
# For multi-node setups: export KAFKA_BROKER=<broker_node_IP>:9092
# If not set, defaults to localhost:9092 (single-machine mode).
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BROKER', 'localhost:9092')
INPUT_TOPIC        = 'error_stream'
OUTPUT_TOPIC       = 'fix_stream'
CHECKPOINT_DIR     = os.environ.get('SPARK_CHECKPOINT', '/tmp/copilot-spark-checkpoint')

# Comma-separated paths to pre-downloaded Kafka connector JARs.
# Required on VCL/HPC (no internet). Leave blank on a machine with internet —
# Spark will download the connector from Maven Central automatically.
# See INSTRUCTIONS_VCL.md Part 9 for exactly which JARs to download.
KAFKA_JARS = os.environ.get('SPARK_KAFKA_JARS', '')

# ── Incoming message schema ────────────────────────────────────────────────────
# Matches the JSON payload fixit.py sends to error_stream:
# {"request_id": "...", "error": "...", "timestamp": 1234567890.0}
INPUT_SCHEMA = StructType([
    StructField("request_id", StringType(), True),
    StructField("error",      StringType(), True),
    StructField("timestamp",  StringType(), True),
])


# ── UDFs ───────────────────────────────────────────────────────────────────────
# Imports are inside the function body so Spark can serialize them to executors.

@udf(returnType=StringType())
def fix_udf(error_text: str) -> str:
    from rules import get_fix
    return get_fix(error_text or "")


@udf(returnType=StringType())
def error_type_udf(error_text: str) -> str:
    from rules import get_error_type
    return get_error_type(error_text or "")


def build_spark_session() -> SparkSession:
    builder = (
        SparkSession.builder
        .appName("TerminalErrorCopilot")
        .master("local[*]")                             # use all available cores
        .config("spark.sql.shuffle.partitions", "2")    # low-latency for small streams
        .config("spark.driver.memory", "2g")
    )

    if KAFKA_JARS:
        # Pre-downloaded JARs — works on VCL/HPC without internet
        builder = builder.config("spark.jars", KAFKA_JARS)
        log.info("Using local Kafka connector JARs.")
    else:
        # Auto-download from Maven Central — requires internet on first run
        pkg = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
        builder = builder.config("spark.jars.packages", pkg)
        log.info("Kafka connector will be downloaded from Maven Central (first run only) ...")

    return builder.getOrCreate()


def main():
    log.info("Starting Spark Structured Streaming worker ...")
    log.info("Kafka broker: %s", BOOTSTRAP_SERVERS)

    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")  # suppress Spark's verbose INFO noise

    # ── Read from Kafka ────────────────────────────────────────────────────────
    # Spark Structured Streaming treats a Kafka topic as an infinite table of rows.
    # Each row has a 'value' column (bytes) plus Kafka metadata (offset, partition, etc).
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", BOOTSTRAP_SERVERS)
        .option("subscribe", INPUT_TOPIC)
        .option("startingOffsets", "latest")   # only process messages that arrive after startup
        .option("failOnDataLoss", "false")      # tolerate topic resets without crashing
        .load()
    )

    # Cast binary value → string, then parse JSON into typed columns
    parsed = (
        raw
        .select(from_json(col("value").cast("string"), INPUT_SCHEMA).alias("msg"))
        .select("msg.*")
    )

    # ── Apply inference via UDFs ───────────────────────────────────────────────
    # Spark calls fix_udf and error_type_udf on each row in the micro-batch.
    # Each UDF imports from rules.py which falls back to llm_fallback.py if needed.
    enriched = (
        parsed
        .withColumn("fix",        fix_udf(col("error")))
        .withColumn("error_type", error_type_udf(col("error")))
    )

    # ── Serialize output to JSON for Kafka ────────────────────────────────────
    # Output matches the response format fixit.py expects on fix_stream:
    # {"request_id": "...", "error_type": "...", "fix": "..."}
    output = enriched.select(
        to_json(struct(
            col("request_id"),
            col("error_type"),
            col("fix"),
        )).alias("value")
    )

    # ── Write back to Kafka via foreachBatch ───────────────────────────────────
    # foreachBatch lets us log each micro-batch before writing to Kafka.
    def process_batch(batch_df: DataFrame, batch_id: int) -> None:
        count = batch_df.count()
        if count > 0:
            log.info("Batch %d: processed %d error(s) → writing to '%s'",
                     batch_id, count, OUTPUT_TOPIC)
        batch_df.write \
            .format("kafka") \
            .option("kafka.bootstrap.servers", BOOTSTRAP_SERVERS) \
            .option("topic", OUTPUT_TOPIC) \
            .save()

    query = (
        output.writeStream
        .foreachBatch(process_batch)
        .option("checkpointLocation", CHECKPOINT_DIR)
        .trigger(processingTime="1 second")   # micro-batch interval
        .start()
    )

    log.info("Streaming query started.")
    log.info("  Reading from : %s", INPUT_TOPIC)
    log.info("  Writing to   : %s", OUTPUT_TOPIC)
    log.info("  Checkpoint   : %s", CHECKPOINT_DIR)
    log.info("─" * 50)

    query.awaitTermination()


if __name__ == '__main__':
    main()
