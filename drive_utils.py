import os
import zipfile
import streamlit as st

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

DB_DIR = "/content/drive/MyDrive/vectordbst"
ZIP_FILENAME = "faiss_vector_store.zip"
ZIP_PATH = os.path.join("/content/drive/MyDrive", ZIP_FILENAME)
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_authenticated_service():
    oauth_data = st.secrets["google_oauth"]
    flow = Flow.from_client_config(
        {
            "installed": {
                "client_id": oauth_data["client_id"],
                "client_secret": oauth_data["client_secret"],
                "auth_uri": oauth_data["auth_uri"],
                "token_uri": oauth_data["token_uri"],
                "auth_provider_x509_cert_url": oauth_data["auth_provider_x509_cert_url"],
                "redirect_uris": [oauth_data["redirect_uri"]]
            }
        },
        scopes=SCOPES
    )
    flow.run_local_server(port=0)
    credentials = flow.credentials
    service = build('drive', 'v3', credentials=credentials)
    return service

def zip_folder(folder_path, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, arcname)

def unzip_file(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zipf.extractall(dest_dir)

def upload_faiss_to_drive():
    service = get_authenticated_service()
    zip_folder(DB_DIR, ZIP_PATH)
    file_metadata = {'name': ZIP_FILENAME}
    media = MediaFileUpload(ZIP_PATH, mimetype='application/zip')
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    os.remove(ZIP_PATH)
    return uploaded_file.get('id')

def download_faiss_from_drive():
    service = get_authenticated_service()
    results = service.files().list(q=f"name='{ZIP_FILENAME}'", spaces='drive').execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    with open(ZIP_PATH, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    unzip_file(ZIP_PATH, DB_DIR)
    os.remove(ZIP_PATH)
    return True
