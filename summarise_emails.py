import os
import base64
import pickle
import openai
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def authenticate_gmail_api():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def authenticate_openai_api():
    with open("openaikey.txt", "r") as key_file:
        openai.api_key = key_file.read().strip()

def get_emails_from_sender(service, sender_email, user_id='me'):
    query = f"from:{sender_email}"
    response = service.users().messages().list(userId=user_id, q=query).execute()
    messages = response.get('messages', [])
    emails = []

    for message in messages:
        msg_id = message['id']
        msg = service.users().messages().get(userId=user_id, id=msg_id).execute()
        payload = msg['payload']
        headers = payload['headers']

        email_data = {
            'id': msg_id,
            'snippet': msg['snippet'],
            'subject': None,
            'from': None,
            'to': None,
            'date': None,
            'content': None
        }

        for header in headers:
            if header['name'] == 'subject' or header['name'] == 'Subject':
                email_data['subject'] = header['value']
            if header['name'] == 'From':
                email_data['from'] = header['value']
            if header['name'] == 'To':
                email_data['to'] = header['value']
            if header['name'] == 'Date':
                email_data['date'] = header['value']

        if 'parts' in payload:
            parts = payload['parts']
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    email_data['content'] = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
            emails.append(email_data)
        return emails

def summarize_email_content(content):
    prompt = f"Please summarize the following email content:\n\n{content}\n\nSummary:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=50,
        n=1,
        stop=None,
        temperature=0.5,
    )

    return response.choices[0].text.strip()

def detect_email_tone(content):
    prompt = f"Please detect the tone of the following email content:\n\n{content}\n\nTone:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=20,
        n=1,
        stop=None,
        temperature=0.5,
    )

    return response.choices[0].text.strip()

def main():
    # Authenticate with the Gmail and OpenAI APIs
    gmail_service = authenticate_gmail_api()
    authenticate_openai_api()

    # Replace 'sender@example.com' with the sender's email address you want to filter
    sender_email = 'JasonMM@intellichoice.com.au'
    emails = get_emails_from_sender(gmail_service, sender_email)
    if emails:
    # Create a log file to store the email data along with the context and tone attributes
        with open("email_log.txt", "w") as log_file:
            for email in emails:
                content = email['content']

                summary = summarize_email_content(content)
                tone = detect_email_tone(content)

                log_entry = f"Subject: {email['subject']}\n" \
                            f"From: {email['from']}\n" \
                            f"To: {email['to']}\n" \
                            f"Date: {email['date']}\n" \
                            f"Summary: {summary}\n" \
                            f"Tone: {tone}\n\n" \
                            f"{'-'*80}\n\n"
                
                log_file.write(log_entry)

        print("Email log has been created.")
    else:
        print("No emails found.")

if __name__ == "__main__":
    main()
