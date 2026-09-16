import os
import sys
import json
import re
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
    token = (
        req.headers.get("X-Service-Secret", "") or
        req.headers.get("Authorization", "") or
        req.args.get("secret", "")
    )
    if token.lower().startswith("bearer "):
        token = token[7:]
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
                    print(f"Failed to download attachment {att.get('url')}: {e}", file=sys.stderr)
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


def is_email_draft(text):
    """Case-insensitive check if text is a Vidhi email draft."""
    lower = text.lower()
    return "virtual office plan" in lower or "ready to send via chatwoot" in lower


def extract_message_content(data):
    """Extract message text from ClickUp webhook payload."""
    # ClickUp Chat webhook structure: payload.data.text_content
    try:
        tc = data.get("payload", {}).get("data", {}).get("text_content", "")
        if tc and is_email_draft(tc):
            return tc
    except Exception:
        pass

    # Fallback: deep search all strings
    def find_strings(obj, depth=0):
        strings = []
        if depth > 10:
            return strings
        if isinstance(obj, str) and len(obj) > 20:
            strings.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                strings.extend(find_strings(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                strings.extend(find_strings(item, depth + 1))
        return strings

    all_strings = find_strings(data)
    for s in sorted(all_strings, key=len, reverse=True):
        if is_email_draft(s):
            return s

    # Last resort: stringify everything
    full_text = json.dumps(data)
    if is_email_draft(full_text):
        return full_text
    return ""


def parse_vidhi_message(text):
    """Parse Vidhi's structured email output into fields."""
    result = {}
    # Clean up: unescape newlines, strip HTML
    clean = text.replace("\\n", "\n")
    clean = re.sub(r'<[^>]+>', ' ', clean)

    to_match = re.search(r'TO:\s*\[?([^\]\s,]+@[^\]\s,]+)', clean, re.IGNORECASE)
    if to_match:
        result["to_email"] = to_match.group(1).strip().rstrip('.')

    subj_match = re.search(r'SUBJECT:\s*(.+?)(?:\s*BODY:|\n|$)', clean, re.IGNORECASE)
    if subj_match:
        result["subject"] = subj_match.group(1).strip()

    body_match = re.search(r'BODY:\s*\n?(.*?)(?:Attachments to forward|Ready to send via Chatwoot|$)', clean, re.IGNORECASE | re.DOTALL)
    if body_match:
        body_text = body_match.group(1).strip()
        if len(body_text) > 10:
            result["body"] = body_text

    # If no BODY: marker, use everything after SUBJECT line as body
    if "body" not in result and "subject" in result:
        after_subj = re.search(r'SUBJECT:\s*.+?\n(.*?)(?:Attachments to forward|Ready to send via Chatwoot|$)', clean, re.IGNORECASE | re.DOTALL)
        if after_subj:
            body_text = after_subj.group(1).strip()
            if len(body_text) > 10:
                result["body"] = body_text

    return result


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


@app.route("/clickup-webhook", methods=["POST"])
def clickup_webhook():
    if not auth_check(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    print(f"=== CLICKUP WEBHOOK RECEIVED ===", file=sys.stderr)

    # Try direct JSON fields first
    if data.get("to_email") and data.get("subject") and data.get("body"):
        to_email = data["to_email"]
        subject = data["subject"]
        body = data["body"]
        attachments = data.get("attachments", [])
    else:
        message_content = extract_message_content(data)
        print(f"=== EXTRACTED (len={len(message_content)}): {message_content[:300]} ===", file=sys.stderr)

        if not message_content:
            return jsonify({"skipped": True, "reason": "No email content found"}), 200

        if not is_email_draft(message_content):
            return jsonify({"skipped": True, "reason": "Not a Vidhi email draft"}), 200

        parsed = parse_vidhi_message(message_content)
        print(f"=== PARSED: {json.dumps(parsed)} ===", file=sys.stderr)

        to_email = parsed.get("to_email")
        subject = parsed.get("subject")
        body = parsed.get("body")
        attachments = []

        if not to_email or not subject:
            return jsonify({"error": "Missing TO or SUBJECT", "parsed": parsed}), 400

        # If no body parsed, use a default
        if not body:
            body = message_content

    print(f"=== SENDING to {to_email}, subj: {subject} ===", file=sys.stderr)
    contact_id = find_or_create_contact(to_email)
    if not contact_id:
        return jsonify({"error": f"Failed to find/create contact for {to_email}"}), 500

    conversation_id = create_conversation(contact_id, subject)
    if not conversation_id:
        return jsonify({"error": "Failed to create conversation"}), 500

    result = send_message(conversation_id, body, attachments)
    print(f"=== CHATWOOT RESULT: {json.dumps(result, default=str)[:300]} ===", file=sys.stderr)

    if "error" in result:
        return jsonify({"error": result}), 500

    return jsonify({"success": True, "contact_id": contact_id, "conversation_id": conversation_id, "message": f"Email sent to {to_email} via Chatwoot", "subject": subject})


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
