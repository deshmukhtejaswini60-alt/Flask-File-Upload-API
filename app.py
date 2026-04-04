"""
Flask File Upload API
=====================
A beginner-friendly Flask app that accepts file uploads via a POST request
to the /upload endpoint and saves them to an "uploads" folder.

How to run:
    1. Install dependencies:
           pip install -r requirements.txt
    2. Start the server:
           python app.py
    3. The server will run at http://localhost:5000

How to test (with curl):
    curl -X POST http://localhost:5000/upload -F "file=@/path/to/your/file.txt"

How to test (with Postman):
    - Method: POST
    - URL: http://localhost:5000/upload
    - Body: form-data, key = "file" (type = File), value = choose a file
"""

import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

# Initialize the Flask application
app = Flask(__name__)

# Name of the folder where uploaded files will be saved
UPLOAD_FOLDER = "uploads"

# Tell Flask where to save uploaded files
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def ensure_upload_folder():
    """Create the uploads folder if it does not already exist."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f'Created folder: "{UPLOAD_FOLDER}"')


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    POST /upload
    ------------
    Accepts a file uploaded via multipart/form-data.
    The form field name must be "file".

    Returns a JSON response with:
        - success (bool): whether the upload succeeded
        - message (str): a human-readable status message
        - filename (str): the name the file was saved as (only on success)

    Error cases handled:
        - No file included in the request
        - File field is present but no file was chosen (empty filename)
    """

    # Check that the request contains a "file" field at all
    if "file" not in request.files:
        return (
            jsonify({
                "success": False,
                "message": 'No file field found in the request. '
                           'Make sure you send a multipart/form-data request '
                           'with a field named "file".'
            }),
            400,  # HTTP 400 Bad Request
        )

    file = request.files["file"]

    # Check that a file was actually selected (not an empty file input)
    if file.filename == "":
        return (
            jsonify({
                "success": False,
                "message": "No file was selected. Please choose a file before uploading."
            }),
            400,
        )

    # secure_filename strips dangerous characters from the filename
    # (e.g. path traversal like "../../etc/passwd" becomes "etc_passwd")
    filename = secure_filename(file.filename)

    # Build the full path where the file will be saved
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Save the file to disk
    file.save(save_path)

    # Return a success response with the saved filename
    return (
        jsonify({
            "success": True,
            "message": "File uploaded successfully!",
            "filename": filename
        }),
        200,  # HTTP 200 OK
    )


@app.route("/", methods=["GET"])
def index():
    """
    GET /
    -----
    A simple health-check endpoint so you can verify the server is running.
    Visit http://localhost:5000 in your browser to confirm.
    """
    return jsonify({
        "message": "Flask File Upload API is running!",
        "upload_endpoint": "POST /upload",
        "instructions": "Send a multipart/form-data POST request to /upload with a field named 'file'."
    })


if __name__ == "__main__":
    # Make sure the uploads folder exists before starting
    ensure_upload_folder()

    print("===========================================")
    print("  Flask File Upload API")
    print("  Server running at http://localhost:5000")
    print("  Upload endpoint: POST /upload")
    print("===========================================")

    # debug=True enables auto-reload when you edit the code
    # and shows detailed error messages in the browser.
    # Set debug=False (or remove it) before going to production.
    app.run(debug=True, host="0.0.0.0", port=5000)
