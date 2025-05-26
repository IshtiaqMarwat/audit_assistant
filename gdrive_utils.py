import os
import zipfile
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

def authenticate_gdrive():
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

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

def upload_faiss_to_drive(folder_path, drive, file_name='faiss_vector_store.zip'):
    zip_path = f"{file_name}"
    zip_folder(folder_path, zip_path)
    file_drive = drive.CreateFile({'title': file_name})
    file_drive.SetContentFile(zip_path)
    file_drive.Upload()
    os.remove(zip_path)
    return file_drive['id']

def download_faiss_from_drive(drive, file_title='faiss_vector_store.zip', dest_dir='vector_store'):
    file_list = drive.ListFile({'q': f"title = '{file_title}' and trashed=false"}).GetList()
    if not file_list:
        return False
    file_drive = file_list[0]
    file_drive.GetContentFile(file_title)
    unzip_file(file_title, dest_dir)
    os.remove(file_title)
    return True
