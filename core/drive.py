from __future__ import annotations
from io import BytesIO
from typing import Optional, Tuple

import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def _drive_service():
    info = st.secrets["gcp_service_account"]["json_content"]
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=creds)

def upload_to_drive(
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    folder_id: Optional[str] = None,
) -> Tuple[str, str]:
    service = _drive_service()

    if folder_id is None:
        folder_id = st.secrets.get("drive_folder_id", None)

    metadata = {"name": file_name}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(BytesIO(file_bytes), mimetype=mime_type, resumable=True)

    created = service.files().create(
        body=metadata, media_body=media, fields="id,webViewLink"
    ).execute()

    return created["id"], created.get("webViewLink", "")
