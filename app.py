from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)

# Max file size (example: 5 MB)
MAX_FILE_SIZE_MB = 5
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024


@app.route('/')
def home():
    return "<h2>Flask App is Running ✅</h2>"


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(error):
    """
    Return a JSON 413 error instead of Flask's default HTML page.

    Handle HTTP 413 - Request Entity Too Large.
    Flask raises this automatically when the incoming body exceeds
    MAX_CONTENT_LENGTH. We return a clean JSON response instead of
    the default HTML error page.
    """
    return jsonify({
        "success": False,
        "message": f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
    }), 413


if __name__== '__main__':
    app.run(debug=True)