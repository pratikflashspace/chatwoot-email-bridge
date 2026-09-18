import os, sys, json, re, requests, io, time
from flask import Flask, request, jsonify
try:
    from PyPDF2 import PdfReader
except: PdfReader = None
try:
    from PIL import Image
    HAS_PIL = True
except:
    HAS_PIL = False

app = Flask(__name__)

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
SERVICE_SECRET = os.environ.get("SERVICE_SECRET", "")
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_TEAM_ID = os.environ.get("CLICKUP_TEAM_ID", "1851686")

HEADERS = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
MAX_PDF_SCAN = 3*1024*1024

PAYMENT_NAME_KW = ["payment","amount","token amount","paid","transaction","receipt","invoice",
    "bank statement","account statement","upi","neft","imps","flash space token"]
PAYMENT_CONTENT_KW = ["payment successful","transaction id","transaction ref","utr no","utr:",
    "upi ref","upi id","paid to","paid via","amount paid","total paid","razorpay","phonepe",
    "google pay","paytm","bhim","bank transfer","neft ref","imps ref","credited","debited",
    "account statement","bank statement","payment receipt","invoice amount",
    "amount received","payment confirmation","order id","payment id",
    "money transfer","fund transfer","transaction successful","txn id",
    "amount debited","amount credited","net banking","total amount"]
KYC_KEYWORDS = ["aadhaar","aadhar","pan card","permanent account number","income tax",
    "election commission","voter id","passport","driving licence","driving license",
    "identity card","uid","unique identification","govt of india","government of india",
    "ministry of","certificate of incorporation","memorandum","articles of association",
    "gst certificate","gstin","registration certificate","company pan"]

VOS_MAPPING = {
    "IndiraNagar - Aspire Coworks":{"email":"aspirecoworkings@gmail.com","address":"17, 7th Main Rd, Indira Nagar II Stage, Hoysala Nagar, Indiranagar, Bengaluru, Karnataka 560038, India"},
    "Koramangala - Aspire Coworks":{"email":"aspirecoworkings@gmail.com","address":"2nd & 3rd Floor, Balaji Arcade, 472/7, 20th L Cross Rd, 4th Block, Koramangala, Bengaluru, Karnataka 560095, India"},
    "EcoSpace - Hebbal, HMT Layout":{"email":"ecospaceblr@gmail.com","address":"No,33, 4th Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India"},
    "Laksh Space - Hebbal, HMT layout":{"email":"Lakshspaceblr@gmail.com","address":"No,33, 1st Floor, 1st Main, CBI Main Rd, HMT Layout, Ganganagar, Bengaluru, Karnataka 560032, India"},
    "RegisterKaro - Old Airport Road":{"email":"rupeshrai@registerkaro.com","address":"Unit 101, Oxford Towers, No. 139 Old Airport Road, Bengaluru-560008"},
    "Getset Spaces - Green Park":{"email":"booking.del@getsetoffice.in","address":"Commercial Complex, 400A, 4th Floor, 12 Ajit Singh House, Yusuf Sarai, Green Park, New Delhi, Delhi 110016"},
    "CP Alt F":{"email":None,"address":"J6JF+53C, Connaught Lane, Barakhamba, New Delhi, Delhi 110001, India"},
    "Mytime Cowork - Saket":{"email":"Sales@mytimeco.work","address":"55 Lane-2, Westend Marg, Saiyad Ul Ajaib Village, Saket, New Delhi, Delhi 110030, India"},
    "Okhla Alt F":{"email":None,"address":"101, NH-19, CRRI, Ishwar Nagar, Okhla, New Delhi, Delhi 110044, India"},
    "WBB Office":{"email":"Info@wbboffice.com","address":"Room no 1 No. 19, Metro Station, 35, Anna Salai, near Little Mount, Little Mount, Nandanam, Chennai, Tamil Nadu 600015, India"},
    "MSB Cospazes":{"email":"msbcospazesofficials@gmail.com","address":"No.26-27-A, H- Block, Third Floor, (Office No.401 & 404) Vikas Marg, Laxmi Nagar, Delhi-110092"},
    "RegisterKaro - Okhla":{"email":"rupeshrai@registerkaro.com","address":"808B, DLF Prime Tower, Pocket F, Okhla Phase I, Okhla Industrial Estate, New Delhi, Delhi 110020"},
    "Getset Spaces - Gurgaon":{"email":"booking.ggn@getsetoffice.in","address":"Unit No. 309, 3rd Floor, Tower-A of Eleven Bay (Former SAS Tower), Support Area, Medicity, Sector-38, Gurgaon 122001"},
    "Infrapro - Sector 44":{"email":"nitish@infraprospaces.com","address":"Plot no 4, 2nd floor, Minarch Tower, Sector 44, Gurugram, Haryana 122003, India"},
    "TEAM COWORK - Palm Court":{"email":"virtualoffice@teamco.work","address":"Mehrauli Rd, Gurugram, Haryana 122022, India"},
    "The Work Lounge - Sector 66":{"email":"theworkloungen@gmail.com","address":"02-007, 2nd Floor, Emar The Palm Square, Sector 66, Golf Course Road, Extension, Gurugram, Haryana, 122102"},
    "MSB COspaze - Bhondsi":{"email":"msbcospazesofficials@gmail.com","address":"2nd Floor, Sona Marble Building, Sneh Vihar, Bhondsi, Gurgaon - 122102"},
    "Click Office - Sector 2":{"email":"Hr@clickoffice.in","address":"B-128, B Block, Sector 2, Noida, Uttar Pradesh 201301"},
    "Crystaa - Sector 63":{"email":"crystatower@gmail.com","address":"63m, Ivent, C-030, C Block, Sector 63, Noida, Hazratpur Wajidpur, Uttar Pradesh 201309, India"},
    "Workshala - Sector 3":{"email":"mohitbhargav28@gmail.com","address":"D-9, Vyapar Marg, Block D, Noida Sector 3, Noida, Uttar Pradesh 201301, India"},
    "RegisterKaro - Sector 90":{"email":"rupeshrai@registerkaro.com","address":"603 604, FLOOR 6th, TOWER B BHUTANI ALPHATHUM, SECTOR 90, NOIDA, 201305."},
    "Alt F - Sector 62":{"email":None,"address":"C-20, 1/1A, Coast Guard Golf Ground Rd, C Block, Phase 2, Industrial Area, Sector 62, Noida, Uttar Pradesh 201309"},
    "Alt F - Sector 142":{"email":None,"address":"Ground Floor, Plot No. 21 & 21A, Sector 142, Noida, Uttar Pradesh 201304"},
    "Alt F - Sector 58":{"email":None,"address":"A100, A Block, Sector 58, Noida, Uttar Pradesh 201309"},
    "Alt F - Sector 68":{"email":None,"address":"A-5, Grovy Optiva, Block A, Sector 68, Noida, Basi Bahuddin Nagar, Uttar Pradesh 201316"},
    "Naitik Get Set Office":{"email":"naitikkr32@gmail.com","address":"648/4 DEVLI VILLAGE BANGALORE - 110062 1 FLOOR"},
}

def match_space_partner(sp_text, loc_text):
    sp=sp_text.lower().strip(); loc=loc_text.lower().strip(); b=sp+" "+loc
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
    b["signatory"]=g([r'(?:Director|Authorised Signatory|Authorized Signatory)\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["phone"]=g([r'Phone\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["email"]=g([r'Email\s*[:=\-]\s*\[?([^\]\s\n]+@[^\]\s\n]+)'])
    b["location"]=g([r'Location\s*/?\s*City\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["space_partner"]=g([r'Space\s*Partner\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["firm_type"]=g([r'Firm\s*Type\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["plan"]=g([r'Plan\s*/?\s*Package\s*[:=\-]\s*(.+?)(?:\n|$)'])
    b["nature_of_business"]=g([r'Nature\s*of\s*Business\s*[:=\-]\s*(.+?)(?:\n|$)'])
    for k in b: b[k]=re.sub(r'\*+','',b[k]).strip(); b[k]=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',b[k])
    return b

def is_payment_by_name(fn): return any(kw in fn.lower() for kw in PAYMENT_NAME_KW)

def check_text_for_payment(text):
    t=text.lower()
    for kw in KYC_KEYWORDS:
        if kw in t: return False
    for kw in PAYMENT_CONTENT_KW:
        if kw in t: return True
    return False

def is_payment_pdf(content):
    if not PdfReader or len(content)>MAX_PDF_SCAN: return False
    try:
        reader=PdfReader(io.BytesIO(content))
        text=""
        for page in reader.pages[:2]:
            try:
                t=page.extract_text()
                if t: text+=t+" "
            except: pass
        if not text.strip(): return False
        r=check_text_for_payment(text)
        if r: print(f"=== PAYMENT PDF ===",file=sys.stderr)
        return r
    except Exception as e:
        print(f"=== PDF err: {e} ===",file=sys.stderr)
    return False

def is_payment_image(content, img_meta=None):
    """Detect payment screenshots using aspect ratio + green color analysis.
    Payment screenshots (Google Pay, PhonePe, Paytm): tall phone screens with green success indicators.
    KYC docs (PAN, Aadhaar): landscape cards or standard document shapes."""
    score = 0
    w = int(img_meta.get("width",0)) if img_meta else 0
    h = int(img_meta.get("height",0)) if img_meta else 0
    
    # Check 1: Aspect ratio from metadata (no download needed for this check)
    if w > 0 and h > 0:
        ratio = h / w
        # Phone screenshots: very tall (ratio > 1.7), typically 9:16 or taller
        if ratio > 1.7:
            score += 2
            print(f"=== IMG ratio {ratio:.1f} ({w}x{h}): phone-like (+2) ===", file=sys.stderr)
        # Document/card shaped (landscape or mild portrait): likely KYC
        elif ratio < 1.2:
            score -= 3  # Very likely a card/document
            print(f"=== IMG ratio {ratio:.1f} ({w}x{h}): card-like (-3) ===", file=sys.stderr)
    
    # Check 2: Green color analysis (payment apps use green for success)
    if HAS_PIL and content:
        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            img.thumbnail((200, 200))  # Tiny for fast analysis
            pixels = list(img.getdata())
            total = len(pixels)
            if total > 0:
                # Count green-dominant pixels (G > R*1.3 and G > B*1.3 and G > 80)
                green_count = sum(1 for r,g,b in pixels if g > r*1.3 and g > b*1.3 and g > 80)
                green_pct = green_count / total * 100
                # Count white pixels (all > 220) - payment screens often have white backgrounds
                white_count = sum(1 for r,g,b in pixels if r>220 and g>220 and b>220)
                white_pct = white_count / total * 100
                
                if green_pct > 8:  # More than 8% green
                    score += 2
                    print(f"=== IMG green={green_pct:.1f}% (+2) ===", file=sys.stderr)
                if green_pct > 15:  # Very green
                    score += 1
                    print(f"=== IMG very green={green_pct:.1f}% (+1) ===", file=sys.stderr)
                    
                # Blue tint (PAN card is blue, Aadhaar has blue elements)
                blue_count = sum(1 for r,g,b in pixels if b > r*1.2 and b > g*1.1 and b > 80)
                blue_pct = blue_count / total * 100
                if blue_pct > 10:  # Blue dominant = likely KYC
                    score -= 2
                    print(f"=== IMG blue={blue_pct:.1f}% (-2, KYC likely) ===", file=sys.stderr)
                
                print(f"=== IMG colors: green={green_pct:.1f}% blue={blue_pct:.1f}% white={white_pct:.1f}% score={score} ===", file=sys.stderr)
        except Exception as e:
            print(f"=== IMG analysis err: {e} ===", file=sys.stderr)
    
    # Score >= 3 = payment, score < 3 = keep as document
    is_pay = score >= 3
    if is_pay: print(f"=== PAYMENT IMAGE (score={score}) ===", file=sys.stderr)
    return is_pay

def extract_attachments(data):
    atts=[]
    try:
        segs=data.get("payload",{}).get("data",{}).get("comment",[])
        img_count=0
        for seg in segs:
            att_obj=seg.get("attachment")
            if isinstance(att_obj,dict) and att_obj.get("url"):
                name=att_obj.get("title",att_obj.get("name","file"))
                if not is_payment_by_name(name):
                    atts.append({"url":att_obj["url"],"name":name,"mime":att_obj.get("mime_type","application/octet-stream"),"type":"doc","meta":att_obj})
                else:
                    print(f"=== SKIP (name): {name} ===",file=sys.stderr)
            img_obj=seg.get("image")
            if isinstance(img_obj,dict) and img_obj.get("url"):
                img_count+=1
                ext=img_obj.get("extension","jpg")
                name=img_obj.get("title",f"document_{img_count}.{ext}")
                if name in ("image.jpg","image.jpeg","image.png"): name=f"document_{img_count}.{ext}"
                if not is_payment_by_name(name):
                    atts.append({"url":img_obj["url"],"name":name,"mime":img_obj.get("mime_type",f"image/{ext}"),"type":"image","meta":img_obj})
                else:
                    print(f"=== SKIP IMG (name): {name} ===",file=sys.stderr)
    except Exception as e:
        print(f"=== Extract err: {e} ===",file=sys.stderr)
    print(f"=== EXTRACTED: {len(atts)} ===",file=sys.stderr)
    return atts

def download_and_filter(atts):
    result=[]
    for a in atts:
        try:
            r=requests.get(a["url"],headers={"Authorization":CLICKUP_API_TOKEN},timeout=30,allow_redirects=True)
            if r.status_code!=200 or len(r.content)<50:
                print(f"=== DL FAIL: {a['name']} ===",file=sys.stderr); continue
            content=r.content; ct=r.headers.get("Content-Type",a["mime"])
            # PDF: read text to check
            if "pdf" in ct.lower() or a["name"].lower().endswith(".pdf"):
                if is_payment_pdf(content):
                    print(f"=== SKIP PDF: {a['name']} ===",file=sys.stderr); continue
            # Image: use aspect ratio + color analysis
            elif a["type"]=="image":
                if is_payment_image(content, a.get("meta",{})):
                    print(f"=== SKIP IMG: {a['name']} ===",file=sys.stderr); continue
            result.append({"name":a["name"],"content":content,"ct":ct})
            print(f"=== OK: {a['name']} ({len(content)}b) ===",file=sys.stderr)
        except Exception as e:
            print(f"=== err {a['name']}: {e} ===",file=sys.stderr)
    return result

def send_chatwoot(conv,content,files):
    url=f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv}/messages"
    if files:
        ff=[("attachments[]",(f["name"],f["content"],f.get("ct","application/octet-stream"))) for f in files]
        r=requests.post(url,headers={"api_access_token":CHATWOOT_TOKEN},data={"content":content,"message_type":"outgoing","content_type":"input_email"},files=ff)
    else:
        r=requests.post(url,headers=HEADERS,json={"content":content,"message_type":"outgoing","content_type":"input_email"})
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
    r=requests.post(f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations",headers=HEADERS,
        json={"inbox_id":CHATWOOT_INBOX_ID,"contact_id":cid,"status":"open","additional_attributes":{"mail_subject":subj}})
    return r.json().get("id") if r.status_code in (200,201) else None

@app.route("/health")
def health(): return jsonify({"v":"9.0","ok":True,"pdf":"yes" if PdfReader else "no","pil":"yes" if HAS_PIL else "no"})

@app.route("/clickup-webhook",methods=["POST"])
def clickup_webhook():
    if not auth_check(request): return jsonify({"error":"auth"}),401
    data=request.json
    if not data: return jsonify({"error":"empty"}),400
    try: text=data["payload"]["data"]["text_content"]
    except: return jsonify({"skip":True}),200
    if "new booking" not in text.lower(): return jsonify({"skip":True}),200

    bk=parse_booking(text)
    sp,loc,co=bk.get("space_partner",""),bk.get("location",""),bk.get("company_name","")
    print(f"=== co={co} sp={sp} loc={loc} ===",file=sys.stderr)
    if not sp or not co or "pending" in co.lower(): return jsonify({"skip":True}),200

    vk,skip=match_space_partner(sp,loc)
    if not vk: return jsonify({"skip":True,"r":skip}),200
    vos=VOS_MAPPING.get(vk)
    if not vos or not vos.get("email"): return jsonify({"skip":True}),200

    lines=["Dear Space Partner,","","Greetings, we have a Virtual Office booking for your Space.","",
        f"Company Name - {co}",f"Space Partner - {vk}",f"Authorized Signatory - {bk.get('signatory','')}",
        f"Location - {vos['address']}",f"Email - {bk.get('email','')}",f"Contact - {bk.get('phone','')}",
        f"Plan - {bk.get('plan','')}",]
    if bk.get("firm_type"): lines.append(f"Entity Type - {bk['firm_type']}")
    if bk.get("nature_of_business"): lines.append(f"Business Description & Nature of Business - {bk['nature_of_business']}")
    lines+=["\nPFA, the required documents, kindly share the Draft Agreement to proceed further.",
        "\nThanks and Regards,","Naitik","Operation Associate","8368041681"]
    body="\n".join(lines)
    subj=f"Virtual Office Plan - {co}"

    atts=extract_attachments(data)
    dls=download_and_filter(atts)

    print(f"=== SEND {vos['email']}: {len(dls)}/{len(atts)} ===",file=sys.stderr)
    cid=find_or_create_contact(vos["email"],vk)
    if not cid: return jsonify({"error":"contact"}),500
    conv=create_conv(cid,subj)
    if not conv: return jsonify({"error":"conv"}),500
    res=send_chatwoot(conv,body,dls)
    if "error" in res: return jsonify(res),500
    return jsonify({"ok":True,"to":vos["email"],"sent":len(dls),"found":len(atts)})

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
