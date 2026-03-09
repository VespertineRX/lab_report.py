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
# These will be pulled from GitHub Secrets
SENDER_EMAIL = os.environ.get('GMAIL_SENDER')
RECEIVER_EMAIL = "wife_email@gmail.com" # <--- Put your wife's actual email here
APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
GCP_JSON = os.environ.get('GCP_CREDENTIALS')

# The name of your Google Sheet
SHEET_NAME = 'Lab Scanning Log' 

def run_daily_report():
    try:
        # 1. Authenticate with Google
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 2. Get Data
        sheet = client.open(SHEET_NAME).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        # 3. Process Data (MM.DD.YY format)
        df['Date Received'] = pd.to_datetime(df['Date Received'], format='%m.%d.%y')
        today = datetime.now()

        # Filter: Ignore 'Finalized', keep blanks/others, check for 5+ days
        mask = (df['Notes'].isna()) | (df['Notes'].astype(str).str.strip().str.lower() != 'finalized')
        pending_df = df[mask].copy()
        pending_df['Days Elapsed'] = (today - pending_df['Date Received']).dt.days
        overdue_df = pending_df[pending_df['Days Elapsed'] >= 5]

        # 4. Send Email
        if not overdue_df.empty:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"PENDING LAB RECORDS: {today.strftime('%m/%d/%y')}"

            # Formatting the table for the email
            # We convert the Date back to a readable string for the email
            overdue_df['Date Received'] = overdue_df['Date Received'].dt.strftime('%m.%d.%y')
            html_table = overdue_df[['Accession number', 'Patient Name', 'Date Received', 'Days Elapsed']].to_html(index=False)
            
            body = f"<html><body><h3>The following records are 5+ days old:</h3>{html_table}</body></html>"
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
            print("Email sent.")
        else:
            print("Nothing overdue today.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_daily_report()
