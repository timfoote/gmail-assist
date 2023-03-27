import os
import base64
import pickle
import openai
import time
import re
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
    query = f"from:{sender_email} after:2023/02/01 before:2023/02/14"
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
            'content': '' # Initialize content to an empty string
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
        else:
            email_data['content'] = "This email does not contain any content."

        emails.append(email_data)

    return emails


def remove_inline_replies(content):
    # Remove quoted text starting with ">"
    content = re.sub(r'^>.*$', '', content, flags=re.MULTILINE)

    # Remove inline replies starting with "On...wrote:"
    content = re.sub(r'On\s.*\swrote:.*', '', content, flags=re.MULTILINE)

    return content


# def summarize_and_detect_tone(content):
#     prompt = (f"Please summarize the following email content and detect its tone:\n\n"
#               f"{content}\n\n"
#               f"==Summary==\n{{summary}}"
#               f"==Tone==\n{{tone}}")

#     response = openai.Completion.create(
#         engine="text-davinci-003",
#         prompt=prompt,
#         max_tokens=500,
#         n=1,
#         stop=None,
#         temperature=0.5,
#     )

#     result_text = response.choices[0].text.strip()
#     matches = re.findall(r'==Summary==\n(.*?)\n==Tone==\n(.*?)', result_text, re.DOTALL)

#     if matches:
#         summary, tone = matches[0]
#         return summary.strip(), tone.strip()
#     else:
#         return "Summary not found", "Tone not found"

# def summarize_and_detect_tone(content):
#     prompt = (f"Please summarize the following email content and detect its tone:\n\n"
#               f"{content}\n\n"
#               f"==Summary==\n{{summary}}"
#               f"==Tone==\n{{tone}}")

#     response = openai.Completion.create(
#         engine="text-davinci-003",
#         prompt=prompt,
#         max_tokens=1000,
#         n=1,
#         stop=None,
#         temperature=0.5,
#     )

#     result_text = response.choices[0].text.strip()
#     result_lines = result_text.splitlines()

#     summary = "Summary not found"
#     tone = "Tone not found"

#     for i, line in enumerate(result_lines):
#         if line.startswith("==Summary=="):
#             summary = result_lines[i + 1].strip()
#         if line.startswith("==Tone=="):
#             tone = result_lines[i + 1].strip()

#     return summary, tone

def summarize_and_detect_tone(content):
    if len(content) < 50:  # Adjust this value as needed
        return "Content is too short to summarize.", "Not applicable"
    
    prompt = (f"Please summarize the following email content and detect its tone:\n\n"
              f"{content}\n\n"
              f"Summary: {{summary}}\n"
              f"Tone: {{tone}}")

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1000,
        n=1,
        stop=None,
        temperature=0.5,
    )

    result_text = response.choices[0].text.strip()
    result_lines = result_text.splitlines()

    summary = "Summary not found"
    tone = "Tone not found"

    for line in result_lines:
        if line.startswith("Summary:"):
            summary = line[len("Summary:"):].strip()
        if line.startswith("Tone:"):
            tone = line[len("Tone:"):].strip()

    return summary, tone


def main():
    # Authenticate with the Gmail and OpenAI APIs
    gmail_service = authenticate_gmail_api()
    authenticate_openai_api()

    # Replace 'sender@example.com' with the sender's email address you want to filter
    sender_email = 'terri.howarth@gmail.com'
    emails = get_emails_from_sender(gmail_service, sender_email)
    if emails:
        for email in emails:
            content = email['content']
            if content:
                cleaned_content = remove_inline_replies(content)
                summary, tone = summarize_and_detect_tone(cleaned_content)
                time.sleep(3)  # Add a delay between combined API calls

                log_entry = (f"Subject: {email['subject']}\n"
                             f"From: {email['from']}\n"
                             f"To: {email['to']}\n"
                             f"Date: {email['date']}\n"
                             f"Summary: {summary}\n"
                             f"Tone: {tone}\n\n"
                             f"{'-'*80}\n\n")
                    
                with open("email_log.txt", "a") as log_file:
                    log_file.write(log_entry)
                    log_file.flush()

        print("Email log has been created.")
    else:
        print("No emails found.")

if __name__ == "__main__":
    main()
