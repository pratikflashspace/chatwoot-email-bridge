"""
Chatwoot MCP Server v2.2
Exposes Chatwoot email operations as MCP tools for ClickUp Super Agents.
Fix: attachments now sent as proper email attachments, not inline base64.
"""
import os, json, re, httpx
from mcp.server.mcpserver import MCPServer

# ── Config ──────────────────────────────────────────────────
CHATWOOT_URL = os.environ.get("CHATWOOT_URL", "https://support.stirringminds.com")
CHATWOOT_TOKEN = os.environ.get("CHATWOOT_TOKEN", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID = int(os.environ.get("CHATWOOT_INBOX_ID", "35"))
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
PORT = int(os.environ.get("PORT", 10000))

# ── MCP Server ──────────────────────────────────────────────
mcp = MCPServer("Chatwoot")

def _headers():
    return {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}


def _guess_ext(ct):
    """Guess file extension from content-type."""
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
        "application/pdf": ".pdf", "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    return mapping.get(ct.split(";")[0].strip().lower(), "")


def _clean_filename(name, ct):
    """Ensure filename has a proper extension."""
    if not name or name == "file":
        ext = _guess_ext(ct)
        return f"document{ext}" if ext else "document"
    # If name has no extension, add one from content-type
    if "." not in name.split("/")[-1]:
        ext = _guess_ext(ct)
        if ext:
            name = name + ext
    return name


@mcp.tool()
async def find_or_create_contact(email: str, name: str = "") -> str:
    """
    Find an existing Chatwoot contact by email, or create a new one.

    Args:
        email: Email address to search or create
        name: Display name for new contact
    """
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
    """
    Create a new outbound email conversation in Chatwoot.

    Args:
        contact_id: Chatwoot contact ID (from find_or_create_contact)
        subject: Email subject line
    """
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
async def send_email(
    conversation_id: int,
    body: str,
    cc_email: str = "",
    attachment_urls: str = "[]",
) -> str:
    """
    Send an outgoing email in a Chatwoot conversation with optional attachments.
    Attachments are downloaded from the provided URLs and forwarded as proper email attachments.

    Args:
        conversation_id: Chatwoot conversation ID
        body: Full email body text
        cc_email: CC email address (optional)
        attachment_urls: JSON array of URLs to download and attach
    """
    url = f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"
    urls = json.loads(attachment_urls) if isinstance(attachment_urls, str) else attachment_urls

    files = []
    if urls:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            for att_url in urls:
                try:
                    hdrs = {}
                    if CLICKUP_API_TOKEN:
                        hdrs["Authorization"] = CLICKUP_API_TOKEN
                    r = await c.get(att_url, headers=hdrs)
                    if r.status_code == 200 and len(r.content) > 50:
                        ct = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
                        # Extract filename from content-disposition or URL
                        cd = r.headers.get("content-disposition", "")
                        if "filename=" in cd:
                            name = re.search(r'filename[*]?=["\']?([^"\';\s]+)', cd)
                            name = name.group(1) if name else "file"
                        else:
                            name = att_url.split("/")[-1].split("?")[0] or "file"
                        name = _clean_filename(name, ct)
                        files.append({"name": name, "content": r.content, "ct": ct})
                except Exception:
                    pass

    async with httpx.AsyncClient(timeout=60) as c:
        if files:
            # Send as outgoing message WITHOUT content_type=input_email
            # This ensures attachments are proper email attachments, not inline base64
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

        if r.status_code in (200, 201):
            fnames = [f["name"] for f in files]
            return json.dumps({"sent": True, "attachments_count": len(files), "filenames": fnames})
        return json.dumps({"error": f"Send failed: {r.status_code} {r.text[:200]}"})


@mcp.tool()
async def get_conversation_messages(conversation_id: int) -> str:
    """
    Get recent messages from a Chatwoot conversation.

    Args:
        conversation_id: Chatwoot conversation ID
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
            headers=_headers(),
        )
        if r.status_code == 200:
            msgs = r.json().get("payload", [])
            return json.dumps([
                {
                    "id": m.get("id"),
                    "content": (m.get("content") or "")[:500],
                    "type": m.get("message_type"),
                    "sender": (m.get("sender") or {}).get("name", ""),
                    "created_at": m.get("created_at"),
                    "attachments": len(m.get("attachments", [])),
                }
                for m in msgs[:20]
            ])
        return json.dumps({"error": f"Failed: {r.status_code}"})


@mcp.tool()
async def list_contact_conversations(email: str) -> str:
    """
    List all Chatwoot conversations for a contact email.

    Args:
        email: Contact email address
    """
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
            convs = r.json().get("payload", [])
            return json.dumps([
                {
                    "id": cv.get("id"),
                    "subject": (cv.get("additional_attributes") or {}).get("mail_subject", ""),
                    "status": cv.get("status"),
                    "created_at": cv.get("created_at"),
                }
                for cv in convs[:20]
            ])
        return json.dumps({"error": f"Failed: {r.status_code}"})


# ── Run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
