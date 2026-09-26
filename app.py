import os, sys, json, re, requests, io, time, gc, base64, threading
from flask import Flask, request, jsonify
try:
    from PIL import Image
    HAS_PIL = True
except:
    HAS_PIL = False
try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMG = True
except:
    HAS_PDF2IMG = False

app = Flask(__name__)
CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "")
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_TEAM_ID = os.environ.get("CLICKUP_TEAM_ID", "1851686")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
HEADERS = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}

SENT_EMAILS = {}
DEDUP_WINDOW = 86400

PAYMENT_NAME_KW = ["payment","amount","token amount","paid","transaction","receipt","invoice","bank statement","account statement","upi","neft","imps","flash space token"]

AMOUNT_STRIP_PATTERNS = [
    r'(?:VO\s*/\s*)?(?:Contract|Registration|Token|Advance|Remaining)\s*(?:Amount|Payment)\s*[:=\-]?\s*[\d,\.]+\s*(?:\+\s*gst|\+\s*GST|\+\s*tax)?\s*',
    r'Payment\s*Date\s*[:=\-]?\s*[\d/\-\.]+\s*',
    r'[\u20b9]\s*[\d,]+\.?\d*\s*(?:\+\s*(?:gst|GST|tax))?\s*',
    r'(?:Rs\.?|INR)\s*[\d,]+\.?\d*\s*(?:\+\s*(?:gst|GST|tax))?\s*',
    r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*\+\s*(?:gst|GST|tax)\b',
]

def sanitize_field(text):
    if not text: return text
    result = text
    for pat in AMOUNT_STRIP_PATTERNS:
        result = re.sub(pat, '', result, flags=re.IGNORECASE)
    result = re.sub(r'[;,\-\s]+$', '', result).strip()
    result = re.sub(r'^[;,\-\s]+', '', result).strip()
    if result != text:
        print(f"=== SANITIZED: '{text}' -> '{result}' ===", file=sys.stderr)
    return result

GEMINI_PROMPT = """Look at this image carefully. Your ONLY job is to classify it.

Is this image a PAYMENT PROOF? Payment proof includes:
- PhonePe/Google Pay/Paytm/BHIM payment screenshot
- UPI transaction confirmation
- Bank transfer confirmation (NEFT/RTGS/IMPS)
- Payment receipt or payment successful screen
- Bank statement showing payment
- Any screenshot showing money was paid/transferred
- QR code payment confirmation

Respond with EXACTLY one word:
- PAYMENT_PROOF (if this is payment/transaction related)
- NOT_PAYMENT (if this is KYC doc like Aadhaar/PAN/GST/agreement/NOC/incorporation certificate/any non-payment document)
- UNCERTAIN (if you cannot determine)

One word only. No explanation."""

def gemini_classify_image(image_bytes, name="?"):
    if not GEMINI_API_KEY:
        print(f"=== GEMINI: no API key, defaulting BLOCK {name} ===", file=sys.stderr)
        return "UNCERTAIN"
    try:
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        mime = "image/jpeg"
        if image_bytes[:4] == b'\x89PNG': mime = "image/png"
        elif image_bytes[:4] == b'RIFF': mime = "image/webp"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": GEMINI_PROMPT},
                    {"inline_data": {"mime_type": mime, "data": b64}}
                ]
            }],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 20}
        }
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"=== GEMINI ERROR ({name}): {r.status_code} {r.text[:200]} ===", file=sys.stderr)
            return "UNCERTAIN"
        resp = r.json()
        # Extract text from all parts (skip thinking parts)
        all_text = ""
        for candidate in resp.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    all_text += part["text"] + " "
        all_text = all_text.strip().upper()
        if "PAYMENT_PROOF" in all_text:
            result = "PAYMENT_PROOF"
        elif "NOT_PAYMENT" in all_text:
            result = "NOT_PAYMENT"
        else:
            result = "UNCERTAIN"
        print(f"=== GEMINI ({name}): {result} (raw: {all_text[:60]}) ===", file=sys.stderr)
        return result
    except Exception as e:
        print(f"=== GEMINI FAIL ({name}): {e} ===", file=sys.stderr)
        return "UNCERTAIN"

def image_to_jpeg_bytes(img, quality=85):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format='JPEG', quality=quality)
    return buf.getvalue()

def should_block_pdf(content, name=""):
    if is_payment_by_name(name):
        print(f"=== BLOCK PDF (name): {name} ===", file=sys.stderr)
        return True
    if not HAS_PDF2IMG:
        print(f"=== PDF no pdf2image, defaulting BLOCK: {name} ===", file=sys.stderr)
        return True
    try:
        images = convert_from_bytes(content, first_page=1, last_page=3, dpi=150, size=(800, None))
        for i, img in enumerate(images):
            jpeg_bytes = image_to_jpeg_bytes(img)
            result = gemini_classify_image(jpeg_bytes, f"{name}_p{i+1}")
            del jpeg_bytes; gc.collect()
            if result in ("PAYMENT_PROOF", "UNCERTAIN"):
                print(f"=== BLOCK PDF (gemini {result}): {name} page {i+1} ===", file=sys.stderr)
                del images; gc.collect()
                return True
        del images; gc.collect()
        print(f"=== ALLOW PDF (gemini): {name} ===", file=sys.stderr)
        return False
    except Exception as e:
        print(f"=== PDF error ({name}): {e}, defaulting BLOCK ===", file=sys.stderr)
        return True

def should_block_image(content, name=""):
    if is_payment_by_name(name):
        print(f"=== BLOCK IMG (name): {name} ===", file=sys.stderr)
        return True
    try:
        if HAS_PIL:
            img = Image.open(io.BytesIO(content))
            img.thumbnail((1200, 1200))
            jpeg_bytes = image_to_jpeg_bytes(img)
            del img; gc.collect()
        else:
            jpeg_bytes = content
    except:
        jpeg_bytes = content
    result = gemini_classify_image(jpeg_bytes, name)
    del jpeg_bytes; gc.collect()
    if result in ("PAYMENT_PROOF", "UNCERTAIN"):
        print(f"=== BLOCK IMG (gemini {result}): {name} ===", file=sys.stderr)
        return True
    print(f"=== ALLOW IMG (gemini): {name} ===", file=sys.stderr)
    return False

def is_payment_by_name(fn):
    return any(kw in fn.lower() for kw in PAYMENT_NAME_KW)

_NONE = "__NONE__"
VOS_MAPPING = {
    "IndiraNagar - Aspire Coworks":{"email":"aspirecoworkings@gmail.com","alternate_email":"booking_in@aspirecoworks.in","address":"17, 7th Main Rd, Indira Nagar II Stage, Hoysala Nagar, Indiranagar, Bengaluru, Karnataka 560038, India"},
    "Koramangala - Aspire Coworks":{"email":"aspirecoworkings@gmail.com","alternate_email":"booking_kmg@aspirecoworks.in","address":"2nd & 3rd Floor, Balaji Arcade, 472/7, 20th L Cross Rd, 4th Block, Koramangala, Bengaluru, Karnataka 560095, India"},
    "EcoSpace - Hebbal, HMT Layout":{"email":"ecospaceblr@gmail.com","address":"No,33, 4th Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India"},
    "Laksh Space - Hebbal, HMT layout":{"email":"Lakshspaceblr@gmail.com","address":"No,33, 1st Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India"},
    "RegisterKaro - Old Airport Road":{"email":"rupeshrai@registerkaro.com","alternate_email":"dipanshusaini@registerkaro.com","address":"Unit 101, Oxford Towers, No. 139 Old Airport Road, Bengaluru-560008"},
    "Getset Spaces - Green Park":{"email":"booking.del@getsetoffice.in","alternate_email":"ekta.mulani@getsetoffice.in","address":"Commercial Complex, 400A, 4th Floor, 12 Ajit Singh House, Yusuf Sarai, Green Park, New Delhi, Delhi 110016"},
    "CP Alt F":{"email":_NONE,"address":"J6JF+53C, Connaught Lane, Barakhamba, New Delhi, Delhi 110001, India"},
    "Mytime Cowork - Saket":{"email":"Sales@mytimeco.work","address":"55 Lane-2, Westend Marg, Saiyad Ul Ajaib Village, Saket, New Delhi, Delhi 110030, India"},
    "Okhla Alt F":{"email":_NONE,"address":"101, NH-19, CRRI, Ishwar Nagar, Okhla, New Delhi, Delhi 110044, India"},
    "WBB Office":{"email":"Info@wbboffice.com","address":"Room no 1 No. 19, Metro Station, 35, Anna Salai, near Little Mount, Little Mount, Nandanam, Chennai, Tamil Nadu 600015, India"},
    "MSB Cospazes":{"email":"msbcospazesofficials@gmail.com","address":"No.26-27-A, H- Block, Third Floor, (Office No.401 & 404) Vikas Marg, Laxmi Nagar, Delhi-110092"},
    "RegisterKaro - Okhla":{"email":"rupeshrai@registerkaro.com","alternate_email":"dipanshusaini@registerkaro.com","address":"808B, DLF Prime Tower, Pocket F, Okhla Phase I, Okhla Industrial Estate, New Delhi, Delhi 110020"},
    "Getset Spaces - Gurgaon":{"email":"booking.ggn@getsetoffice.in","address":"Unit No. 309, 3rd Floor, Tower-A of Eleven Bay (Former SAS Tower), Support Area, Medicity, Sector-38, Gurgaon 122001"},
    "Infrapro - Sector 44":{"email":"nitish@infraprospaces.com","address":"Plot no 4, 2nd floor, Minarch Tower, Sector 44, Gurugram, Haryana 122003, India"},
    "TEAM COWORK - Palm Court":{"email":"virtualoffice@teamco.work","address":"Mehrauli Rd, Gurugram, Haryana 122022, India"},
    "The Work Lounge - Sector 66":{"email":"theworkloungen@gmail.com","address":"02-007, 2nd Floor, Emar The Palm Square, Sector 66, Golf Course Road, Extension, Gurugram, Haryana, 122102"},
    "MSB COspaze - Bhondsi":{"email":"msbcospazesofficials@gmail.com","address":"2nd Floor, Sona Marble Building, Sneh Vihar, Bhondsi, Gurgaon - 122102"},
    "Click Office - Sector 2":{"email":"Hr@clickoffice.in","address":"B-128, B Block, Sector 2, Noida, Uttar Pradesh 201301"},
    "Crystaa - Sector 63":{"email":"crystatower@gmail.com","address":"63m, Ivent, C-030, C Block, Sector 63, Noida, Hazratpur Wajidpur, Uttar Pradesh 201309, India"},
    "Workshala - Sector 3":{"email":"mohitbhargav28@gmail.com","address":"D-9, Vyapar Marg, Block D, Noida Sector 3, Noida, Uttar Pradesh 201301, India"},
    "RegisterKaro - Sector 90":{"email":"rupeshrai@registerkaro.com","alternate_email":"dipanshusaini@registerkaro.com","address":"603 604, FLOOR 6th, TOWER B BHUTANI ALPHATHUM, SECTOR 90, NOIDA, 201305."},
    "Alt F - Sector 62":{"email":_NONE,"address":"C-20, 1/1A, Coast Guard Golf Ground Rd, C Block, Phase 2, Industrial Area, Sector 62, Noida, Uttar Pradesh 201309"},
    "Alt F - Sector 142":{"email":_NONE,"address":"Ground Floor, Plot No. 21 & 21A, Sector 142, Noida, Uttar Pradesh 201304"},
    "Alt F - Sector 58":{"email":_NONE,"address":"A100, A Block, Sector 58, Noida, Uttar Pradesh 201309"},
    "Alt F - Sector 68":{"email":_NONE,"address":"A-5, Grovy Optiva, Block A, Sector 68, Noida, Basi Bahuddin Nagar, Uttar Pradesh 201316"},
    "Mankit Instaspaces":{"email":"naitikkr32@gmail.com","alternate_email":"mankitkr980@gmail.com","address":"Noida, 1 Floor Sector 32 Uttar Pradesh - 110062"},
    "Naitik Get Set Office":{"email":"naitikkr32@gmail.com","address":"648/4 DEVLI VILLAGE BANGALORE - 110062 1 FLOOR"},
}
for _k in VOS_MAPPING:
    if VOS_MAPPING[_k].get("email") == _NONE:
        VOS_MAPPING[_k]["email"] = None

def match_space_partner(sp_text,loc_text):
    sp=sp_text.lower().strip();loc=loc_text.lower().strip();b=sp+" "+loc
    if "stirring" in sp or sp in ("sm","stirringminds"): return None,"DIRECT"
    if "aspire" in sp: return ("Koramangala - Aspire Coworks",None) if "koramangala" in b else ("IndiraNagar - Aspire Coworks",None)
    if "eco" in sp and "space" in sp or "ecospace" in sp.replace(" ",""): return "EcoSpace - Hebbal, HMT Layout",None
    if "laksh" in sp: return "Laksh Space - Hebbal, HMT layout",None
    if "get" in sp and "set" in sp or "getset" in sp.replace(" ",""):
        if any(w in b for w in ["green park","delhi","central"]): return "Getset Spaces - Green Park",None
        if any(w in b for w in ["gurgaon","gurugram","ggn"]): return "Getset Spaces - Gurgaon",None
        if any(w in b for w in ["naitik","test"]): return "Naitik Get Set Office",None
        if "delhi" in loc: return "Getset Spaces - Green Park",None
        if "gurgaon" in loc: return "Getset Spaces - Gurgaon",None
        return "Getset Spaces - Green Park",None
    if "mankit" in sp or "instaspaces" in sp.replace(" ",""): return "Mankit Instaspaces",None
    if "click" in sp and "office" in sp: return "Click Office - Sector 2",None
    if "crysta" in sp: return "Crystaa - Sector 63",None
    if "alt" in sp and "f" in sp:
        if "cp" in b or "connaught" in b: return "CP Alt F",None
        if "okhla" in b: return "Okhla Alt F",None
        for s in ["62","142","58","68"]:
            if s in b: return f"Alt F - Sector {s}",None
        return None,"ALT_F_UNCLEAR"
    if "mytime" in sp: return "Mytime Cowork - Saket",None
    if "wbb" in sp: return "WBB Office",None
    if "msb" in sp: return ("MSB COspaze - Bhondsi",None) if any(w in b for w in ["bhondsi","gurgaon"]) else ("MSB Cospazes",None)
    if "register" in sp and "karo" in sp:
        if "okhla" in b: return "RegisterKaro - Okhla",None
        if any(w in b for w in ["airport","bangalore"]): return "RegisterKaro - Old Airport Road",None
        if any(w in b for w in ["noida","90"]): return "RegisterKaro - Sector 90",None
        return None,"RK_UNCLEAR"
    if "infrapro" in sp: return "Infrapro - Sector 44",None
    if "team" in sp and "cowork" in sp or "palm court" in sp: return "TEAM COWORK - Palm Court",None
    if "work" in sp and "lounge" in sp: return "The Work Lounge - Sector 66",None
    if "workshala" in sp: return "Workshala - Sector 3",None
    return None,"NOT_ELIGIBLE"

def parse_booking(text):
    b={}
    def g(pats):
        for p in pats:
            m=re.search(p,text,re.IGNORECASE)
            if m: return m.group(1).strip()
        return ""
    b["company_name"]=g([r'Company\s*Name\s*[:=\-]\s*\*?\*?\s*(.+?)(?:\n|$)'])
    b["signatory"]=g([r'(?:Director|Authorised Signatory|Authorized Signatory|Proprietor)\s*/?\s*(?:Authorised Signatory)?\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["phone"]=g([r'Phone\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["email"]=g([r'Email\s*[:=\-]\s*\[?([^\]\s\n]+@[^\]\s\n]+)'])
    b["location"]=g([r'Location\s*/?\s*City\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["space_partner"]=g([r'Space\s*Partner\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["firm_type"]=g([r'Firm\s*Type\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["plan"]=g([r'Plan\s*/?\s*Package\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["nature_of_business"]=g([r'Nature\s*of\s*Business\s*[:=\-]\s*(.+?)(?:\n|$)'])
    for k in b: b[k]=re.sub(r'\*+','',b[k]).strip(); b[k]=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',b[k])
    for k in b: b[k] = sanitize_field(b[k])
    return b

def is_duplicate(company, sp_email):
    key = f"{company.lower().strip()}|{sp_email.lower().strip()}"
    now = time.time()
    expired = [k for k,v in SENT_EMAILS.items() if now-v > DEDUP_WINDOW]
    for k in expired: del SENT_EMAILS[k]
    if key in SENT_EMAILS:
        print(f"=== DUPLICATE: {key} ({int(now-SENT_EMAILS[key])}s ago) ===",file=sys.stderr)
        return True
    return False

def mark_sent(company, sp_email):
    key = f"{company.lower().strip()}|{sp_email.lower().strip()}"
    SENT_EMAILS[key] = time.time()

def extract_attachments(data):
    atts=[]; segs=data.get("payload",{}).get("data",{}).get("comment",[]); ic=0
    for seg in segs:
        ao=seg.get("attachment")
        if isinstance(ao,dict) and ao.get("url"):
            nm=ao.get("title",ao.get("name","file"))
            if not is_payment_by_name(nm):
                atts.append({"url":ao["url"],"name":nm,"mime":ao.get("mime_type","application/octet-stream"),"type":"doc","meta":ao})
            else:
                print(f"=== SKIP name: {nm} ===",file=sys.stderr)
        io2=seg.get("image")
        if isinstance(io2,dict) and io2.get("url"):
            ic+=1; ext=io2.get("extension","jpg"); nm=io2.get("title",f"doc_{ic}.{ext}")
            if nm in ("image.jpg","image.jpeg","image.png"): nm=f"doc_{ic}.{ext}"
            if not is_payment_by_name(nm):
                atts.append({"url":io2["url"],"name":nm,"mime":io2.get("mime_type",f"image/{ext}"),"type":"image","meta":io2})
    return atts

def download_and_filter(atts):
    res=[]
    for a in atts:
        try:
            r=requests.get(a["url"],headers={"Authorization":CLICKUP_API_TOKEN},timeout=30,allow_redirects=True)
            if r.status_code!=200 or len(r.content)<50: continue
            c=r.content; ct=r.headers.get("Content-Type",a["mime"])
            is_pdf = "pdf" in ct.lower() or a["name"].lower().endswith(".pdf")
            if is_pdf:
                if should_block_pdf(c, a["name"]): continue
            elif a["type"]=="image":
                if should_block_image(c, a["name"]): continue
            res.append({"name":a["name"],"content":c,"ct":ct})
            print(f"=== OK: {a['name']} ({len(c)}b) ===",file=sys.stderr)
        except Exception as e:
            print(f"=== DL error ({a['name']}): {e} ===", file=sys.stderr)
    return res

def send_chatwoot(conv,content,files,cc_email=None):
    url=f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv}/messages"
    if files:
        ff=[("attachments[]",(f["name"],f["content"],f.get("ct","application/octet-stream"))) for f in files]
        form_data={"content":content,"message_type":"outgoing","content_type":"input_email"}
        if cc_email: form_data["cc_emails"]=cc_email
        r=requests.post(url,headers={"api_access_token":CHATWOOT_TOKEN},data=form_data,files=ff)
    else:
        payload={"content":content,"message_type":"outgoing","content_type":"input_email"}
        if cc_email: payload["cc_emails"]=cc_email
        r=requests.post(url,headers=HEADERS,json=payload)
    print(f"=== CHATWOOT: {r.status_code} ===",file=sys.stderr)
    return r.json() if r.status_code in (200,201) else {"error":r.text}

def auth_check(req):
    t=req.headers.get("X-Service-Secret","") or req.headers.get("Authorization","") or req.args.get("secret","")
    if t.lower().startswith("bearer "): t=t[7:]
    return not SERVICE_SECRET or t==SERVICE_SECRET

def find_or_create_contact(email,name=None):
    r=requests.get(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",headers=HEADERS,params={"q":email})
    for c in r.json().get("payload",[]): 
        if c.get("email","").lower()==email.lower(): return c["id"]
    p={"email":email}
    if name: p["name"]=name
    r=requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts",headers=HEADERS,json=p)
    return r.json().get("payload",{}).get("contact",{}).get("id") if r.status_code in (200,201) else None

def create_conv(cid,subj):
    aa={"mail_subject":subj}
    r=requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations",headers=HEADERS,json={"inbox_id":CHATWOOT_INBOX_ID,"contact_id":cid,"status":"open","additional_attributes":aa})
    return r.json().get("id") if r.status_code in (200,201) else None

def process_booking_async(data):
    """Process booking in background thread (no timeout from ClickUp)."""
    try:
        text=data["payload"]["data"]["text_content"]
        bk=parse_booking(text)
        sp,loc,co=bk.get("space_partner",""),bk.get("location",""),bk.get("company_name","")
        print(f"=== co={co} sp={sp} loc={loc} ===",file=sys.stderr)
        if not sp or not co or "pending" in co.lower(): return
        vk,skip=match_space_partner(sp,loc)
        if not vk: return
        vos=VOS_MAPPING.get(vk)
        if not vos or not vos.get("email"): return
        if is_duplicate(co, vos["email"]): return
        cc_email = vos.get("alternate_email")
        nob = bk.get('nature_of_business','')
        lines=["Dear Space Partner,","","Greetings, we have a Virtual Office booking for your Space.","",f"Company Name - {co}",f"Space Partner - {vk}",f"Authorized Signatory - {bk.get('signatory','')}",f"Location - {vos['address']}",f"Email - {bk.get('email','')}",f"Contact - {bk.get('phone','')}",f"Plan - {bk.get('plan','')}",]
        if bk.get("firm_type"): lines.append(f"Entity Type - {bk['firm_type']}")
        if nob: lines.append(f"Business Description & Nature of Business - {nob}")
        lines+=["\nPFA, the required documents, kindly share the Draft Agreement to proceed further.","\nThanks and Regards,","Naitik","Operation Associate","8368041681"]
        body="\n".join(lines); subj=f"Virtual Office Plan - {co}"
        atts=extract_attachments(data); dls=download_and_filter(atts)
        print(f"=== SEND {vos['email']} CC={cc_email or 'none'}: {len(dls)}/{len(atts)} ===",file=sys.stderr)
        cid=find_or_create_contact(vos["email"],vk)
        if not cid: print(f"=== ERROR: contact creation failed ===",file=sys.stderr); return
        conv=create_conv(cid,subj)
        if not conv: print(f"=== ERROR: conversation creation failed ===",file=sys.stderr); return
        res=send_chatwoot(conv,body,dls,cc_email=cc_email)
        if "error" not in res:
            mark_sent(co, vos["email"])
            print(f"=== DONE: {co} -> {vos['email']} ===",file=sys.stderr)
        else:
            print(f"=== ERROR: chatwoot send failed: {res} ===",file=sys.stderr)
    except Exception as e:
        print(f"=== ASYNC ERROR: {e} ===",file=sys.stderr)

@app.route("/health")
def health(): return jsonify({"v":"12.2","ok":True,"gemini":bool(GEMINI_API_KEY),"pdf2img":HAS_PDF2IMG,"dedup":len(SENT_EMAILS)})

@app.route("/clickup-webhook",methods=["POST"])
def clickup_webhook():
    if not auth_check(request): return jsonify({"error":"auth"}),401
    data=request.json
    if not data: return jsonify({"error":"empty"}),400
    try: text=data["payload"]["data"]["text_content"]
    except: return jsonify({"skip":True}),200
    if "new booking" not in text.lower(): return jsonify({"skip":True}),200
    # Process in background thread to avoid ClickUp 15s timeout
    t = threading.Thread(target=process_booking_async, args=(data,))
    t.start()
    return jsonify({"ok":True,"async":True}),200

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
