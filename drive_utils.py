import os
import zipfile
import streamlit as st
import io

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Audit_FAISS_DB"

def get_authenticated_service():
    creds_data = st.secrets["google_oauth"]
    flow = Flow.from_client_config(
        {
            "installed": {
                "client_id": creds_data["client_id"],
                "client_secret": creds_data["client_secret"],
                "auth_uri": creds_data["auth_uri"],
                "token_uri": creds_data["token_uri"],
                "auth_provider_x509_cert_url": creds_data["auth_provider_x509_cert_url"],
                "redirect_uris": [creds_data["redirect_uri"]]
            }
        },
        scopes=SCOPES
    )
    flow.run_local_server(port=0)
    creds = flow.credentials
    return build("drive", "v3", credentials=creds)

def get_drive_folder_id(service):
    response = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{FOLDER_NAME}' and trashed=false",
        spaces='drive', fields='files(id, name)'
    ).execute()
    folders = response.get("files", [])
    if folders:
        return folders[0]["id"]
    metadata = {"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder.get("id")

def zip_folder(folder_path, zip_name):
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, arcname)

def unzip_file(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.extractall(dest_dir)

def upload_faiss_to_drive(folder_path, zip_name):
    service = get_authenticated_service()
    folder_id = get_drive_folder_id(service)
    zip_folder(folder_path, zip_name)

    # Delete old copy
    results = service.files().list(q=f"name='{zip_name}' and '{folder_id}' in parents and trashed=false").execute()
    for file in results.get("files", []):
        service.files().delete(fileId=file["id"]).execute()

    file_metadata = {"name": zip_name, "parents": [folder_id]}
    media = MediaFileUpload(zip_name, mimetype="application/zip")
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    os.remove(zip_name)
    return uploaded.get("id")

def download_faiss_from_drive(zip_name, dest_dir):
    service = get_authenticated_service()
    folder_id = get_drive_folder_id(service)
    files = service.files().list(q=f"name='{zip_name}' and '{folder_id}' in parents and trashed=false").execute().get("files", [])
    if not files:
        return False

    request = service.files().get_media(fileId=files[0]["id"])
    with open(zip_name, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    unzip_file(zip_name, dest_dir)
    os.remove(zip_name)
    return True
