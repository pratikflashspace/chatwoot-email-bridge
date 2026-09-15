import os
import json
import requests
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "")

HEADERS = {
    "api_access_token": CHATWOOT_TOKEN,
    "Content-Type": "application/json"
}

def auth_check(req):
    token = req.headers.get("X-Service-Secret", "") or req.args.get("secret", "")
    if SERVICE_SECRET and token != SERVICE_SECRET:
        return False
    return True


def find_or_create_contact(email, name=None):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search"
    params = {"q": email}
    resp = requests.get(url, headers=HEADERS, params=params)
    data = resp.json()
    if data.get("payload") and len(data["payload"]) > 0:
        for contact in data["payload"]:
            if contact.get("email", "").lower() == email.lower():
                return contact["id"]
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts"
    payload = {"email": email}
    if name:
        payload["name"] = name
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code in (200, 201):
        return resp.json().get("payload", {}).get("contact", {}).get("id")
    return None


def create_conversation(contact_id, subject=None):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations"
    payload = {
        "inbox_id": CHATWOOT_INBOX_ID,
        "contact_id": contact_id,
        "status": "open",
        "additional_attributes": {}
    }
    if subject:
        payload["additional_attributes"]["mail_subject"] = subject
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    return None


def send_message(conversation_id, content, attachments=None):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"
    if attachments and len(attachments) > 0:
        files = []
        for i, att in enumerate(attachments):
            if att.get("url"):
                try:
                    file_resp = requests.get(att["url"], timeout=30)
                    file_content = file_resp.content
                    filename = att.get("name", f"attachment_{i}")
                    files.append(("attachments[]", (filename, file_content, att.get("content_type", "application/octet-stream"))))
                except Exception as e:
                    print(f"Failed to download attachment {att.get('url')}: {e}")
            elif att.get("base64"):
                file_content = base64.b64decode(att["base64"])
                filename = att.get("name", f"attachment_{i}")
                files.append(("attachments[]", (filename, file_content, att.get("content_type", "application/octet-stream"))))
        headers_no_ct = {"api_access_token": CHATWOOT_TOKEN}
        resp = requests.post(url, headers=headers_no_ct, data={"content": content, "message_type": "outgoing", "content_type": "input_email"}, files=files)
    else:
        payload = {"content": content, "message_type": "outgoing", "content_type": "input_email"}
        resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code in (200, 201):
        return resp.json()
    return {"error": resp.text, "status_code": resp.status_code}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "chatwoot-bridge"})


@app.route("/send-email", methods=["POST"])
def send_email():
    if not auth_check(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400
    to_email = data.get("to_email")
    to_name = data.get("to_name")
    subject = data.get("subject")
    body = data.get("body")
    attachments = data.get("attachments", [])
    if not to_email or not subject or not body:
        return jsonify({"error": "Missing required fields: to_email, subject, body"}), 400
    contact_id = find_or_create_contact(to_email, to_name)
    if not contact_id:
        return jsonify({"error": f"Failed to find/create contact for {to_email}"}), 500
    conversation_id = create_conversation(contact_id, subject)
    if not conversation_id:
        return jsonify({"error": "Failed to create conversation"}), 500
    result = send_message(conversation_id, body, attachments)
    if "error" in result:
        return jsonify({"error": result}), 500
    return jsonify({"success": True, "contact_id": contact_id, "conversation_id": conversation_id, "message": "Email sent via Chatwoot"})


@app.route("/test", methods=["GET"])
def test():
    if not auth_check(request):
        return jsonify({"error": "Unauthorized"}), 401
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/inboxes"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        inboxes = resp.json().get("payload", [])
        inbox_names = [{"id": i["id"], "name": i["name"]} for i in inboxes]
        return jsonify({"status": "connected", "inboxes": inbox_names})
    return jsonify({"status": "error", "details": resp.text}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
