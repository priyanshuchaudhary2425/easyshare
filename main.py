from flask import Flask, render_template, request, redirect, url_for, send_file, abort
from werkzeug.utils import secure_filename
import os
import random
import string
import datetime
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Inudnfueuvn767659tgdjgeGYFvuhBTvbygbmkin'  # Replace with a strong and random secret key

# Configuration for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'doc',
                      'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 'mp4', 'avi',
                      'mov', 'csv', 'json', 'exe', 'dll', 'msi', 'bat', 'sh', 'py',
                      'html', 'css', 'js', 'java', 'cpp', 'h', 'php', 'asp', 'aspx',
                      'jsp', 'ipynb'}

MAX_FILE_SIZE_MB = 5000
MAX_UPLOADS_PER_DAY = 5000 # Max 5000 uploads per day per user

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching

# Dictionary to store links and corresponding file paths
links_database = {}
uploads_count = {}

def generate_random_link():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_expired_files():
    while True:
        current_time = datetime.datetime.now()
        for link, file_info in list(links_database.items()):
            upload_time = file_info['upload_time']
            expiration_time = upload_time + datetime.timedelta(days=1)

            if current_time > expiration_time:
                # Remove the file if it has expired
                os.remove(file_info['file_path'])
                del links_database[link]
                del uploads_count[link]

        # Sleep for some time before checking again (adjust as needed)
        time.sleep(3600)  # 1 hour

# Start the cleanup thread for expired files when the application starts
cleanup_files_thread = threading.Thread(target=cleanup_expired_files, daemon=True)
cleanup_files_thread.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    file_link = None
    error_message = None

    if request.method == 'POST':
        try:
            # Check if the post request has the file part
            if 'file' not in request.files:
                raise ValueError("No file part in the request")

            file = request.files['file']

            # If the user does not select a file, the browser submits an empty file without a filename
            if file.filename == '':
                raise ValueError("No selected file")

            # Check file size
            file_size_mb = request.content_length / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise ValueError("File size exceeds the maximum limit of 500MB.")

            user_ip = request.remote_addr

            # Check if the user has uploaded today
            last_upload_date = uploads_count.get(user_ip, {}).get('last_upload_date')
            current_date = datetime.date.today()

            if last_upload_date != current_date:
                # Reset the upload count for the new day
                uploads_count[user_ip] = {'count': 0, 'last_upload_date': current_date}

            user_uploads = uploads_count[user_ip]['count']

            # Check the number of uploads from the same user
            if user_uploads >= MAX_UPLOADS_PER_DAY:
                raise ValueError("Maximum upload limit exceeded for the day.")

            if file and allowed_file(file.filename):
                # Save the uploaded file with a secure filename
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Generate a quick link
                file_link = generate_random_link()

                # Store the link, file path, and upload time in a dictionary
                links_database[file_link] = {
                    'file_path': file_path,
                    'upload_time': datetime.datetime.now()
                }

                # Increment user uploads count for the day
                uploads_count[user_ip]['count'] += 1

        except ValueError as ve:
            error_message = str(ve)

    return render_template('index.html', file_link=file_link, error=error_message,
                           uploads_remaining=get_uploads_remaining(),
                           space_remaining=get_space_remaining())

def get_uploads_remaining():
    return MAX_UPLOADS_PER_DAY - sum(upload_info['count'] for upload_info in uploads_count.values())

def get_space_remaining():
    total_space_mb = 5000 # 1 GB
    used_space_mb = sum(os.path.getsize(file_info['file_path']) / (1024 * 1024) for file_info in links_database.values())
    return total_space_mb - used_space_mb

@app.route('/file_info/<link>', methods=['GET'])
def file_info(link):
    file_info = links_database.get(link)

    if file_info:
        file_name = os.path.basename(file_info['file_path'])
        file_path = file_info['file_path']

        # Get file size in bytes
        file_size_bytes = os.path.getsize(file_path)

        # Convert file size to KB
        file_size_kb = "%3.1f KB" % (file_size_bytes / 1024.0)

        return render_template('file_info.html', file_name=file_name, file_size=file_size_kb, link=link)
    else:
        return "Link not found"

@app.route('/download/<link>', methods=['GET'])
def download(link):
    file_info = links_database.get(link)

    if file_info:
        file_path = file_info['file_path']

        # Check if the file has expired (1 day limit)
        upload_time = file_info['upload_time']
        expiration_time = upload_time + datetime.timedelta(days=1)
        current_time = datetime.datetime.now()

        if current_time > expiration_time:
            # Remove the file if it has expired
            os.remove(file_path)
            del links_database[link]
            del uploads_count[link]
            return "Link expired. The file has been removed."

        try:
            return send_file(file_path, as_attachment=True)
        except Exception as e:
            app.logger.error(f"Error while sending file: {e}")
            abort(500)
    else:
        return "Link not found"

if __name__ == '__main__':
    # Ensure the 'uploads' folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    app.run(debug=True)
