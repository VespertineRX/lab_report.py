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
# These are pulled from your GitHub Secrets (GCP_CREDENTIALS, GMAIL_SENDER, GMAIL_APP_PASSWORD)
SENDER_EMAIL = os.environ.get('GMAIL_SENDER')
RECEIVER_EMAIL = "ryuzaki.vespertine@gmail.com"  # <--- UPDATE THIS
APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
GCP_JSON = os.environ.get('GCP_CREDENTIALS')

# The exact name of your Google Sheet
SHEET_NAME = 'labtest' 

def run_daily_report():
    try:
        print("Connecting to Google Sheets...")
        # 1. Authenticate with Google
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GCP_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 2. Get Data
        sheet = client.open(SHEET_NAME).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        # 3. Process Data
        # Using MM.DD.YY as per your last screenshot
        df['Date Received'] = pd.to_datetime(df['Date Received'], format='%m.%d.%y')
        today = datetime.now()

        # Filter: Ignore 'Finalized', include blanks, check for 5+ days
        mask = (df['Notes'].isna()) | (df['Notes'].astype(str).str.strip().str.lower() != 'finalized')
        pending_df = df[mask].copy()
        
        # Calculate age
        pending_df['Days Elapsed'] = (today - pending_df['Date Received']).dt.days
        overdue_df = pending_df[pending_df['Days Elapsed'] >= 5]

        # 4. Send Email if records found
        if not overdue_df.empty:
            print(f"Found {len(overdue_df)} overdue records. Sending email...")
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"LAB ALERT: {len(overdue_df)} Pending Records - {today.strftime('%m/%d/%y')}"

            # Format date for the email table
            overdue_df['Date Received'] = overdue_df['Date Received'].dt.strftime('%m.%d.%y')
            html_table = overdue_df[['Accession number', 'Patient Name', 'Date Received', 'Days Elapsed']].to_html(index=False)
            
            body = f"""
            <html>
            <head>
                <style>
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h2>Pending Records (5+ Days)</h2>
                <p>The following items were found in the log and have not been finalized:</p>
                {html_table}
                <p><i>This report was automatically generated.</i></p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
            print("Report sent successfully.")
        else:
            print("Zero overdue records found. No email sent.")

    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    run_daily_report()
