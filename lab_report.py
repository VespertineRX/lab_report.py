import os
import json
import gspread
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials

# --- SETTINGS ---
SENDER_EMAIL = os.environ.get('GMAIL_SENDER')
RECEIVER_EMAIL = "ryuzaki.vespertine@gmail.com" # <--- Double check this is correct!
APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
GCP_JSON = os.environ.get('GCP_CREDENTIALS')
SHEET_NAME = 'Lab Scanning Log' 

def run_daily_report():
    try:
        print("Checking connection to Google...")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet = client.open(SHEET_NAME).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        print(f"Successfully pulled {len(df)} rows from Google Sheets.")

        # Process dates
        df['Date Received'] = pd.to_datetime(df['Date Received'], format='%m.%d.%y')
        today = datetime.now()

        # Filter: Not Finalized AND 5+ days old
        mask = (df['Notes'].isna()) | (df['Notes'].astype(str).str.strip().str.lower() != 'finalized')
        pending_df = df[mask].copy()
        
        pending_df['Days Elapsed'] = (today - pending_df['Date Received']).dt.days
        overdue_df = pending_df[pending_df['Days Elapsed'] >= 5]

        # --- EMAIL LOGIC ---
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        
        if not overdue_df.empty:
            print(f"Found {len(overdue_df)} overdue items. Sending alert to {RECEIVER_EMAIL}...")
            msg['To'] = RECEIVER_EMAIL
            msg['Cc'] = SENDER_EMAIL
            msg['Subject'] = f"ACTION REQUIRED: {len(overdue_df)} Overdue Records"
            
            overdue_df['Date Received'] = overdue_df['Date Received'].dt.strftime('%m.%d.%y')
            html_table = overdue_df[['Accession number', 'Patient Name', 'Date Received', 'Days Elapsed']].to_html(index=False)
            body = f"<html><body><h3>The following records are 5+ days old:</h3>{html_table}</body></html>"
        else:
            print("Nothing overdue. Sending 'System Check' email to Sender only.")
            msg['To'] = SENDER_EMAIL
            msg['Subject'] = "Lab Script Status: All Clear"
            body = "<html><body><p>The script ran successfully. No records were 5+ days old today.</p></body></html>"

        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully.")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_daily_report()
