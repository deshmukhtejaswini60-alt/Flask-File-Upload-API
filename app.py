from flask import Flask, request, jsonify, render_template_string
import os
import uuid

app = Flask(__name__)

# Upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


#  Home Route (Simple Upload Form)
@app.route("/")
def home():
    return render_template_string("""
    <h2>Upload File</h2>
    <form method="POST" action="/upload" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload</button>
    </form>
    """)


#  Upload API
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Generate unique ID
    file_id = str(uuid.uuid4())

    # Extract file extension
    filename = file.filename
    ext = filename.split(".")[-1]

    # New filename (unique)
    new_filename = f"{file_id}.{ext}"

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)

    # Save file
    file.save(file_path)

    # File size
    file_size = os.path.getsize(file_path)

    # JSON response
    return jsonify({
        "id": file_id,
        "filename": filename,
        "stored_name": new_filename,
        "size_bytes": file_size,
        "type": ext,
        "path": file_path
    })


# Run app
if __name__ == "__main__":
    app.run(debug=True)