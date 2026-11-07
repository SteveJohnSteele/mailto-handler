"""mailto: parsing and the webmail provider table. Standard library only."""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

ADDRESS_FIELDS = ("to", "cc", "bcc")
FIELDS = ("to", "cc", "bcc", "subject", "body")
PLACEHOLDERS = FIELDS + ("mailto",)

# Built-in providers. A template is an https URL with {placeholders}. Any
# query parameter whose placeholders are all empty is dropped from the URL.
# `{mailto}` is the whole original mailto: link, percent-encoded, for sites
# that accept one (that is how browsers register webmail as a mailto handler).
# `note` is shown in the settings window.
BUILTIN_PROVIDERS = [
    {"id": "gmail", "name": "Gmail",
     "template": "https://mail.google.com/mail/?view=cm&fs=1"
                 "&to={to}&cc={cc}&bcc={bcc}&su={subject}&body={body}",
     "note": ""},
    {"id": "outlook-live", "name": "Outlook.com / Hotmail",
     "template": "https://outlook.live.com/mail/0/deeplink/compose"
                 "?to={to}&cc={cc}&bcc={bcc}&subject={subject}&body={body}",
     "note": "To, subject and body work reliably. Microsoft does not document "
             "this link, and Cc/Bcc support has been reported as inconsistent."},
    {"id": "yahoo", "name": "Yahoo Mail",
     "template": "https://compose.mail.yahoo.com/"
                 "?to={to}&cc={cc}&bcc={bcc}&subject={subject}&body={body}",
     "note": "Addresses only (no display names). If you are signed out, the "
             "fields may be lost after logging in."},
    {"id": "fastmail", "name": "Fastmail",
     "template": "https://app.fastmail.com/mail/compose"
                 "?to={to}&cc={cc}&bcc={bcc}&subject={subject}&body={body}",
     "note": "To, Cc, subject and body confirmed; Bcc is accepted by Fastmail's "
             "mobile app and is expected to work here too."},
    {"id": "proton", "name": "Proton Mail",
     "template": "https://mail.proton.me/inbox/#mailto={mailto}",
     "note": "Proton has no compose URL with separate fields. This hands it "
             "the whole mailto: link, the same way Proton registers itself as "
             "a browser mailto handler."},
]

DEFAULT_PROVIDER = "gmail"


def parse_mailto(url):
    """Parse a mailto: URL (RFC 6068) into a dict of field -> string.

    Percent-escapes are decoded, but '+' stays a literal plus (it is not a
    space in mailto: URLs). Header names are case-insensitive.
    """
    if url[:7].lower() != "mailto:":
        raise ValueError("not a mailto: URL")
    rest = url[7:].split("#", 1)[0]
    path, _, query = rest.partition("?")

    values = {key: [] for key in FIELDS}
    if path:
        values["to"].append(unquote(path))
    for pair in query.split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        key = unquote(key).strip().lower()
        if key in values:
            values[key].append(unquote(value))

    fields = {}
    for key in ADDRESS_FIELDS:
        joined = ",".join(v.strip() for v in values[key] if v.strip())
        if joined:
            fields[key] = joined
    if values["subject"]:
        fields["subject"] = values["subject"][-1]
    if values["body"]:
        body = "\n".join(values["body"])
        fields["body"] = body.replace("\r\n", "\n").replace("\r", "\n")
    return {k: v for k, v in fields.items() if v}


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def template_problem(template):
    """Return why a template is unusable, or None if it is fine."""
    template = template.strip()
    if not re.match(r"https?://[^/\s]+", template, re.IGNORECASE):
        return "The address must start with http:// or https://"
    names = _PLACEHOLDER.findall(template)
    if not names:
        return ("Add at least one placeholder, such as {to}, {subject} "
                "or {body}.")
    unknown = sorted({n for n in names if n not in PLACEHOLDERS})
    if unknown:
        return "Unknown placeholder: " + ", ".join("{%s}" % n for n in unknown)
    return None


FIELD_LABELS = (("to", "To"), ("cc", "Cc"), ("bcc", "Bcc"),
                ("subject", "Subject"), ("body", "Body"))


def supported_fields(template):
    """The mailto fields a template can carry (a {mailto} template passes all)."""
    names = set(_PLACEHOLDER.findall(template))
    if "mailto" in names:
        return set(FIELDS)
    return names & set(FIELDS)


def fill_template(template, fields, mailto_url=""):
    """Substitute `fields` into `template`, dropping parameters left empty."""
    template = template.strip()
    values = {key: quote(fields.get(key, ""), safe="@,") for key in FIELDS}
    values["mailto"] = quote(mailto_url, safe="")

    def substitute(text):
        return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), text)

    def is_empty(text):
        names = _PLACEHOLDER.findall(text)
        return bool(names) and not any(values.get(n) for n in names)

    base, question, query = template.partition("?")
    if not question:
        return substitute(base)
    kept = [substitute(part) for part in query.split("&")
            if part and not is_empty(part)]
    url = substitute(base)
    return url + ("?" + "&".join(kept) if kept else "")


def all_providers(cfg):
    """Built-in providers followed by the user's custom ones."""
    providers = [dict(p, builtin=True) for p in BUILTIN_PROVIDERS]
    for item in cfg.get("custom_providers", []):
        if isinstance(item, dict) and item.get("id") and item.get("template"):
            providers.append({"id": item["id"],
                              "name": item.get("name") or item["id"],
                              "template": item["template"],
                              "note": "",
                              "builtin": False})
    return providers


def find_provider(cfg, provider_id=None):
    """The configured provider (or `provider_id`); falls back to Gmail."""
    wanted = provider_id or cfg.get("provider")
    providers = all_providers(cfg)
    for provider in providers:
        if provider["id"] == wanted:
            return provider
    return next(p for p in providers if p["id"] == DEFAULT_PROVIDER)


def build_url(provider, mailto_url):
    """The webmail compose URL for a mailto: link."""
    return fill_template(provider["template"], parse_mailto(mailto_url),
                         mailto_url)