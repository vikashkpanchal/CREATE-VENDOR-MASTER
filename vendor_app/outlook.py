"""Outlook draft creation via COM (Outlook 2016 / Office 16, Windows only).

Every email is saved as a DRAFT in a named sub-folder rather than sent, so
the user can review each one in Outlook before sending.

The user's default Outlook signature is preserved: creating the item and
touching its Inspector makes Outlook populate HTMLBody with the configured
signature, which we then append below our own body.

Importing this module is safe on any platform - pywin32 is imported lazily
and OUTLOOK_AVAILABLE reports whether Outlook can actually be driven here.
"""

import re

# olFolderInbox / olMailItem / olFolderDrafts constants (avoids needing the
# generated Outlook type library to be present).
OL_FOLDER_INBOX = 6
OL_FOLDER_DRAFTS = 16
OL_MAIL_ITEM = 0

try:  # pragma: no cover - platform dependent
    import pythoncom  # noqa: F401
    import win32com.client  # noqa: F401

    OUTLOOK_AVAILABLE = True
    IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - platform dependent
    OUTLOOK_AVAILABLE = False
    IMPORT_ERROR = str(exc)


class OutlookError(RuntimeError):
    """Raised when Outlook cannot be reached or driven."""


def ensure_available():
    if not OUTLOOK_AVAILABLE:
        raise OutlookError(
            "Outlook automation is unavailable on this machine.\n\n"
            "It requires Windows with Microsoft Outlook installed and the "
            "'pywin32' package (pip install pywin32).\n\n"
            f"Import error: {IMPORT_ERROR}"
        )


def _connect():
    ensure_available()
    import pythoncom
    import win32com.client

    # Drafts are created from a Tk callback, which may not be the thread that
    # first initialised COM - initialise defensively and ignore "already done".
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass

    try:
        app = win32com.client.Dispatch("Outlook.Application")
        namespace = app.GetNamespace("MAPI")
    except Exception as exc:
        raise OutlookError(f"Could not start or connect to Outlook: {exc}") from exc
    return app, namespace


def get_or_create_folder(namespace, folder_name: str):
    """Return the named sub-folder of the default Inbox, creating it if needed."""
    try:
        inbox = namespace.GetDefaultFolder(OL_FOLDER_INBOX)
    except Exception as exc:
        raise OutlookError(f"Could not open the Outlook Inbox: {exc}") from exc

    for i in range(1, inbox.Folders.Count + 1):
        existing = inbox.Folders.Item(i)
        if str(existing.Name).strip().lower() == folder_name.strip().lower():
            return existing

    try:
        return inbox.Folders.Add(folder_name)
    except Exception as exc:
        raise OutlookError(
            f"Could not create the Outlook folder '{folder_name}': {exc}"
        ) from exc


def _default_signature_html(mail) -> str:
    """Outlook fills HTMLBody with the default signature once the item's
    Inspector is realised; whatever is there at that point IS the signature."""
    try:
        mail.GetInspector  # noqa: B018 - property access is the trigger
        return mail.HTMLBody or ""
    except Exception:
        return ""


def _merge_body_with_signature(body_html: str, signature_html: str) -> str:
    """Insert our body above the signature, inside the signature's own
    <body> when there is one, so Outlook keeps the signature's styling."""
    if not signature_html.strip():
        return body_html

    match = re.search(r"<body[^>]*>", signature_html, re.IGNORECASE)
    if match:
        insert_at = match.end()
        return signature_html[:insert_at] + body_html + signature_html[insert_at:]
    return body_html + signature_html


def create_draft(
    to_addresses: str,
    subject: str,
    body_html: str,
    folder_name: str,
    cc_addresses: str = "",
):
    """Save one draft into `folder_name` under the Inbox. Returns the item.

    `to_addresses` / `cc_addresses` are Outlook-style recipient strings -
    multiple addresses separated by ';'.
    """
    app, namespace = _connect()
    folder = get_or_create_folder(namespace, folder_name)

    try:
        mail = app.CreateItem(OL_MAIL_ITEM)
        signature = _default_signature_html(mail)

        mail.To = to_addresses or ""
        if cc_addresses:
            mail.CC = cc_addresses
        mail.Subject = subject
        mail.HTMLBody = _merge_body_with_signature(body_html, signature)

        # Save first (lands in Drafts), then move into the target sub-folder.
        mail.Save()
        moved = mail.Move(folder)
        return moved if moved is not None else mail
    except OutlookError:
        raise
    except Exception as exc:
        raise OutlookError(f"Could not create the Outlook draft: {exc}") from exc


def create_drafts(messages: list, folder_name: str, cc_addresses: str = "", progress=None):
    """Create many drafts in one Outlook session.

    `messages` is a list of dicts with 'to', 'subject' and 'body_html'.
    Failures are collected per-message rather than aborting the batch, so one
    bad recipient never costs the user the rest of the run.

    Returns {"created": int, "errors": [(label, message), ...]}.
    """
    app, namespace = _connect()
    folder = get_or_create_folder(namespace, folder_name)

    created = 0
    errors = []
    for index, message in enumerate(messages, start=1):
        label = message.get("label") or message.get("subject") or f"message {index}"
        try:
            mail = app.CreateItem(OL_MAIL_ITEM)
            signature = _default_signature_html(mail)

            mail.To = message.get("to", "") or ""
            if cc_addresses:
                mail.CC = cc_addresses
            mail.Subject = message.get("subject", "")
            mail.HTMLBody = _merge_body_with_signature(message.get("body_html", ""), signature)
            mail.Save()
            mail.Move(folder)
            created += 1
        except Exception as exc:
            errors.append((label, str(exc)))
        if progress is not None:
            progress(index, len(messages))

    return {"created": created, "errors": errors}
