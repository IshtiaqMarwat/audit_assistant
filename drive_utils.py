import os
import zipfile
import streamlit as st
import json
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Audit_FAISS_DB"

def get_authenticated_service():
    service_account_info = json.loads(st.secrets["gdrive_service_account"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

def get_drive_folder_id(service):
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{FOLDER_NAME}' and trashed=false",
        spaces='drive', fields='files(id, name)'
    ).execute()
    folders = results.get("files", [])
    if folders:
        return folders[0]["id"]

    folder_metadata = {"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=folder_metadata, fields="id").execute()
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

    existing_files = service.files().list(q=f"name='{zip_name}' and '{folder_id}' in parents").execute()
    for file in existing_files.get("files", []):
        service.files().delete(fileId=file["id"]).execute()

    file_metadata = {"name": zip_name, "parents": [folder_id]}
    media = MediaFileUpload(zip_name, mimetype="application/zip")
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    os.remove(zip_name)
    return uploaded.get("id")

def download_faiss_from_drive(zip_name, dest_dir):
    service = get_authenticated_service()
    folder_id = get_drive_folder_id(service)
    files = service.files().list(q=f"name='{zip_name}' and '{folder_id}' in parents").execute().get("files", [])
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
