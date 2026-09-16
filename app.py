import os, sys, json, re, requests, base64
from flask import Flask, request, jsonify

app = Flask(__name__)

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "")

HEADERS = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}

# -- VOS Location mapping (eligible Space Partners only) --
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
    if "stirring" in sp or sp in ("sm", "stirringminds"):
        return None, "DIRECT_BOOKING"
    if "aspire" in sp:
        if "koramangala" in both: return "Koramangala - Aspire Coworks", None
        return "IndiraNagar - Aspire Coworks", None
    if "eco" in sp and "space" in sp or "ecospace" in sp.replace(" ",""):
        return "EcoSpace - Hebbal, HMT Layout", None
    if "laksh" in sp:
        return "Laksh Space - Hebbal, HMT layout", None
    if "get" in sp and "set" in sp or "getset" in sp.replace(" ",""):
        if any(w in both for w in ["green park", "delhi", "central"]): return "Getset Spaces - Green Park", None
        if any(w in both for w in ["gurgaon", "gurugram", "ggn"]): return "Getset Spaces - Gurgaon", None
        if any(w in both for w in ["naitik", "test"]): return "Naitik Get Set Office", None
        if any(w in loc for w in ["delhi"]): return "Getset Spaces - Green Park", None
        if any(w in loc for w in ["gurgaon", "gurugram"]): return "Getset Spaces - Gurgaon", None
        return "Getset Spaces - Green Park", None
    if "click" in sp and "office" in sp:
        return "Click Office - Sector 2", None
    if "crysta" in sp:
        return "Crystaa - Sector 63", None
    if "alt" in sp and "f" in sp:
        if "cp" in both or "connaught" in both: return "CP Alt F", None
        if "okhla" in both: return "Okhla Alt F", None
        if "62" in both: return "Alt F - Sector 62", None
        if "142" in both: return "Alt F - Sector 142", None
        if "58" in both: return "Alt F - Sector 58", None
        if "68" in both: return "Alt F - Sector 68", None
        return None, "ALT_F_LOCATION_UNCLEAR"
    if "mytime" in sp or "my time" in sp:
        return "Mytime Cowork - Saket", None
    if "wbb" in sp:
        return "WBB Office", None
    if "msb" in sp:
        if any(w in both for w in ["bhondsi", "gurgaon", "gurugram"]): return "MSB COspaze - Bhondsi", None
        return "MSB Cospazes", None
    if "register" in sp and "karo" in sp:
        if any(w in both for w in ["okhla"]): return "RegisterKaro - Okhla", None
        if any(w in both for w in ["airport", "bangalore", "bengaluru"]): return "RegisterKaro - Old Airport Road", None
        if any(w in both for w in ["noida", "90", "sector 90"]): return "RegisterKaro - Sector 90", None
        return None, "REGISTERKARO_LOCATION_UNCLEAR"
    if "infrapro" in sp:
        return "Infrapro - Sector 44", None
    if "team" in sp and ("cowork" in sp or "co work" in sp) or "palm court" in sp:
        return "TEAM COWORK - Palm Court", None
    if "work" in sp and "lounge" in sp:
        return "The Work Lounge - Sector 66", None
    if "workshala" in sp:
        return "Workshala - Sector 3", None
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
    payload = {"inbox_id": CHATWOOT_INBOX_ID, "contact_id": contact_id, "status": "open", "additional_attributes": {"mail_subject": subject}}
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations", headers=HEADERS, json=payload)
    return r.json().get("id") if r.status_code in (200,201) else None

def send_chatwoot_message(conversation_id, content):
    payload = {"content": content, "message_type": "outgoing", "content_type": "input_email"}
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages", headers=HEADERS, json=payload)
    return r.json() if r.status_code in (200,201) else {"error": r.text}


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "chatwoot-bridge-v3"})

@app.route("/test")
def test():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/inboxes", headers=HEADERS)
    if r.status_code == 200:
        return jsonify({"status": "connected", "inboxes": [{"id":i["id"],"name":i["name"]} for i in r.json().get("payload",[])]})
    return jsonify({"status": "error"}), 500

@app.route("/send-email", methods=["POST"])
def send_email():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    d = request.json or {}
    to, subj, body = d.get("to_email"), d.get("subject"), d.get("body")
    if not all([to, subj, body]): return jsonify({"error": "Missing fields"}), 400
    cid = find_or_create_contact(to, d.get("to_name"))
    if not cid: return jsonify({"error": "Contact creation failed"}), 500
    conv = create_conversation(cid, subj)
    if not conv: return jsonify({"error": "Conversation creation failed"}), 500
    res = send_chatwoot_message(conv, body)
    if "error" in res: return jsonify(res), 500
    return jsonify({"success": True, "conversation_id": conv})


@app.route("/clickup-webhook", methods=["POST"])
def clickup_webhook():
    if not auth_check(request): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    if not data: return jsonify({"error": "No data"}), 400

    text = ""
    try: text = data.get("payload",{}).get("data",{}).get("text_content","")
    except: pass
    if not text:
        return jsonify({"skipped": True, "reason": "No text_content"}), 200

    print(f"=== BOOKING TEXT ===\n{text[:500]}\n=== END ===", file=sys.stderr)

    if "new booking" not in text.lower():
        return jsonify({"skipped": True, "reason": "Not a new booking message"}), 200

    booking = parse_booking(text)
    print(f"=== PARSED BOOKING: {json.dumps(booking)} ===", file=sys.stderr)

    sp = booking.get("space_partner","")
    loc = booking.get("location","")
    company = booking.get("company_name","")

    if not sp:
        return jsonify({"skipped": True, "reason": "No Space Partner found"}), 200
    if not company or "pending" in company.lower():
        return jsonify({"skipped": True, "reason": f"Company pending: {company}"}), 200

    vos_key, skip_reason = match_space_partner(sp, loc)
    print(f"=== MATCH: sp='{sp}' loc='{loc}' -> vos='{vos_key}' skip='{skip_reason}' ===", file=sys.stderr)

    if not vos_key:
        return jsonify({"skipped": True, "reason": f"Not eligible: {skip_reason}", "sp": sp}), 200

    vos = VOS_MAPPING.get(vos_key)
    if not vos or not vos.get("email"):
        return jsonify({"skipped": True, "reason": f"No email for {vos_key}"}), 200

    lines = [
        "Dear Space Partner,",
        "",
        "Greetings, we have a Virtual Office booking for your Space.",
        "",
        f"Company Name - {company}",
        f"Space Partner - {vos_key}",
        f"Authorized Signatory - {booking.get('signatory','')}",
        f"Location - {vos['address']}",
        f"Email - {booking.get('email','')}",
        f"Contact - {booking.get('phone','')}",
        f"Plan - {booking.get('plan','')}",
    ]
    ft = booking.get("firm_type","")
    if ft: lines.append(f"Entity Type - {ft}")
    nb = booking.get("nature_of_business","")
    if nb: lines.append(f"Business Description & Nature of Business - {nb}")
    lines += [
        "",
        "PFA, the required documents, kindly share the Draft Agreement to proceed further.",
        "",
        "Thanks and Regards,",
        "Naitik",
        "Operation Associate",
        "8368041681",
    ]
    email_body = "\n".join(lines)
    subject = f"Virtual Office Plan - {company}"

    print(f"=== SENDING to {vos['email']}, subj: {subject} ===", file=sys.stderr)

    contact_id = find_or_create_contact(vos["email"], vos_key)
    if not contact_id:
        return jsonify({"error": f"Contact failed for {vos['email']}"}), 500

    conv_id = create_conversation(contact_id, subject)
    if not conv_id:
        return jsonify({"error": "Conversation failed"}), 500

    result = send_chatwoot_message(conv_id, email_body)
    print(f"=== CHATWOOT: {json.dumps(result, default=str)[:300]} ===", file=sys.stderr)

    if "error" in result:
        return jsonify({"error": result}), 500

    return jsonify({"success": True, "to": vos["email"], "subject": subject, "space_partner": vos_key, "conversation_id": conv_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
