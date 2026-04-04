"""
Flask File Upload API — with Validation
========================================
A beginner-friendly Flask app that validates and saves uploaded files.

Validation rules:
  - Allowed MIME types: image/jpeg, image/png, application/pdf
  - Maximum file size: 2 MB

How to run:
    1. Install dependencies:
           pip install -r requirements.txt
    2. Start the server:
           python app.py
    3. The server runs at: http://localhost:5000

How to test (Postman):
    POST http://localhost:5000/upload
    Body → form-data → key: "file" (type: File) → pick a .jpg / .png / .pdf

How to test (curl):
    curl -X POST http://localhost:5000/upload -F "file=@photo.jpg"
"""

import os
import magic                          # python-magic: reads actual file bytes to detect type
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

# ─────────────────────────────────────────────
#  Configuration constants
# ─────────────────────────────────────────────

UPLOAD_FOLDER = "uploads"            # Folder where valid files will be saved

MAX_FILE_SIZE_MB = 2                 # Maximum allowed file size in megabytes
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB → bytes (2,097,152)

# Only these MIME types are accepted.
# MIME type describes WHAT a file actually is (e.g. "image/jpeg"), not just its extension.
ALLOWED_MIME_TYPES = {
    "image/jpeg",        # .jpg / .jpeg images
    "image/png",         # .png images
    "application/pdf",   # .pdf documents
}

# ─────────────────────────────────────────────
#  App setup
# ─────────────────────────────────────────────

app = Flask(__name__)

# Tell Flask the maximum request body size.
# Requests larger than this are automatically rejected with HTTP 413
# before they even reach our route handler.
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_BYTES

# ─────────────────────────────────────────────
#  Helper functions
# ─────────────────────────────────────────────

def ensure_upload_folder():
    """Create the uploads folder if it does not already exist."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f'Created folder: "{UPLOAD_FOLDER}"')


def error_response(message, status_code=400):
    """
    Build a standard JSON error response.

    Args:
        message (str): A human-readable description of the problem.
        status_code (int): HTTP status code to return (default: 400 Bad Request).

    Returns:
        A Flask JSON response tuple (response, status_code).
    """
    return jsonify({"success": False, "message": message}), status_code


def success_response(filename):
    """
    Build a standard JSON success response.

    Args:
        filename (str): The name of the file that was saved.

    Returns:
        A Flask JSON response tuple (response, 200).
    """
    return jsonify({
        "success": True,
        "message": "File uploaded successfully!",
        "filename": filename,
    }), 200


def get_mime_type(file_stream):
    """
    Detect the true MIME type of a file by reading its first few bytes.

    Why not trust the filename extension?
    Someone could rename a virus.exe to photo.jpg and fool an extension check.
    Reading the actual bytes ("magic bytes") is much more reliable.

    Args:
        file_stream: The file object from request.files.

    Returns:
        str: The detected MIME type, e.g. "image/jpeg".
    """
    # Read only the first 2048 bytes — enough to identify the file type
    header = file_stream.read(2048)

    # Rewind the file so it can be read again later when saving
    file_stream.seek(0)

    # python-magic inspects the raw bytes and returns the MIME type string
    mime = magic.from_buffer(header, mime=True)
    return mime


def is_valid_mime_type(mime_type):
    """
    Check whether the detected MIME type is in our allowed list.

    Args:
        mime_type (str): The MIME type to check.

    Returns:
        bool: True if allowed, False otherwise.
    """
    return mime_type in ALLOWED_MIME_TYPES


def is_within_size_limit(file_stream):
    """
    Check whether the file is within the allowed size limit.

    We measure the actual file size by seeking to the end and checking
    the position, which is more accurate than relying on Content-Length headers.

    Args:
        file_stream: The file object from request.files.

    Returns:
        bool: True if the file is within the size limit, False if it is too large.
    """
    # Move to the end of the file to find its total size
    file_stream.seek(0, os.SEEK_END)
    file_size = file_stream.tell()   # Current position = file size in bytes

    # Rewind so the file can be read again when saving
    file_stream.seek(0)

    return file_size <= MAX_FILE_SIZE_BYTES


# ─────────────────────────────────────────────
#  Error handlers
# ─────────────────────────────────────────────

@app.errorhandler(413)
def request_too_large(error):
    """
    Handle HTTP 413 — Request Entity Too Large.

    Flask raises this automatically when the incoming request exceeds
    MAX_CONTENT_LENGTH. We return our own friendly JSON message instead
    of a generic HTML error page.
    """
    return error_response(
        f"File is too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        status_code=413,
    )


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """
    GET /
    -----
    Health-check endpoint. Visit http://localhost:5000 in your browser
    to confirm the server is running.
    """
    return jsonify({
        "message": "Flask File Upload API is running!",
        "upload_endpoint": "POST /upload",
        "allowed_types": sorted(ALLOWED_MIME_TYPES),
        "max_file_size": f"{MAX_FILE_SIZE_MB} MB",
    })


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    POST /upload
    ------------
    Accepts a single file upload via multipart/form-data.
    The form field key must be named "file".

    Validation steps (in order):
        1. Check that the "file" field exists in the request.
        2. Check that a file was actually chosen (non-empty filename).
        3. Check that the file size is within the 2 MB limit.
        4. Check that the file's MIME type is in the allowed list.

    On success:
        - Saves the file to the "uploads/" folder.
        - Returns HTTP 200 with { success, message, filename }.

    On failure:
        - Returns HTTP 400 (or 413 for size) with { success, message }.
    """

    # ── Step 1: Make sure the "file" field is present in the request ──────────
    if "file" not in request.files:
        return error_response(
            'No "file" field found in the request. '
            "Send a multipart/form-data POST with a field named \"file\"."
        )

    file = request.files["file"]

    # ── Step 2: Make sure the user actually selected a file ───────────────────
    if file.filename == "":
        return error_response("No file was selected. Please choose a file before uploading.")

    # ── Step 3: Check file size ───────────────────────────────────────────────
    # Note: Flask's MAX_CONTENT_LENGTH already blocks huge requests, but we
    # also check manually here for a consistent JSON error message.
    if not is_within_size_limit(file.stream):
        return error_response(
            f"File is too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
            status_code=413,
        )

    # ── Step 4: Validate MIME type by inspecting the file's actual bytes ──────
    detected_mime = get_mime_type(file.stream)

    if not is_valid_mime_type(detected_mime):
        allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
        return error_response(
            f'Invalid file type: "{detected_mime}". '
            f"Allowed types are: {allowed}."
        )

    # ── Save the file ─────────────────────────────────────────────────────────
    # secure_filename removes dangerous characters (e.g. "../" path traversal)
    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    return success_response(filename)


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    ensure_upload_folder()

    print("==============================================")
    print("  Flask File Upload API  (with validation)")
    print("  Server: http://localhost:5000")
    print("  Endpoint: POST /upload")
    print(f"  Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}")
    print(f"  Max size: {MAX_FILE_SIZE_MB} MB")
    print("==============================================")

    # debug=True: auto-reloads when you save the file, shows detailed errors.
    # Change to debug=False before deploying to production.
    app.run(debug=True, host="0.0.0.0", port=5000)
