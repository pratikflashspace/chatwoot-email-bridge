import os, json, glob, requests, sys, time

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = "1"
CHATWOOT_INBOX_ID = 35
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
HEADERS = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}

def find_or_create_contact(email, name=None):
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",
                     headers=HEADERS, params={"q": email})
    for c in r.json().get("payload", []):
        if c.get("email", "").lower() == email.lower():
            return c["id"]
    p = {"email": email}
    if name: p["name"] = name
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts",
                      headers=HEADERS, json=p)
    return r.json().get("payload", {}).get("contact", {}).get("id") if r.status_code in (200, 201) else None

def create_conversation(contact_id, subject):
    aa = {"mail_subject": subject}
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations",
                      headers=HEADERS,
                      json={"inbox_id": CHATWOOT_INBOX_ID, "contact_id": contact_id,
                            "status": "open", "additional_attributes": aa})
    return r.json().get("id") if r.status_code in (200, 201) else None

def download_attachment(url):
    try:
        r = requests.get(url, headers={"Authorization": CLICKUP_API_TOKEN},
                        timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 50:
            ct = r.headers.get("Content-Type", "application/octet-stream")
            return r.content, ct
    except Exception as e:
        print(f"  Download failed: {e}")
    return None, None

def send_message(conv_id, body, attachments, cc_email=None):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages"
    form_data = {"content": body, "message_type": "outgoing", "content_type": "input_email"}
    if cc_email:
        form_data["cc_emails"] = cc_email
    files = []
    for att in attachments:
        files.append(("attachments[]", (att["name"], att["content"], att["content_type"])))
    if files:
        r = requests.post(url, headers={"api_access_token": CHATWOOT_TOKEN},
                         data=form_data, files=files)
    else:
        r = requests.post(url, headers=HEADERS, json={**form_data})
    print(f"  Chatwoot response: {r.status_code}")
    return r.status_code in (200, 201)

def process_job(filepath):
    print(f"\n=== Processing: {filepath} ===")
    with open(filepath) as f:
        job = json.load(f)
    to_email = job["to_email"]
    cc_email = job.get("cc_email")
    sp_name = job.get("sp_name", "")
    subject = job["subject"]
    body = job["body"]
    attachment_list = job.get("attachments", [])
    print(f"  TO: {to_email}")
    print(f"  CC: {cc_email or 'none'}")
    print(f"  Subject: {subject}")
    print(f"  Attachments: {len(attachment_list)}")
    contact_id = find_or_create_contact(to_email, sp_name)
    if not contact_id:
        print("  ERROR: Could not create contact")
        return False
    conv_id = create_conversation(contact_id, subject)
    if not conv_id:
        print("  ERROR: Could not create conversation")
        return False
    downloaded = []
    for att in attachment_list:
        print(f"  Downloading: {att['name']}...")
        content, ct = download_attachment(att["url"])
        if content:
            downloaded.append({"name": att["name"], "content": content, "content_type": ct})
            print(f"    OK ({len(content)} bytes)")
        else:
            print(f"    FAILED - skipping")
    success = send_message(conv_id, body, downloaded, cc_email)
    if success:
        print(f"  SENT to {to_email} with {len(downloaded)} attachments")
    else:
        print(f"  SEND FAILED")
    return success

jobs = sorted(glob.glob("jobs/*.json"))
if not jobs:
    print("No job files found")
    sys.exit(0)
print(f"Found {len(jobs)} job(s)")
results = []
for j in jobs:
    try:
        ok = process_job(j)
        results.append((j, ok))
    except Exception as e:
        print(f"  ERROR processing {j}: {e}")
        results.append((j, False))
print(f"\n=== Summary ===")
for path, ok in results:
    print(f"  {'OK' if ok else 'FAIL'}: {path}")
failed = [r for r in results if not r[1]]
if failed:
    print(f"\n{len(failed)} job(s) failed")
    sys.exit(1)
