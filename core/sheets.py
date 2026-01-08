
import streamlit as st
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

@st.cache_resource
def get_db():
    creds_json = json.loads(st.secrets["gcp_service_account"]["json_content"], strict=False)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope))
    return client.open("GestorObras_DB")
