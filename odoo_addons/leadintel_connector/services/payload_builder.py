# -*- coding: utf-8 -*-
"""Build sanitized lead payloads for SaaS upsert."""

import re

from odoo import fields


def _strip_html(html):
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(html))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]


def build_lead_payload(lead):
    ICP = lead.env["ir.config_parameter"].sudo()
    instance_id = ICP.get_param("leadintel.odoo_instance_id") or ""
    max_messages = int(ICP.get_param("leadintel.max_messages") or 10)

    partner = lead.partner_id
    email = lead.email_from or (partner.email if partner else False) or ""
    phone = lead.phone or (partner.phone if partner else False) or ""
    website = (partner.website if partner else False) or ""
    company = lead.partner_name or (partner.name if partner else False) or ""

    messages = []
    if hasattr(lead, "message_ids"):
        for msg in lead.message_ids[:max_messages]:
            if msg.message_type not in ("email", "comment"):
                continue
            messages.append(
                {
                    "message_id": str(msg.id),
                    "date": fields.Datetime.to_string(msg.date) if msg.date else None,
                    "author_email": msg.email_from or "",
                    "subject": msg.subject or "",
                    "body_text": _strip_html(msg.body),
                }
            )

    attachments = []
    if hasattr(lead, "attachment_ids"):
        for att in lead.attachment_ids[:20]:
            attachments.append(
                {
                    "id": str(att.id),
                    "filename": att.name or "file",
                    "mimetype": att.mimetype or None,
                    "size": att.file_size or None,
                }
            )

    write_date = fields.Datetime.to_string(lead.write_date) if lead.write_date else None
    idempotency_key = f"crm.lead:{lead.id}:{write_date or 'new'}"

    return {
        "idempotency_key": idempotency_key,
        "odoo_instance_id": instance_id,
        "model": "crm.lead",
        "res_id": str(lead.id),
        "write_date": write_date,
        "lead": {
            "name": lead.name or f"Lead {lead.id}",
            "company_name": company or None,
            "contact_name": lead.contact_name or None,
            "email": email or None,
            "phone": phone or None,
            "website": website or None,
            "country_code": (lead.country_id.code if lead.country_id else None),
            "city": lead.city or None,
            "description": _strip_html(lead.description) or None,
            "expected_revenue": float(lead.expected_revenue or 0) or None,
            "stage_name": lead.stage_id.name if lead.stage_id else None,
            "salesperson_name": lead.user_id.name if lead.user_id else None,
            "team_name": lead.team_id.name if lead.team_id else None,
        },
        "messages": messages,
        "attachments": attachments,
    }
