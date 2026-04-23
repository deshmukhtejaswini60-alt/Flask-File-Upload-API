"""
Flask File Upload API with Celery Async Processing
====================================================
Upload a file via POST /upload → file is saved → a Celery background
task is triggered immediately → you get back a task_id you can poll.

Routes:
    GET  /                    → health check / welcome message
    POST /upload              → save file, queue Celery task, return task_id
    GET  /status/<task_id>    → poll the status of a background task

How to run (3 terminal windows):
    1. Start Redis      : redis-server
    2. Start Celery     : celery -A tasks worker --loglevel=info
    3. Start Flask      : python app.py

Then upload a file:
    curl -X POST http://localhost:5000/upload -F "file=@photo.jpg"
    # → returns { "task_id": "abc-123-..." }

Then poll status:
    curl http://localhost:5000/status/abc-123-...
"""

import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Import the Celery task defined in tasks.py
# We import the task function, not the Celery app object
from tasks import process_file

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

UPLOAD_FOLDER      = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "txt", "csv"}
MAX_FILE_SIZE_MB   = 10
MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024   # bytes

# ─────────────────────────────────────────────────────────────────────────────
#  Flask app
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config['CELERY_TASK_ALWAYS_EAGER'] = True
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_upload_folder():
    """Create the uploads/ folder if it does not exist."""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_extension(filename):
    """Return True if the file has an accepted extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# ─────────────────────────────────────────────────────────────────────────────
#  Error handlers
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(error):
    return jsonify({
        "success": False,
        "error": "FILE_TOO_LARGE",
        "message": f"File exceeds the {MAX_FILE_SIZE_MB} MB limit."
    }), 413

# ─────────────────────────────────────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """
    GET /
    -----
    Simple health-check / welcome response.
    """
    return jsonify({
        "message": "Flask + Celery File Processing API",
        "endpoints": {
            "upload": "POST /upload  — upload a file and start background processing",
            "status": "GET  /status/<task_id>  — check processing status"
        }
    })


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    POST /upload
    ------------
    1. Receive and validate the uploaded file.
    2. Save it to the uploads/ folder.
    3. Dispatch a Celery background task to process it.
    4. Return the task_id immediately — the client does not wait for processing.

    Success response:
        {
            "success"  : true,
            "message"  : "File uploaded. Processing started in background.",
            "filename" : "report.pdf",
            "task_id"  : "3f2a1b4c-7b8e-4f1a-9c0d-1e2f3a4b5c6d"
        }

    Then poll GET /status/<task_id> to check progress.
    """

    # ── Validate: file field present ──────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({
            "success": False,
            "error": "NO_FILE_FIELD",
            "message": 'No "file" field found. Send multipart/form-data with key "file".'
        }), 400

    file = request.files["file"]

    # ── Validate: a file was chosen ───────────────────────────────────────────
    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "NO_FILE_SELECTED",
            "message": "No file selected."
        }), 400

    # ── Validate: allowed extension ───────────────────────────────────────────
    if not allowed_extension(file.filename):
        return jsonify({
            "success": False,
            "error": "INVALID_FILE_TYPE",
            "message": f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        }), 400

    # ── Save file to disk ─────────────────────────────────────────────────────
    filename  = secure_filename(file.filename)
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    ensure_upload_folder()
    file.save(save_path)

    # ── Dispatch Celery task ──────────────────────────────────────────────────
    # .delay() sends the task to Redis and returns an AsyncResult immediately.
    # The file path is passed so the worker knows which file to process.
    # The Flask response is returned WITHOUT waiting for the task to finish.
    task = process_file.delay(save_path, filename)

    return jsonify({
        "success": True,
        "message": "File uploaded. Processing started in the background.",
        "filename": filename,
        "file_path": save_path,
        "task_id": task.id      # Store this and use it to poll /status/<task_id>
    }), 202   # 202 Accepted: request received, processing in progress


@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    """
    GET /status/<task_id>
    ----------------------
    Poll the Celery task and return its current state.

    Possible states:
        PENDING  → task is waiting in the queue (or task_id doesn't exist)
        STARTED  → worker has picked up the task and is running it
        SUCCESS  → task completed successfully; result is available
        FAILURE  → task raised an exception during processing
        RETRY    → task failed and is being retried

    Response examples:

        In progress:
        { "task_id": "...", "status": "PENDING", "result": null }

        Done:
        { "task_id": "...", "status": "SUCCESS", "result": { ... } }

        Failed:
        { "task_id": "...", "status": "FAILURE", "error": "..." }
    """
    # Import AsyncResult here to look up any task by its ID
    # This works because tasks.py and app.py share the same Celery + Redis config
    from tasks import celery_app
    task = celery_app.AsyncResult(task_id)

    # Build the response based on the current state
    if task.state == "PENDING":
        response = {
            "task_id": task_id,
            "status": "PENDING",
            "message": "Task is waiting to be picked up by a worker.",
            "result": None
        }

    elif task.state == "STARTED":
        response = {
            "task_id": task_id,
            "status": "STARTED",
            "message": "Task is currently being processed.",
            "result": None
        }

    elif task.state == "SUCCESS":
        response = {
            "task_id": task_id,
            "status": "SUCCESS",
            "message": "Task completed successfully.",
            "result": task.result   # The value returned by the Celery task function
        }

    elif task.state == "FAILURE":
        # task.result holds the exception when the task failed
        response = {
            "task_id": task_id,
            "status": "FAILURE",
            "message": "Task failed.",
            "error": str(task.result)
        }

    else:
        # Covers RETRY, REVOKED, or any custom state
        response = {
            "task_id": task_id,
            "status": task.state,
            "message": "Task is in an intermediate state.",
            "result": None
        }

    return jsonify(response)

# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_upload_folder()

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     Flask + Celery Async File Processing API         ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  Flask  : http://localhost:5000                      ║")
    print("║  Upload : POST /upload                               ║")
    print("║  Status : GET  /status/<task_id>                     ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  Make sure Redis and Celery are running first!        ║")
    print("║    redis-server                                       ║")
    print("║    celery -A tasks worker --loglevel=info             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    app.run(debug=True, host="0.0.0.0", port=5000)
