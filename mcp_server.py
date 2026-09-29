"""
Chatwoot MCP Server v2.3
Expose attachment metadata and fail closed before sending if any download fails.
"""
import os, json, httpx, ipaddress, socket, asyncio
from urllib.parse import urlsplit, urljoin, unquote
from email.message import Message
from mcp.server.mcpserver import MCPServer

CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "https://support.stirringminds.com")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
PORT = int(os.environ.get("PORT", 10000))
mcp = MCPServer("Chatwoot")

def _headers():
    return {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}

def _guess_ext(ct):
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "application/pdf": ".pdf", "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    return mapping.get(ct.split(";")[0].strip().lower(), "")

def _clean_filename(name, ct):
    name = str(name or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ord(ch) >= 32 and ord(ch) != 127)
    if not name or name in ("file", ".", ".."):
        return "document" + _guess_ext(ct)
    if "." not in name:
        name += _guess_ext(ct)
    return name

def _download_filename(response, original_url, ct):
    msg = Message()
    msg["Content-Disposition"] = response.headers.get("content-disposition", "")
    name = msg.get_filename()
    if not name:
        name = unquote(urlsplit(str(response.url or original_url)).path.rsplit("/", 1)[-1])
    return _clean_filename(name, ct)

async def _validate_download_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Attachment URL must be public HTTPS without embedded credentials")
    if parsed.port not in (None, 443):
        raise ValueError("Attachment URL must use the HTTPS port")
    infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not infos or any(not ipaddress.ip_address(info[4][0]).is_global for info in infos):
        raise ValueError("Attachment URL must resolve to public addresses")
    return parsed

async def _download_attachment(client, url):
    current = url
    for _ in range(6):
        parsed = await _validate_download_url(current)
        # Never disclose ClickUp credentials to Chatwoot, storage, or redirect hosts.
        headers = {}
        if parsed.hostname == "api.clickup.com" and CLICKUP_API_TOKEN:
            headers["Authorization"] = CLICKUP_API_TOKEN
        response = await client.get(current, headers=headers, follow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                raise ValueError("Attachment redirect has no destination")
            current = urljoin(current, location)
            continue
        if response.status_code != 200:
            raise ValueError(f"Attachment download returned HTTP {response.status_code}")
        if not response.content:
            raise ValueError("Attachment download was empty")
        ct = response.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
        if ct in ("text/html", "application/xhtml+xml"):
            raise ValueError("Attachment download returned an HTML page, not a verified file")
        return {"name": _download_filename(response, url, ct), "content": response.content, "ct": ct}
    raise ValueError("Too many attachment redirects")

@mcp.tool()
async def find_or_create_contact(email: str, name: str = "") -> str:
    """Find an existing Chatwoot contact by email, or create a new one."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",
            headers=_headers(), params={"q": email},
        )
        for ct in r.json().get("payload", []):
            if ct.get("email", "").lower() == email.lower():
                return json.dumps({"contact_id": ct["id"], "name": ct.get("name", ""), "created": False})
        payload = {"email": email}
        if name:
            payload["name"] = name
        r = await c.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts",
            headers=_headers(), json=payload,
        )
        if r.status_code in (200, 201):
            cid = r.json().get("payload", {}).get("contact", {}).get("id")
            return json.dumps({"contact_id": cid, "name": name, "created": True})
        return json.dumps({"error": f"Create failed: {r.status_code} {r.text[:200]}"})

@mcp.tool()
async def create_email_conversation(contact_id: int, subject: str) -> str:
    """Create a new outbound email conversation in Chatwoot."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations",
            headers=_headers(),
            json={
                "inbox_id": CHATWOOT_INBOX_ID,
                "contact_id": contact_id,
                "status": "open",
                "additional_attributes": {"mail_subject": subject},
            },
        )
        if r.status_code in (200, 201):
            return json.dumps({"conversation_id": r.json().get("id"), "subject": subject})
        return json.dumps({"error": f"Create failed: {r.status_code} {r.text[:200]}"})

@mcp.tool()
async def send_email(conversation_id: int, body: str, cc_email: str = "", attachment_urls: str = "[]") -> str:
    """Send an outgoing email. attachment_urls is a JSON array of HTTPS URLs.
    All requested attachments must download successfully before any email is posted.
    On an uncertain POST result, inspect conversation history before retrying.
    """
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"
    try:
        urls = json.loads(attachment_urls) if isinstance(attachment_urls, str) else attachment_urls
        if not isinstance(urls, list) or any(not isinstance(u, str) or not u.strip() for u in urls):
            raise ValueError("Expected a JSON array of nonempty attachment URLs")
    except (ValueError, TypeError):
        return json.dumps({"sent": False, "error": "Invalid attachment_urls: expected a JSON array of URLs"})
    files = []
    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as c:
        for index, att_url in enumerate(urls):
            try:
                files.append(await _download_attachment(c, att_url))
            except Exception:
                return json.dumps({
                    "sent": False, "error": "Attachment download failed; no email was posted",
                    "failed_attachment_index": index, "expected_attachments": len(urls),
                    "downloaded_attachments": len(files),
                })
    async with httpx.AsyncClient(timeout=60) as c:
        try:
            if files:
                form = {"content": body, "message_type": "outgoing"}
                if cc_email:
                    form["cc_emails"] = cc_email
                mf = [("attachments[]", (f["name"], f["content"], f["ct"])) for f in files]
                r = await c.post(url, headers={"api_access_token": CHATWOOT_TOKEN}, data=form, files=mf)
            else:
                payload = {"content": body, "message_type": "outgoing"}
                if cc_email:
                    payload["cc_emails"] = cc_email
                r = await c.post(url, headers=_headers(), json=payload)
        except httpx.HTTPError:
            return json.dumps({"sent": None, "error": "Email submission outcome unknown; check conversation before retrying"})
        if r.status_code in (200, 201):
            try:
                result = r.json()
            except ValueError:
                result = {}
            return json.dumps({
                "sent": True, "accepted": True, "delivery_confirmed": False,
                "message_id": result.get("id"), "status": result.get("status"),
                "attachments_count": len(files), "filenames": [f["name"] for f in files],
                "server_attachments_count": len(result.get("attachments") or []),
            })
        return json.dumps({"sent": None, "error": f"Email submission returned HTTP {r.status_code}; check conversation before retrying"})

@mcp.tool()
async def get_conversation_messages(conversation_id: int, before: int = 0) -> str:
    """Get a page of messages with full content and downloadable attachment_details.
    The legacy attachments field remains a count. Use before=min(message IDs) for older pages.
    Attachment names may be inferred from URLs; verify downloaded files before forwarding.
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
            headers=_headers(), params={"before": before} if before else {},
        )
        if r.status_code == 200:
            output = []
            for m in r.json().get("payload", []):
                details = []
                for attachment in m.get("attachments") or []:
                    a = dict(attachment)
                    download_url = a.get("data_url") or a.get("download_url") or a.get("url")
                    a["download_url"] = download_url
                    a["filename"] = a.get("file_name") or a.get("filename") or a.get("name")
                    if not a["filename"] and download_url:
                        a["filename"] = unquote(urlsplit(download_url).path.rsplit("/", 1)[-1])
                        a["filename_inferred_from_url"] = True
                    details.append(a)
                output.append({
                    "id": m.get("id"), "content": m.get("content") or "",
                    "type": m.get("message_type"), "sender": (m.get("sender") or {}).get("name", ""),
                    "sender_email": (m.get("sender") or {}).get("email"),
                    "created_at": m.get("created_at"), "private": m.get("private"),
                    "status": m.get("status"), "content_attributes": m.get("content_attributes"),
                    "attachments": len(details), "attachment_details": details,
                })
            return json.dumps(output)
        return json.dumps({"error": f"Failed: {r.status_code}"})

@mcp.tool()
async def list_contact_conversations(email: str) -> str:
    """List Chatwoot conversations for a contact email."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",
            headers=_headers(), params={"q": email},
        )
        contact = None
        for ct in r.json().get("payload", []):
            if ct.get("email", "").lower() == email.lower():
                contact = ct
                break
        if not contact:
            return json.dumps({"error": "Contact not found"})
        r = await c.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/{contact['id']}/conversations",
            headers=_headers(),
        )
        if r.status_code == 200:
            return json.dumps([
                {"id": cv.get("id"), "subject": (cv.get("additional_attributes") or {}).get("mail_subject", ""),
                 "status": cv.get("status"), "created_at": cv.get("created_at")}
                for cv in r.json().get("payload", [])[:20]
            ])
        return json.dumps({"error": f"Failed: {r.status_code}"})

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
