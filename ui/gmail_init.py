from __future__ import print_function
import os.path
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 只需要运行一次，之后会保存 token.json，后续使用Gmail API时会自动加载token.json
# 需要的权限（这里只要发邮件）
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}

def main():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret_219323836374-3dejcnqui3g2nurk7k61t737qjje8cap.apps.googleusercontent.com.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)

    # 构造邮件
    message = create_message(
        sender="dli861127@gmail.com",
        to="tingjia.guo@siu.edu",
        subject="Workflow Report",
        message_text="This is the workflow result."
    )

    # 调用 Gmail API 发送
    sent = service.users().messages().send(userId="me", body=message).execute()
    print("Message sent! Message ID:", sent["id"])

if __name__ == "__main__":
    main()
