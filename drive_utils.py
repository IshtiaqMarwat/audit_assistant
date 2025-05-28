import os
import zipfile
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "vectordbst"
ZIP_NAME = "faiss_vector_store.zip"

# 🔐 Auth from Streamlit secrets
def get_authenticated_service():
    service_account_info = st.secrets["gdrive_service_account"]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

# 📁 Locate or create the Google Drive folder
def get_drive_folder_id(service):
    response = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{FOLDER_NAME}' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()

    folders = response.get("files", [])
    if folders:
        return folders[0]["id"]

    # Create folder if not exists
    folder_metadata = {
        "name": FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder"
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    return folder.get("id")

# 🗜️ Zip a local folder
def zip_folder(folder_path, zip_name):
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, arcname)

# 📦 Upload the FAISS DB zip to Google Drive
def upload_faiss_to_drive(local_folder_path):
    service = get_authenticated_service()
    folder_id = get_drive_folder_id(service)

    # 🗜️ Zip the FAISS DB
    zip_folder(local_folder_path, ZIP_NAME)
    st.info(f"Zip file created: {ZIP_NAME}")
    st.info(f"Zip size: {os.path.getsize(ZIP_NAME)} bytes")

    # ❌ Delete existing file with same name
    existing = service.files().list(
        q=f"name='{ZIP_NAME}' and '{folder_id}' in parents and trashed=false",
        spaces="drive", fields="files(id, name)"
    ).execute()

    for file in existing.get("files", []):
        service.files().delete(fileId=file["id"]).execute()

    # ✅ Upload to Drive folder
    file_metadata = {"name": ZIP_NAME, "parents": [folder_id]}
    media = MediaFileUpload(ZIP_NAME, mimetype="application/zip")
    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    os.remove(ZIP_NAME)

    # 🔗 Generate links
    file_id = uploaded.get("id")
    file_link = f"https://drive.google.com/file/d/{file_id}/view"
    folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

    # ✅ Optional: Share with your Gmail
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "reader", "emailAddress": "engrishtiaq455@gmail.com"},
            fields="id"
        ).execute()
        st.success("Shared with your email too!")
    except Exception as e:
        st.warning(f"Could not share file: {e}")

    # 🔎 Print access links
    st.success(f"✅ FAISS DB uploaded to Google Drive folder: [Open Folder]({folder_link})")
    st.info(f"📁 View file: [Click here]({file_link})")

    return file_link

# 📥 Download and unzip FAISS DB
def download_faiss_from_drive(dest_dir):
    service = get_authenticated_service()
    folder_id = get_drive_folder_id(service)

    files = service.files().list(
        q=f"name='{ZIP_NAME}' and '{folder_id}' in parents and trashed=false",
        spaces='drive', fields='files(id, name)'
    ).execute().get("files", [])

    if not files:
        return False

    request = service.files().get_media(fileId=files[0]["id"])
    with open(ZIP_NAME, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    with zipfile.ZipFile(ZIP_NAME, "r") as zipf:
        zipf.extractall(dest_dir)

    os.remove(ZIP_NAME)
    return True
