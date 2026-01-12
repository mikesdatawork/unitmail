#!/usr/bin/env python3
"""
CLI script to run the unitMail email queue worker as a standalone process.

This script provides a command-line interface for starting the queue worker
with configurable concurrency and graceful shutdown handling.

Usage:
    python queue_worker.py [OPTIONS]

Options:
    --workers N       Number of concurrent workers (default: 4)
    --batch-size N    Number of items to fetch per batch (default: 10)
    --poll-interval S Seconds between queue polls (default: 1.0)
    --config FILE     Path to configuration file
    --debug           Enable debug mode
    --help            Show this message and exit

Examples:
    Start with default settings:
        python queue_worker.py

    Start with 8 workers:
        python queue_worker.py --workers 8

    Start in debug mode:
        python queue_worker.py --debug --workers 2
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

# Add the src directory to the Python path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))


# Global reference for signal handler
_queue_manager: Optional["QueueManager"] = None
_shutdown_requested = False


def setup_logging(debug: bool = False) -> logging.Logger:
    """
    Configure logging for the queue worker.

    Args:
        debug: Enable debug logging.

    Returns:
        Configured logger instance.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Create queue worker logger
    logger = logging.getLogger("unitmail.queue_worker")

    # Reduce noise from third-party libraries in non-debug mode
    if not debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Run the unitMail email queue worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    Start with default settings:
        python queue_worker.py

    Start with 8 workers:
        python queue_worker.py --workers 8

    Start with custom batch size and poll interval:
        python queue_worker.py --workers 4 --batch-size 20 --poll-interval 0.5

    Start in debug mode:
        python queue_worker.py --debug

Environment Variables:
    QUEUE_WORKERS           Number of concurrent workers
    QUEUE_BATCH_SIZE        Items to fetch per batch
    QUEUE_POLL_INTERVAL     Seconds between polls
    UNITMAIL_CONFIG_FILE    Path to configuration file
    SUPABASE_URL            Supabase project URL
    SUPABASE_KEY            Supabase API key
        """,
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of concurrent workers (default: 4 or QUEUE_WORKERS)",
    )

    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=None,
        help="Number of items to fetch per batch (default: 10 or QUEUE_BATCH_SIZE)",
    )

    parser.add_argument(
        "--poll-interval",
        "-p",
        type=float,
        default=None,
        help="Seconds between queue polls (default: 1.0 or QUEUE_POLL_INTERVAL)",
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (TOML format)",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        default=None,
        help="Enable debug mode",
    )

    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Disable event emission",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Maximum retry attempts per message (default: 5)",
    )

    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=None,
        help="Seconds to wait for graceful shutdown (default: 30)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="unitMail Queue Worker 1.0.0",
    )

    return parser.parse_args()


def get_config_value(
    arg_value: Optional[any],
    env_var: str,
    default: any,
    value_type: type = str,
) -> any:
    """
    Get configuration value with precedence: CLI arg > env var > default.

    Args:
        arg_value: Value from command-line argument.
        env_var: Environment variable name.
        default: Default value.
        value_type: Type to convert the value to.

    Returns:
        Configuration value.
    """
    if arg_value is not None:
        return arg_value

    env_value = os.getenv(env_var)
    if env_value is not None:
        try:
            return value_type(env_value)
        except (ValueError, TypeError):
            pass

    return default


def handle_event(event) -> None:
    """
    Handle queue events for logging and monitoring.

    Args:
        event: QueueEvent instance.
    """
    logger = logging.getLogger("unitmail.queue_worker.events")

    event_data = {
        "type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
    }

    if event.queue_item_id:
        event_data["queue_item_id"] = str(event.queue_item_id)
    if event.message_id:
        event_data["message_id"] = str(event.message_id)
    if event.status:
        event_data["status"] = event.status
    if event.error:
        event_data["error"] = event.error
    if event.metadata:
        event_data["metadata"] = event.metadata

    # Log based on event type
    if event.event_type in ("message_sent", "queue_started"):
        logger.info("Queue event: %s", event_data)
    elif event.event_type in ("message_dead_letter", "message_deferred"):
        logger.warning("Queue event: %s", event_data)
    elif "error" in event.event_type:
        logger.error("Queue event: %s", event_data)
    else:
        logger.debug("Queue event: %s", event_data)


async def run_queue_worker(
    num_workers: int,
    batch_size: int,
    poll_interval: float,
    emit_events: bool,
    max_retries: Optional[int],
    shutdown_timeout: Optional[float],
    logger: logging.Logger,
) -> int:
    """
    Run the queue worker main loop.

    Args:
        num_workers: Number of concurrent workers.
        batch_size: Items to fetch per batch.
        poll_interval: Seconds between polls.
        emit_events: Whether to emit events.
        max_retries: Maximum retry attempts.
        shutdown_timeout: Graceful shutdown timeout.
        logger: Logger instance.

    Returns:
        Exit code (0 for success).
    """
    global _queue_manager, _shutdown_requested

    # Import queue modules after path setup
    from gateway.smtp.queue import QueueManager, QueueConfig, create_queue_manager
    from gateway.smtp.worker import QueueWorker

    # Build configuration
    config = QueueConfig(
        num_workers=num_workers,
        batch_size=batch_size,
        poll_interval=poll_interval,
        emit_events=emit_events,
    )

    if max_retries is not None:
        config.max_retries = max_retries

    if shutdown_timeout is not None:
        config.shutdown_timeout = shutdown_timeout

    # Create queue manager
    event_handler = handle_event if emit_events else None
    queue_manager = QueueManager(config=config, event_handler=event_handler)
    queue_manager.set_worker_class(QueueWorker)

    # Store global reference for signal handler
    _queue_manager = queue_manager

    logger.info(
        "Starting queue worker with configuration: workers=%d, batch_size=%d, poll_interval=%.1fs",
        num_workers,
        batch_size,
        poll_interval,
    )

    try:
        # Run the queue manager
        await queue_manager.start()
        return 0

    except asyncio.CancelledError:
        logger.info("Queue worker cancelled")
        return 0

    except Exception as e:
        logger.exception("Queue worker failed: %s", e)
        return 1

    finally:
        if queue_manager.is_running:
            logger.info("Stopping queue manager...")
            await queue_manager.stop()


def signal_handler(signum: int, frame) -> None:
    """
    Handle shutdown signals (SIGTERM, SIGINT).

    Args:
        signum: Signal number.
        frame: Current stack frame.
    """
    global _shutdown_requested

    signal_name = signal.Signals(signum).name
    logger = logging.getLogger("unitmail.queue_worker")

    if _shutdown_requested:
        logger.warning("Forced shutdown requested, exiting immediately")
        sys.exit(1)

    logger.info("Received %s, initiating graceful shutdown...", signal_name)
    _shutdown_requested = True

    # Request queue manager to stop
    if _queue_manager and _queue_manager.is_running:
        # Schedule the stop coroutine
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_queue_manager.stop())


def main() -> int:
    """
    Main entry point for the queue worker.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    args = parse_args()

    # Determine debug mode
    debug = get_config_value(args.debug, "QUEUE_DEBUG", False, bool)

    # Setup logging
    logger = setup_logging(debug)
    logger.info("unitMail Queue Worker starting...")

    # Set config file path if provided
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error("Configuration file not found: %s", args.config)
            return 1
        os.environ["UNITMAIL_CONFIG_FILE"] = str(config_path)
        logger.info("Using configuration file: %s", args.config)

    # Get configuration values
    num_workers = get_config_value(args.workers, "QUEUE_WORKERS", 4, int)
    batch_size = get_config_value(args.batch_size, "QUEUE_BATCH_SIZE", 10, int)
    poll_interval = get_config_value(args.poll_interval, "QUEUE_POLL_INTERVAL", 1.0, float)
    emit_events = not args.no_events

    # Validate configuration
    if num_workers < 1:
        logger.error("Number of workers must be at least 1")
        return 1

    if batch_size < 1:
        logger.error("Batch size must be at least 1")
        return 1

    if poll_interval <= 0:
        logger.error("Poll interval must be positive")
        return 1

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info(
        "Configuration: workers=%d, batch_size=%d, poll_interval=%.1fs, events=%s",
        num_workers,
        batch_size,
        poll_interval,
        "enabled" if emit_events else "disabled",
    )

    try:
        # Run the async main loop
        exit_code = asyncio.run(
            run_queue_worker(
                num_workers=num_workers,
                batch_size=batch_size,
                poll_interval=poll_interval,
                emit_events=emit_events,
                max_retries=args.max_retries,
                shutdown_timeout=args.shutdown_timeout,
                logger=logger,
            )
        )

        logger.info("Queue worker stopped with exit code %d", exit_code)
        return exit_code

    except KeyboardInterrupt:
        logger.info("Queue worker interrupted by user")
        return 0

    except Exception as e:
        logger.exception("Queue worker failed to start: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
