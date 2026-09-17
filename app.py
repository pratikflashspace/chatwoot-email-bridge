import os, sys, json, re, requests, base64, time
from flask import Flask, request, jsonify

app = Flask(__name__)

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "")
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_TEAM_ID = os.environ.get("CLICKUP_TEAM_ID", "1851686")
DOC_PANEL_VIEW_ID = os.environ.get("DOC_PANEL_VIEW_ID", "1rg96-107936")

HEADERS = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
CLICKUP_HEADERS = {"Authorization": CLICKUP_API_TOKEN, "Content-Type": "application/json"}

PAYMENT_KEYWORDS = ["payment", "amount", "token amount", "paid", "transaction", "receipt", "invoice", "bank statement", "account statement", "upi", "neft", "imps", "flash space token"]

VOS_MAPPING = {
    "IndiraNagar - Aspire Coworks": {"email":"aspirecoworkings@gmail.com","address":"17, 7th Main Rd, Indira Nagar II Stage, Hoysala Nagar, Indiranagar, Bengaluru, Karnataka 560038, India","city":"BANGALORE"},
    "Koramangala - Aspire Coworks": {"email":"aspirecoworkings@gmail.com","address":"2nd & 3rd Floor, Balaji Arcade, 472/7, 20th L Cross Rd, 4th Block, Koramangala, Bengaluru, Karnataka 560095, India","city":"BANGALORE"},
    "EcoSpace - Hebbal, HMT Layout": {"email":"ecospaceblr@gmail.com","address":"No,33, 4th Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India","city":"BANGALORE"},
    "Laksh Space - Hebbal, HMT layout": {"email":"Lakshspaceblr@gmail.com","address":"No,33, 1st Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India","city":"BANGALORE"},
    "RegisterKaro - Old Airport Road": {"email":"rupeshrai@registerkaro.com","address":"Unit 101, Oxford Towers, No. 139 Old Airport Road, Bengaluru-560008","city":"BANGALORE"},
    "Getset Spaces - Green Park": {"email":"booking.del@getsetoffice.in","address":"Commercial Complex, 400A, 4th Floor, 12 Ajit Singh House, Yusuf Sarai, Green Park, New Delhi, Delhi 110016","city":"DELHI"},
    "CP Alt F": {"email":None,"address":"J6JF+53C, Connaught Lane, Barakhamba, New Delhi, Delhi 110001, India","city":"DELHI"},
    "Mytime Cowork - Saket": {"email":"Sales@mytimeco.work","address":"55 Lane-2, Westend Marg, Saiyad Ul Ajaib Village, Saket, New Delhi, Delhi 110030, India","city":"DELHI"},
    "Okhla Alt F": {"email":None,"address":"101, NH-19, CRRI, Ishwar Nagar, Okhla, New Delhi, Delhi 110044, India","city":"DELHI"},
    "WBB Office": {"email":"Info@wbboffice.com","address":"Room no 1 No. 19, Metro Station, 35, Anna Salai, near Little Mount, Little Mount, Nandanam, Chennai, Tamil Nadu 600015, India","city":"DELHI"},
    "MSB Cospazes": {"email":"msbcospazesofficials@gmail.com","address":"No.26-27-A, H- Block, Third Floor, (Office No.401 & 404) Vikas Marg, Laxmi Nagar, Delhi-110092","city":"DELHI"},
    "RegisterKaro - Okhla": {"email":"rupeshrai@registerkaro.com","address":"808B, DLF Prime Tower, Pocket F, Okhla Phase I, Okhla Industrial Estate, New Delhi, Delhi 110020","city":"DELHI"},
    "Getset Spaces - Gurgaon": {"email":"booking.ggn@getsetoffice.in","address":"Unit No. 309, 3rd Floor, Tower-A of Eleven Bay (Former SAS Tower), Support Area, Medicity, Sector-38, Gurgaon 122001","city":"GURGAON"},
    "Infrapro - Sector 44": {"email":"nitish@infraprospaces.com","address":"Plot no 4, 2nd floor, Minarch Tower, Sector 44, Gurugram, Haryana 122003, India","city":"GURGAON"},
    "TEAM COWORK - Palm Court": {"email":"virtualoffice@teamco.work","address":"Mehrauli Rd, Gurugram, Haryana 122022, India","city":"GURGAON"},
    "The Work Lounge - Sector 66": {"email":"theworkloungen@gmail.com","address":"02-007, 2nd Floor, Emar The Palm Square, Sector 66, Golf Course Road, Extension, Gurugram, Haryana, 122102","city":"GURGAON"},
    "MSB COspaze - Bhondsi": {"email":"msbcospazesofficials@gmail.com","address":"2nd Floor, Sona Marble Building, Sneh Vihar, Bhondsi, Gurgaon - 122102","city":"GURGAON"},
    "Click Office - Sector 2": {"email":"Hr@clickoffice.in","address":"B-128, B Block, Sector 2, Noida, Uttar Pradesh 201301","city":"NOIDA"},
    "Crystaa - Sector 63": {"email":"crystatower@gmail.com","address":"63m, Ivent, C-030, C Block, Sector 63, Noida, Hazratpur Wajidpur, Uttar Pradesh 201309, India","city":"NOIDA"},
    "Workshala - Sector 3": {"email":"mohitbhargav28@gmail.com","address":"D-9, Vyapar Marg, Block D, Noida Sector 3, Noida, Uttar Pradesh 201301, India","city":"NOIDA"},
    "RegisterKaro - Sector 90": {"email":"rupeshrai@registerkaro.com","address":"603 604, FLOOR 6th, TOWER B BHUTANI ALPHATHUM, SECTOR 90, NOIDA, 201305.","city":"NOIDA"},
    "Alt F - Sector 62": {"email":None,"address":"C-20, 1/1A, Coast Guard Golf Ground Rd, C Block, Phase 2, Industrial Area, Sector 62, Noida, Uttar Pradesh 201309","city":"NOIDA"},
    "Alt F - Sector 142": {"email":None,"address":"Ground Floor, Plot No. 21 & 21A, Sector 142, Noida, Uttar Pradesh 201304","city":"NOIDA"},
    "Alt F - Sector 58": {"email":None,"address":"A100, A Block, Sector 58, Noida, Uttar Pradesh 201309","city":"NOIDA"},
    "Alt F - Sector 68": {"email":None,"address":"A-5, Grovy Optiva, Block A, Sector 68, Noida, Basi Bahuddin Nagar, Uttar Pradesh 201316","city":"NOIDA"},
    "Naitik Get Set Office": {"email":"naitikkr32@gmail.com","address":"648/4 DEVLI VILLAGE BANGALORE - 110062 1 FLOOR","city":"BANGALORE"},
}


def match_space_partner(sp_text, loc_text):
    sp = sp_text.lower().strip()
    loc = loc_text.lower().strip()
    both = sp + " " + loc
    if "stirring" in sp or sp in ("sm", "stirringminds"): return None, "DIRECT_BOOKING"
    if "aspire" in sp:
        return ("Koramangala - Aspire Coworks", None) if "koramangala" in both else ("IndiraNagar - Aspire Coworks", None)
    if "eco" in sp and "space" in sp or "ecospace" in sp.replace(" ",""): return "EcoSpace - Hebbal, HMT Layout", None
    if "laksh" in sp: return "Laksh Space - Hebbal, HMT layout", None
    if "get" in sp and "set" in sp or "getset" in sp.replace(" ",""):
        if any(w in both for w in ["green park", "delhi", "central"]): return "Getset Spaces - Green Park", None
        if any(w in both for w in ["gurgaon", "gurugram", "ggn"]): return "Getset Spaces - Gurgaon", None
        if any(w in both for w in ["naitik", "test"]): return "Naitik Get Set Office", None
        if any(w in loc for w in ["delhi"]): return "Getset Spaces - Green Park", None
        if any(w in loc for w in ["gurgaon", "gurugram"]): return "Getset Spaces - Gurgaon", None
        return "Getset Spaces - Green Park", None
    if "click" in sp and "office" in sp: return "Click Office - Sector 2", None
    if "crysta" in sp: return "Crystaa - Sector 63", None
    if "alt" in sp and "f" in sp:
        if "cp" in both or "connaught" in both: return "CP Alt F", None
        if "okhla" in both: return "Okhla Alt F", None
        if "62" in both: return "Alt F - Sector 62", None
        if "142" in both: return "Alt F - Sector 142", None
        if "58" in both: return "Alt F - Sector 58", None
        if "68" in both: return "Alt F - Sector 68", None
        return None, "ALT_F_LOCATION_UNCLEAR"
    if "mytime" in sp or "my time" in sp: return "Mytime Cowork - Saket", None
    if "wbb" in sp: return "WBB Office", None
    if "msb" in sp:
        return ("MSB COspaze - Bhondsi", None) if any(w in both for w in ["bhondsi", "gurgaon", "gurugram"]) else ("MSB Cospazes", None)
    if "register" in sp and "karo" in sp:
        if any(w in both for w in ["okhla"]): return "RegisterKaro - Okhla", None
        if any(w in both for w in ["airport", "bangalore", "bengaluru"]): return "RegisterKaro - Old Airport Road", None
        if any(w in both for w in ["noida", "90", "sector 90"]): return "RegisterKaro - Sector 90", None
        return None, "REGISTERKARO_LOCATION_UNCLEAR"
    if "infrapro" in sp: return "Infrapro - Sector 44", None
    if "team" in sp and ("cowork" in sp or "co work" in sp) or "palm court" in sp: return "TEAM COWORK - Palm Court", None
    if "work" in sp and "lounge" in sp: return "The Work Lounge - Sector 66", None
    if "workshala" in sp: return "Workshala - Sector 3", None
    return None, "NOT_IN_ELIGIBLE_LIST"


def parse_booking(text):
    b = {}
    def grab(patterns, t=text):
        for p in patterns:
            m = re.search(p, t, re.IGNORECASE)
            if m: return m.group(1).strip()
        return ""
    b["company_name"] = grab([r'Company\s*Name\s*[:=\-]\s*\*?\*?\s*(.+?)(?:\n|$)'])
    b["signatory"] = grab([r'(?:Director|Authorised Signatory|Authorized Signatory)\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["phone"] = grab([r'Phone\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["email"] = grab([r'Email\s*[:=\-]\s*\[?([^\]\s\n]+@[^\]\s\n]+)'])
    b["location"] = grab([r'Location\s*/?\s*City\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["space_partner"] = grab([r'Space\s*Partner\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["firm_type"] = grab([r'Firm\s*Type\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["plan"] = grab([r'Plan\s*/?\s*Package\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["nature_of_business"] = grab([r'Nature\s*of\s*Business\s*[:=\-]\s*(.+?)(?:\n|$)', r'Business\s*Description\s*[:=\-]\s*(.+?)(?:\n|$)'])
    for k in b:
        b[k] = re.sub(r'\*+', '', b[k]).strip()
        b[k] = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', b[k])
    return b


def is_payment_file(filename):
    fn = filename.lower()
    for kw in PAYMENT_KEYWORDS:
        if kw in fn: return True
    return False


def fetch_comment_attachments(comment_id):
    """Fetch attachments for a ClickUp chat comment."""
    attachments = []
    if not CLICKUP_API_TOKEN:
        print("=== No ClickUp token ===", file=sys.stderr)
        return attachments

    # Method 1: v3 entity attachments endpoint
    url1 = f"https://api.clickup.com/api/v3/workspaces/{CLICKUP_TEAM_ID}/comments/{comment_id}/attachments"
    print(f"=== v3 try: {url1} ===", file=sys.stderr)
    try:
        r = requests.get(url1, headers=CLICKUP_HEADERS, timeout=15)
        print(f"=== v3: {r.status_code} ===", file=sys.stderr)
        if r.status_code == 200:
            data = r.json()
            for att in data.get("attachments", data.get("data", [])):
                url_val = att.get("url", att.get("download_url", ""))
                name = att.get("title", att.get("name", att.get("filename", "file")))
                ext = att.get("extension", "")
                if ext and not name.endswith(f".{ext}"): name = f"{name}.{ext}"
                mime = att.get("mimetype", att.get("mime_type", "application/octet-stream"))
                if url_val and not is_payment_file(name):
                    attachments.append({"url": url_val, "name": name, "mime": mime})
            if attachments:
                print(f"=== v3 found {len(attachments)}: {[a['name'] for a in attachments]} ===", file=sys.stderr)
                return attachments
    except Exception as e:
        print(f"=== v3 err: {e} ===", file=sys.stderr)

    # Method 2: Get chat view comments via v2, parse rich text for attachment-id and image-id
    url2 = f"https://api.clickup.com/api/v2/view/{DOC_PANEL_VIEW_ID}/comment"
    print(f"=== v2 try: {url2} start_id={comment_id} ===", file=sys.stderr)
    try:
        r = requests.get(url2, headers=CLICKUP_HEADERS, params={"start_id": str(comment_id)}, timeout=15)
        print(f"=== v2: {r.status_code} ===", file=sys.stderr)
        if r.status_code == 200:
            full_response = r.json()
            comments = full_response.get("comments", [])
            print(f"=== v2 got {len(comments)} comments ===", file=sys.stderr)
            
            # Find our specific comment
            target_comment = None
            for c in comments:
                if str(c.get("id")) == str(comment_id):
                    target_comment = c
                    break
            
            if not target_comment:
                print(f"=== Comment {comment_id} not in v2 results, trying first comment ===", file=sys.stderr)
                if comments:
                    target_comment = comments[0]
            
            if target_comment:
                segments = target_comment.get("comment", [])
                print(f"=== Scanning {len(segments)} segments for attachments ===", file=sys.stderr)
                
                for i, seg in enumerate(segments):
                    attrs = seg.get("attributes", {})
                    text = seg.get("text", "")
                    seg_type = seg.get("type", "")
                    
                    # Check for embedded PDF/doc attachments
                    att_id = attrs.get("attachment-id", "")
                    att_name = attrs.get("attachment-name", "")
                    embed_type = attrs.get("embed-type", "")
                    
                    if att_id:
                        print(f"=== Segment {i}: attachment-id={att_id} name={att_name} ===", file=sys.stderr)
                        if att_name and not is_payment_file(att_name):
                            dl_url = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{att_id}"
                            attachments.append({"url": dl_url, "name": att_name, "mime": "application/octet-stream"})
                    
                    # Check for inline images (Aadhaar, PAN scans)
                    img_id = attrs.get("image-id", "")
                    if img_id:
                        img_ext = img_id.split(".")[-1] if "." in img_id else "jpg"
                        img_name = f"document_{len(attachments)+1}.{img_ext}"
                        dl_url = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{img_id}"
                        attachments.append({"url": dl_url, "name": img_name, "mime": f"image/{img_ext}"})
                        print(f"=== Segment {i}: image-id={img_id} ===", file=sys.stderr)
                    
                    # Check for type=attachment segments
                    if seg_type == "attachment" or embed_type == "attachment":
                        if not att_id:  # not already handled
                            print(f"=== Segment {i}: type=attachment but no att_id, attrs={json.dumps(attrs)} ===", file=sys.stderr)
                
                print(f"=== v2 extracted {len(attachments)} attachments ===", file=sys.stderr)
    except Exception as e:
        print(f"=== v2 err: {e} ===", file=sys.stderr)

    # Method 3: Parse the raw webhook payload comment array as fallback
    # (handled by caller if methods 1 and 2 fail)
    return attachments


def fetch_attachments_from_webhook_payload(data):
    """Extract attachment info directly from the webhook payload's comment array."""
    attachments = []
    try:
        comment_segments = data.get("payload", {}).get("data", {}).get("comment", [])
        if not isinstance(comment_segments, list):
            return attachments
        
        print(f"=== Webhook payload has {len(comment_segments)} comment segments ===", file=sys.stderr)
        
        for i, seg in enumerate(comment_segments):
            attrs = seg.get("attributes", {})
            
            att_id = attrs.get("attachment-id", "")
            att_name = attrs.get("attachment-name", "")
            img_id = attrs.get("image-id", "")
            
            if att_id and att_name and not is_payment_file(att_name):
                dl_url = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{att_id}"
                attachments.append({"url": dl_url, "name": att_name, "mime": "application/octet-stream"})
                print(f"=== Webhook seg {i}: PDF {att_name} ===", file=sys.stderr)
            
            if img_id:
                img_ext = img_id.split(".")[-1] if "." in img_id else "jpg"
                img_name = f"document_{len(attachments)+1}.{img_ext}"
                dl_url = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{img_id}"
                attachments.append({"url": dl_url, "name": img_name, "mime": f"image/{img_ext}"})
                print(f"=== Webhook seg {i}: IMG {img_id} ===", file=sys.stderr)
    except Exception as e:
        print(f"=== Webhook parse err: {e} ===", file=sys.stderr)
    
    return attachments


def download_file(url):
    """Download a file from URL with ClickUp auth."""
    try:
        headers = {"Authorization": CLICKUP_API_TOKEN}
        r = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 50:
            return r.content, r.headers.get("Content-Type", "application/octet-stream")
        print(f"=== Download {r.status_code} ({len(r.content)} bytes): {url[:80]} ===", file=sys.stderr)
    except Exception as e:
        print(f"=== Download err: {url[:60]}: {e} ===", file=sys.stderr)
    return None, None


def send_chatwoot_with_attachments(conversation_id, content, files):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"
    if files:
        form_files = [("attachments[]", (f["name"], f["content"], f.get("content_type", "application/octet-stream"))) for f in files]
        r = requests.post(url, headers={"api_access_token": CHATWOOT_TOKEN}, data={"content": content, "message_type": "outgoing", "content_type": "input_email"}, files=form_files)
    else:
        r = requests.post(url, headers=HEADERS, json={"content": content, "message_type": "outgoing", "content_type": "input_email"})
    return r.json() if r.status_code in (200, 201) else {"error": r.text}


def auth_check(req):
    token = req.headers.get("X-Service-Secret","") or req.headers.get("Authorization","") or req.args.get("secret","")
    if token.lower().startswith("bearer "): token = token[7:]
    return not SERVICE_SECRET or token == SERVICE_SECRET

def find_or_create_contact(email, name=None):
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search", headers=HEADERS, params={"q": email})
    for c in r.json().get("payload", []):
        if c.get("email","").lower() == email.lower(): return c["id"]
    payload = {"email": email}
    if name: payload["name"] = name
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts", headers=HEADERS, json=payload)
    return r.json().get("payload",{}).get("contact",{}).get("id") if r.status_code in (200,201) else None

def create_conversation(contact_id, subject):
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations", headers=HEADERS,
        json={"inbox_id": CHATWOOT_INBOX_ID, "contact_id": contact_id, "status": "open", "additional_attributes": {"mail_subject": subject}})
    return r.json().get("id") if r.status_code in (200,201) else None


@app.route("/health")
def health():
    return jsonify({"status": "ok", "v": "5.1", "cu_token": "set" if CLICKUP_API_TOKEN else "no"})

@app.route("/test")
def test():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/inboxes", headers=HEADERS)
    return jsonify({"status": "connected", "inboxes": [{"id":i["id"],"name":i["name"]} for i in r.json().get("payload",[])]}) if r.status_code == 200 else jsonify({"error": "fail"}), 500

@app.route("/send-email", methods=["POST"])
def send_email():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    d = request.json or {}
    to, subj, body = d.get("to_email"), d.get("subject"), d.get("body")
    if not all([to, subj, body]): return jsonify({"error": "Missing fields"}), 400
    cid = find_or_create_contact(to, d.get("to_name"))
    if not cid: return jsonify({"error": "Contact failed"}), 500
    conv = create_conversation(cid, subj)
    if not conv: return jsonify({"error": "Conv failed"}), 500
    res = send_chatwoot_with_attachments(conv, body, [])
    return jsonify(res) if "error" in res else jsonify({"success": True, "conversation_id": conv})


@app.route("/clickup-webhook", methods=["POST"])
def clickup_webhook():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    text, comment_id = "", ""
    try:
        text = data.get("payload",{}).get("data",{}).get("text_content","")
        comment_id = str(data.get("payload",{}).get("data",{}).get("id",""))
    except: pass
    if not text: return jsonify({"skipped": True, "reason": "No text"}), 200

    print(f"=== BOOKING (comment {comment_id}) len={len(text)} ===", file=sys.stderr)
    if "new booking" not in text.lower(): return jsonify({"skipped": True, "reason": "Not booking"}), 200

    booking = parse_booking(text)
    sp, loc, company = booking.get("space_partner",""), booking.get("location",""), booking.get("company_name","")
    print(f"=== PARSED: co={company} sp={sp} loc={loc} ===", file=sys.stderr)

    if not sp: return jsonify({"skipped": True, "reason": "No SP"}), 200
    if not company or "pending" in company.lower(): return jsonify({"skipped": True, "reason": f"Pending: {company}"}), 200

    vos_key, skip = match_space_partner(sp, loc)
    print(f"=== MATCH: {vos_key} skip={skip} ===", file=sys.stderr)
    if not vos_key: return jsonify({"skipped": True, "reason": f"Not eligible: {skip}"}), 200

    vos = VOS_MAPPING.get(vos_key)
    if not vos or not vos.get("email"): return jsonify({"skipped": True, "reason": f"No email: {vos_key}"}), 200

    # Compose email
    lines = ["Dear Space Partner,", "", "Greetings, we have a Virtual Office booking for your Space.", "",
        f"Company Name - {company}", f"Space Partner - {vos_key}",
        f"Authorized Signatory - {booking.get('signatory','')}", f"Location - {vos['address']}",
        f"Email - {booking.get('email','')}", f"Contact - {booking.get('phone','')}",
        f"Plan - {booking.get('plan','')}",]
    if booking.get("firm_type"): lines.append(f"Entity Type - {booking['firm_type']}")
    if booking.get("nature_of_business"): lines.append(f"Business Description & Nature of Business - {booking['nature_of_business']}")
    lines += ["", "PFA, the required documents, kindly share the Draft Agreement to proceed further.",
        "", "Thanks and Regards,", "Naitik", "Operation Associate", "8368041681"]
    email_body = "\n".join(lines)
    subject = f"Virtual Office Plan - {company}"

    # === FETCH ATTACHMENTS (3 methods) ===
    # Method A: Parse webhook payload directly (fastest)
    att_list = fetch_attachments_from_webhook_payload(data)
    print(f"=== Method A (webhook): {len(att_list)} attachments ===", file=sys.stderr)
    
    # Method B: ClickUp API if webhook had none
    if not att_list and comment_id:
        att_list = fetch_comment_attachments(comment_id)
        print(f"=== Method B (API): {len(att_list)} attachments ===", file=sys.stderr)

    # Download all
    downloaded = []
    for att in att_list:
        content, ct = download_file(att["url"])
        if content:
            downloaded.append({"name": att["name"], "content": content, "content_type": ct or att.get("mime","application/octet-stream")})
            print(f"=== DL OK: {att['name']} ({len(content)}b) ===", file=sys.stderr)
        else:
            print(f"=== DL FAIL: {att['name']} ===", file=sys.stderr)

    print(f"=== SENDING to {vos['email']}, {len(downloaded)}/{len(att_list)} attachments ===", file=sys.stderr)

    cid = find_or_create_contact(vos["email"], vos_key)
    if not cid: return jsonify({"error": f"Contact failed: {vos['email']}"}), 500
    conv = create_conversation(cid, subject)
    if not conv: return jsonify({"error": "Conv failed"}), 500
    result = send_chatwoot_with_attachments(conv, email_body, downloaded)
    print(f"=== CHATWOOT: {json.dumps(result, default=str)[:200]} ===", file=sys.stderr)
    if "error" in result: return jsonify({"error": result}), 500

    return jsonify({"success": True, "to": vos["email"], "subject": subject, "sp": vos_key,
        "conv": conv, "att_sent": len(downloaded), "att_found": len(att_list)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
