import os
import zipfile
import json
import io
import streamlit as st

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
ZIP_FILENAME = "faiss_vector_store.zip"

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

def upload_faiss_to_drive(folder_path):
    service = get_authenticated_service()
    zip_folder(folder_path, ZIP_FILENAME)
    file_metadata = {'name': ZIP_FILENAME}
    media = MediaFileUpload(ZIP_FILENAME, mimetype='application/zip')
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    os.remove(ZIP_FILENAME)
    return uploaded_file.get('id')

def download_faiss_from_drive(dest_dir):
    service = get_authenticated_service()
    results = service.files().list(q=f"name='{ZIP_FILENAME}'", spaces='drive').execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = open(ZIP_FILENAME, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.close()
    unzip_file(ZIP_FILENAME, dest_dir)
    os.remove(ZIP_FILENAME)
    return True
