from __future__ import annotations

import datetime as dt
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"))


def send_report_email(report: dict[str, Any], pdf_path: str | Path) -> dict[str, str]:
    recipient = os.getenv("EMAIL_TO", "huic@sc.edu")
    if not smtp_configured():
        return {"status": "pending", "recipient": recipient, "detail": "SMTP secrets are not configured; PDF remains archived in GitHub."}
    papers = report.get("papers") or []
    counts = {category: sum(1 for paper in papers if paper.get("category") == category) for category in ("research", "review", "preprint")}
    directions = (report.get("synthesis") or {}).get("ranked_grant_directions") or []
    themes = "\n".join(f"- {item.get('title')}" for item in directions[:3]) or "- See attached infographic."
    message = EmailMessage()
    message["Subject"] = f"[Weekly ZGA/MZT] Research and review infographic - {report['coverage']['end']}"
    message["From"] = os.environ["SMTP_USERNAME"]
    message["To"] = recipient
    message.set_content(f"""Coverage: {report['coverage']['start']} to {report['coverage']['end']}
Primary research: {counts['research']}
Reviews: {counts['review']}
Preprints: {counts['preprint']}

Top early-Xenopus grant directions:
{themes}

The detailed cited PDF is attached and archived in the private GitHub repository. Automated summaries require expert verification before grant use.
""")
    pdf = Path(pdf_path)
    message.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename=pdf.name)
    try:
        with smtplib.SMTP_SSL(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "465")), context=ssl.create_default_context(), timeout=45) as smtp:
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except Exception as exc:
        return {"status": "failed", "recipient": recipient, "detail": f"SMTP failed: {type(exc).__name__}: {exc}"}
    return {"status": "verified", "recipient": recipient, "accepted_at": dt.datetime.now(dt.timezone.utc).isoformat(), "detail": "SMTP server accepted the message."}

