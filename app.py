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
    sp = sp_text.lower().strip(); loc = loc_text.lower().strip(); both = sp + " " + loc
    if "stirring" in sp or sp in ("sm", "stirringminds"): return None, "DIRECT_BOOKING"
    if "aspire" in sp: return ("Koramangala - Aspire Coworks", None) if "koramangala" in both else ("IndiraNagar - Aspire Coworks", None)
    if "eco" in sp and "space" in sp or "ecospace" in sp.replace(" ",""): return "EcoSpace - Hebbal, HMT Layout", None
    if "laksh" in sp: return "Laksh Space - Hebbal, HMT layout", None
    if "get" in sp and "set" in sp or "getset" in sp.replace(" ",""):
        if any(w in both for w in ["green park","delhi","central"]): return "Getset Spaces - Green Park", None
        if any(w in both for w in ["gurgaon","gurugram","ggn"]): return "Getset Spaces - Gurgaon", None
        if any(w in both for w in ["naitik","test"]): return "Naitik Get Set Office", None
        if "delhi" in loc: return "Getset Spaces - Green Park", None
        if "gurgaon" in loc or "gurugram" in loc: return "Getset Spaces - Gurgaon", None
        return "Getset Spaces - Green Park", None
    if "click" in sp and "office" in sp: return "Click Office - Sector 2", None
    if "crysta" in sp: return "Crystaa - Sector 63", None
    if "alt" in sp and "f" in sp:
        if "cp" in both or "connaught" in both: return "CP Alt F", None
        if "okhla" in both: return "Okhla Alt F", None
        for s in ["62","142","58","68"]:
            if s in both: return f"Alt F - Sector {s}", None
        return None, "ALT_F_LOCATION_UNCLEAR"
    if "mytime" in sp or "my time" in sp: return "Mytime Cowork - Saket", None
    if "wbb" in sp: return "WBB Office", None
    if "msb" in sp: return ("MSB COspaze - Bhondsi", None) if any(w in both for w in ["bhondsi","gurgaon","gurugram"]) else ("MSB Cospazes", None)
    if "register" in sp and "karo" in sp:
        if "okhla" in both: return "RegisterKaro - Okhla", None
        if any(w in both for w in ["airport","bangalore","bengaluru"]): return "RegisterKaro - Old Airport Road", None
        if any(w in both for w in ["noida","90"]): return "RegisterKaro - Sector 90", None
        return None, "REGISTERKARO_LOCATION_UNCLEAR"
    if "infrapro" in sp: return "Infrapro - Sector 44", None
    if "team" in sp and "cowork" in sp or "palm court" in sp: return "TEAM COWORK - Palm Court", None
    if "work" in sp and "lounge" in sp: return "The Work Lounge - Sector 66", None
    if "workshala" in sp: return "Workshala - Sector 3", None
    return None, "NOT_IN_ELIGIBLE_LIST"

def parse_booking(text):
    b = {}
    def grab(patterns):
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
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
    b["nature_of_business"] = grab([r'Nature\s*of\s*Business\s*[:=\-]\s*(.+?)(?:\n|$)'])
    for k in b:
        b[k] = re.sub(r'\*+', '', b[k]).strip()
        b[k] = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', b[k])
    return b

def is_payment_file(fn): return any(kw in fn.lower() for kw in PAYMENT_KEYWORDS)

def extract_all_attachments(data, comment_id):
    """Extract attachments from webhook payload + ClickUp API. Logs full segment dumps."""
    attachments = []

    # === SOURCE 1: Webhook comment segments ===
    try:
        segs = data.get("payload",{}).get("data",{}).get("comment",[])
        print(f"=== WEBHOOK: {len(segs)} segments ===", file=sys.stderr)
        for i, seg in enumerate(segs):
            attrs = seg.get("attributes",{})
            stype = seg.get("type","")
            text = seg.get("text","")
            # DUMP every segment that has type or non-trivial attrs
            if stype or (attrs and attrs != {} and "block-id" not in str(attrs)):
                print(f"=== WH SEG {i} FULL: {json.dumps(seg)} ===", file=sys.stderr)
            # Check all possible keys
            aid = attrs.get("attachment-id","") or seg.get("attachment-id","") or seg.get("attachmentId","")
            aname = attrs.get("attachment-name","") or seg.get("attachment-name","") or seg.get("attachmentName","")
            imgid = attrs.get("image-id","") or seg.get("image-id","") or seg.get("imageId","")
            # Also check nested 'attachment' object
            att_obj = seg.get("attachment",{}) or attrs.get("attachment",{})
            if isinstance(att_obj, dict):
                aid = aid or att_obj.get("id","") or att_obj.get("attachment_id","")
                aname = aname or att_obj.get("name","") or att_obj.get("title","")
                au = att_obj.get("url","")
                if au and not is_payment_file(aname or "file"):
                    attachments.append({"url":au, "name":aname or "file", "mime":att_obj.get("mimetype","application/octet-stream")})
                    print(f"=== WH SEG {i}: att_obj url={au} name={aname} ===", file=sys.stderr)
            if aid:
                dl = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{aid}"
                if aname and not is_payment_file(aname):
                    attachments.append({"url":dl, "name":aname, "mime":"application/octet-stream"})
                    print(f"=== WH SEG {i}: att_id={aid} name={aname} ===", file=sys.stderr)
            if imgid:
                ext = imgid.split(".")[-1] if "." in imgid else "jpg"
                dl = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{imgid}"
                attachments.append({"url":dl, "name":f"scan_{len(attachments)+1}.{ext}", "mime":f"image/{ext}"})
                print(f"=== WH SEG {i}: img={imgid} ===", file=sys.stderr)
    except Exception as e:
        print(f"=== WH parse err: {e} ===", file=sys.stderr)

    print(f"=== SOURCE 1 RESULT: {len(attachments)} ===", file=sys.stderr)
    if attachments: return attachments

    # === SOURCE 2: ClickUp v2 API ===
    if not CLICKUP_API_TOKEN or not comment_id: return attachments
    url2 = f"https://api.clickup.com/api/v2/view/{DOC_PANEL_VIEW_ID}/comment"
    try:
        r = requests.get(url2, headers=CLICKUP_HEADERS, params={"start_id": str(comment_id)}, timeout=15)
        if r.status_code == 200:
            for c in r.json().get("comments",[]):
                if str(c.get("id")) != str(comment_id): continue
                segs = c.get("comment",[])
                print(f"=== API: {len(segs)} segments for comment {comment_id} ===", file=sys.stderr)
                for i, seg in enumerate(segs):
                    attrs = seg.get("attributes",{})
                    stype = seg.get("type","")
                    if stype or (attrs and attrs != {} and "block-id" not in str(attrs)):
                        print(f"=== API SEG {i} FULL: {json.dumps(seg)} ===", file=sys.stderr)
                    aid = attrs.get("attachment-id","") or seg.get("attachment-id","")
                    aname = attrs.get("attachment-name","") or seg.get("attachment-name","")
                    imgid = attrs.get("image-id","") or seg.get("image-id","")
                    att_obj = seg.get("attachment",{}) or attrs.get("attachment",{})
                    if isinstance(att_obj, dict) and att_obj:
                        aid = aid or att_obj.get("id","")
                        aname = aname or att_obj.get("name","")
                        au = att_obj.get("url","")
                        if au and not is_payment_file(aname or "file"):
                            attachments.append({"url":au, "name":aname or "file", "mime":"application/octet-stream"})
                    if aid:
                        dl = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{aid}"
                        if (aname or stype == "attachment") and not is_payment_file(aname or ""):
                            attachments.append({"url":dl, "name":aname or f"attachment_{len(attachments)+1}", "mime":"application/octet-stream"})
                    if imgid:
                        ext = imgid.split(".")[-1] if "." in imgid else "jpg"
                        dl = f"https://t{CLICKUP_TEAM_ID}.p.clickup-attachments.com/t{CLICKUP_TEAM_ID}/{imgid}"
                        attachments.append({"url":dl, "name":f"scan_{len(attachments)+1}.{ext}", "mime":f"image/{ext}"})
                break
    except Exception as e:
        print(f"=== API err: {e} ===", file=sys.stderr)

    print(f"=== SOURCE 2 RESULT: {len(attachments)} ===", file=sys.stderr)
    return attachments

def download_file(url):
    try:
        r = requests.get(url, headers={"Authorization": CLICKUP_API_TOKEN}, timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 50:
            return r.content, r.headers.get("Content-Type", "application/octet-stream")
        print(f"=== DL {r.status_code} ({len(r.content)}b): {url[:80]} ===", file=sys.stderr)
    except Exception as e:
        print(f"=== DL err: {e} ===", file=sys.stderr)
    return None, None

def send_chatwoot(conv_id, content, files):
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages"
    if files:
        ff = [("attachments[]", (f["name"], f["content"], f.get("ct","application/octet-stream"))) for f in files]
        r = requests.post(url, headers={"api_access_token":CHATWOOT_TOKEN}, data={"content":content,"message_type":"outgoing","content_type":"input_email"}, files=ff)
    else:
        r = requests.post(url, headers=HEADERS, json={"content":content,"message_type":"outgoing","content_type":"input_email"})
    return r.json() if r.status_code in (200,201) else {"error":r.text}

def auth_check(req):
    t = req.headers.get("X-Service-Secret","") or req.headers.get("Authorization","") or req.args.get("secret","")
    if t.lower().startswith("bearer "): t = t[7:]
    return not SERVICE_SECRET or t == SERVICE_SECRET

def find_or_create_contact(email, name=None):
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search", headers=HEADERS, params={"q":email})
    for c in r.json().get("payload",[]): 
        if c.get("email","").lower()==email.lower(): return c["id"]
    p = {"email":email}
    if name: p["name"]=name
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts", headers=HEADERS, json=p)
    return r.json().get("payload",{}).get("contact",{}).get("id") if r.status_code in (200,201) else None

def create_conversation(cid, subj):
    r = requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations", headers=HEADERS,
        json={"inbox_id":CHATWOOT_INBOX_ID,"contact_id":cid,"status":"open","additional_attributes":{"mail_subject":subj}})
    return r.json().get("id") if r.status_code in (200,201) else None

@app.route("/health")
def health(): return jsonify({"status":"ok","v":"5.2-debug"})

@app.route("/test")
def test():
    if not auth_check(request): return jsonify({"error":"Unauthorized"}), 401
    r = requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/inboxes", headers=HEADERS)
    return jsonify({"ok":True}) if r.status_code==200 else jsonify({"error":"fail"}), 500

@app.route("/clickup-webhook", methods=["POST"])
def clickup_webhook():
    if not auth_check(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    if not data: return jsonify({"error":"No data"}), 400
    text = ""; cid = ""
    try: text=data["payload"]["data"]["text_content"]; cid=str(data["payload"]["data"]["id"])
    except: pass
    if not text: return jsonify({"skipped":True}), 200
    if "new booking" not in text.lower(): return jsonify({"skipped":True,"reason":"not booking"}), 200

    booking = parse_booking(text)
    sp,loc,co = booking.get("space_partner",""),booking.get("location",""),booking.get("company_name","")
    print(f"=== BOOKING: co={co} sp={sp} loc={loc} ===", file=sys.stderr)
    if not sp: return jsonify({"skipped":True}), 200
    if not co or "pending" in co.lower(): return jsonify({"skipped":True}), 200

    vk, skip = match_space_partner(sp,loc)
    if not vk: return jsonify({"skipped":True,"reason":skip}), 200
    vos = VOS_MAPPING.get(vk)
    if not vos or not vos.get("email"): return jsonify({"skipped":True}), 200

    lines = ["Dear Space Partner,","","Greetings, we have a Virtual Office booking for your Space.","",
        f"Company Name - {co}",f"Space Partner - {vk}",f"Authorized Signatory - {booking.get('signatory','')}",
        f"Location - {vos['address']}",f"Email - {booking.get('email','')}",f"Contact - {booking.get('phone','')}",
        f"Plan - {booking.get('plan','')}",]
    if booking.get("firm_type"): lines.append(f"Entity Type - {booking['firm_type']}")
    if booking.get("nature_of_business"): lines.append(f"Business Description & Nature of Business - {booking['nature_of_business']}")
    lines += ["","PFA, the required documents, kindly share the Draft Agreement to proceed further.",
        "","Thanks and Regards,","Naitik","Operation Associate","8368041681"]
    body = "\n".join(lines)
    subj = f"Virtual Office Plan - {co}"

    att_list = extract_all_attachments(data, cid)
    print(f"=== TOTAL ATTACHMENTS FOUND: {len(att_list)} ===", file=sys.stderr)

    downloaded = []
    for a in att_list:
        content,ct = download_file(a["url"])
        if content:
            downloaded.append({"name":a["name"],"content":content,"ct":ct or a.get("mime","application/octet-stream")})
            print(f"=== OK: {a['name']} ({len(content)}b) ===", file=sys.stderr)
        else:
            print(f"=== FAIL: {a['name']} ===", file=sys.stderr)

    print(f"=== SENDING {vos['email']}: {len(downloaded)}/{len(att_list)} att ===", file=sys.stderr)
    contact = find_or_create_contact(vos["email"],vk)
    if not contact: return jsonify({"error":"contact"}), 500
    conv = create_conversation(contact,subj)
    if not conv: return jsonify({"error":"conv"}), 500
    res = send_chatwoot(conv,body,downloaded)
    if "error" in res: return jsonify(res), 500
    return jsonify({"ok":True,"to":vos["email"],"att_sent":len(downloaded),"att_found":len(att_list)})

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
