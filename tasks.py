"""
Celery Tasks
=============
This file does two things:
    1. Creates and configures the Celery application object (celery_app).
    2. Defines the background task (process_file) that runs after a file upload.

Why a separate file?
    Celery needs its own module to start the worker process.
    Running `celery -A tasks worker` tells Celery to look in tasks.py.

Redis as the broker:
    Redis acts as a message queue between Flask and Celery.
    Flask puts a message ("process this file") into Redis.
    The Celery worker picks it up and runs the task.
"""

import time
import os
from celery import Celery

# ─────────────────────────────────────────────────────────────────────────────
#  Celery application
# ─────────────────────────────────────────────────────────────────────────────

# Both the broker and the result backend point to Redis running locally.
# The broker   : where tasks are sent (Redis list / queue)
# The backend  : where results are stored so /status/<id> can read them
REDIS_URL = "redis://localhost:6379/0"

celery_app = Celery(
    "tasks",              # Name of this Celery app — matches the module name
    broker=REDIS_URL,     # Redis receives task messages from Flask
    backend=REDIS_URL,    # Redis stores task results for status polling
)

# Optional: fine-tune serialisation and result expiry
celery_app.conf.update(
    task_serializer="json",       # Tasks are sent as JSON (human-readable)
    result_serializer="json",     # Results are stored as JSON
    accept_content=["json"],      # Only accept JSON-encoded tasks
    result_expires=3600,          # Results expire from Redis after 1 hour
    timezone="UTC",
    enable_utc=True,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Task definition
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True)
def process_file(self, file_path: str, filename: str) -> dict:
    """
    Background task: read and process an uploaded file.

    This task is queued by Flask immediately after saving the file.
    It runs in a separate worker process so Flask can return its
    response without waiting for the processing to finish.

    Args:
        self      : Celery task instance (available because bind=True).
                    Lets us update task state mid-run.
        file_path : Full path to the saved file, e.g. "uploads/report.pdf"
        filename  : Original sanitised filename, e.g. "report.pdf"

    Returns:
        dict: A summary of what was processed (stored in Redis as the result).

    Raises:
        FileNotFoundError: If the file disappears before the task runs.
        Exception: Any unexpected error is caught and re-raised so Celery
                   marks the task as FAILURE.
    """

    print(f"\n[Celery] ── Task started ──────────────────────────")
    print(f"[Celery]   Task ID  : {self.request.id}")
    print(f"[Celery]   Filename : {filename}")
    print(f"[Celery]   Path     : {file_path}")

    # ── Step 1: Update state so /status returns "STARTED" ─────────────────────
    # By default Celery skips the STARTED state.
    # We update it manually so callers can distinguish "waiting" from "running".
    self.update_state(
        state="STARTED",
        meta={"step": "reading file", "filename": filename}
    )

    # ── Step 2: Read the file from disk ───────────────────────────────────────
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)   # Size in bytes

    # Get the file extension (e.g. ".pdf")
    _, file_ext = os.path.splitext(filename)

    print(f"[Celery]   Size     : {file_size} bytes")
    print(f"[Celery]   Type     : {file_ext}")
    print(f"[Celery]   Status   : Processing… (simulated 5-second delay)")

    # ── Step 3: Simulate file processing ──────────────────────────────────────
    # In a real app this is where you would:
    #   - Generate a thumbnail for an image
    #   - Extract text from a PDF
    #   - Parse and validate a CSV
    #   - Run a virus scan
    # We use time.sleep to simulate that work taking time.
    time.sleep(5)

    # ── Step 4: Build the result ───────────────────────────────────────────────
    result = {
        "message"  : f"File '{filename}' processed successfully!",
        "filename" : filename,
        "file_path": file_path,
        "file_size": file_size,
        "file_type": file_ext.lower(),
        "task_id"  : self.request.id,
    }

    print(f"[Celery]   Done ✓")
    print(f"[Celery] ──────────────────────────────────────────────\n")

    # Whatever we return here is stored in Redis and served by /status/<task_id>
    return result
