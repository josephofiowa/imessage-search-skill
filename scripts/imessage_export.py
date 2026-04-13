#!/usr/bin/env python3
"""
iMessage Exporter & Search Tool (v2)
=====================================
Exports all iMessages from macOS chat.db to JSON and provides local search.
Extracts message text from BOTH the `text` column and the `attributedBody`
blob, which is where newer macOS versions store the actual message content.

Requirements:
  - macOS
  - Python 3.7+
  - Full Disk Access granted to Terminal (System Settings → Privacy & Security → Full Disk Access)

Usage:
  python3 imessage_export_v2.py export                  # Export all messages to imessages.json
  python3 imessage_export_v2.py export -o my_msgs.json  # Export to custom filename
  python3 imessage_export_v2.py search "hello"           # Search messages for "hello"
  python3 imessage_export_v2.py search "dinner" --from "+15551234567"
  python3 imessage_export_v2.py search "meeting" --after 2025-01-01
  python3 imessage_export_v2.py search "project" --before 2025-06-01 --limit 20
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# macOS stores iMessage timestamps as nanoseconds since 2001-01-01
APPLE_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01

DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
DEFAULT_EXPORT = "imessages.json"


def check_db_access():
    """Verify the chat.db file exists and is readable."""
    if not os.path.exists(DB_PATH):
        print("Error: chat.db not found. Are you running this on macOS?")
        print(f"  Expected path: {DB_PATH}")
        sys.exit(1)
    if not os.access(DB_PATH, os.R_OK):
        print("Error: Cannot read chat.db. Grant Full Disk Access to your terminal app.")
        print("  System Settings → Privacy & Security → Full Disk Access → add Terminal")
        sys.exit(1)


def apple_ts_to_iso(apple_timestamp):
    """Convert Apple Core Data timestamp (nanoseconds since 2001-01-01) to ISO 8601 string."""
    if apple_timestamp is None or apple_timestamp == 0:
        return None
    # Some older messages use seconds, newer ones use nanoseconds
    if apple_timestamp > 1e15:
        seconds = apple_timestamp / 1e9
    elif apple_timestamp > 1e12:
        seconds = apple_timestamp / 1e6
    else:
        seconds = apple_timestamp
    unix_ts = seconds + APPLE_EPOCH_OFFSET
    try:
        dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def extract_text_from_attributed_body(blob):
    """
    Extract plain text from the NSAttributedString blob stored in attributedBody.

    The blob is a binary plist containing an NSAttributedString. The actual text
    is embedded as a UTF-8 string between known byte markers. This approach avoids
    needing to fully deserialize the NSKeyedArchiver format.
    """
    if blob is None:
        return None

    try:
        # Strategy 1: Look for the streamtyped NSString content.
        # The text typically appears after a "NSString" marker followed by
        # a length-prefixed UTF-8 string, or after specific byte patterns.

        # First, try to find text between the common markers.
        # Pattern: text sits between 0x01 + length bytes and a trailing 0x86 0x84 or similar.
        # A more reliable approach: find "NSString" in the blob, then extract the
        # UTF-8 run that follows.

        # Attempt to decode as much as possible and extract readable text
        blob_bytes = bytes(blob)

        # Strategy: The actual message text in attributedBody is typically stored
        # as a length-prefixed UTF-8 string. We look for the pattern where the text
        # appears after certain CoreData serialization markers.

        # Method 1: Search for the text after "NSString" or "NSSt" markers
        text = None

        # The attributed body often has the plain text between specific byte sequences.
        # Look for the pattern: \x01+ followed by the text followed by \x06\x00
        # or other control sequences.

        # Most reliable method: find runs of valid UTF-8 text
        # The main text block usually follows a specific header pattern
        for marker in [b"+NSString", b"NSString", b"NSSt"]:
            idx = blob_bytes.find(marker)
            if idx != -1:
                # Skip past the marker and any intervening bytes to find the text
                search_start = idx + len(marker)
                # Look for the length byte(s) followed by UTF-8 text
                remaining = blob_bytes[search_start:]

                # Try to find a length-prefixed string
                # Often the pattern is: marker ... some bytes ... \x49 length text
                # Or directly after some control bytes
                for offset in range(min(50, len(remaining))):
                    candidate = remaining[offset:]
                    try:
                        # Try to decode a meaningful UTF-8 string
                        decoded = candidate.decode("utf-8", errors="strict")
                        # Strip trailing control characters
                        cleaned = ""
                        for ch in decoded:
                            if ch == "\x00":
                                break
                            if ord(ch) >= 32 or ch in ("\n", "\t", "\r"):
                                cleaned += ch
                            elif cleaned:
                                # Hit a control char after real text - likely end
                                break
                        cleaned = cleaned.strip()
                        if len(cleaned) >= 1:
                            text = cleaned
                            break
                    except UnicodeDecodeError:
                        continue
                if text:
                    break

        if text:
            return text

        # Method 2: Fallback — find the longest UTF-8 substring in the blob
        # Split on null bytes and control sequences, find the longest readable chunk
        # Skip the first ~30 bytes (header)
        best = ""
        current = ""
        for byte in blob_bytes[20:]:
            if 32 <= byte < 127 or byte >= 128:
                try:
                    char = bytes([byte]).decode("utf-8", errors="ignore")
                    current += char
                except Exception:
                    if len(current) > len(best):
                        best = current
                    current = ""
            elif byte in (10, 13, 9):  # newline, carriage return, tab
                current += chr(byte)
            else:
                if len(current) > len(best):
                    best = current
                current = ""
        if len(current) > len(best):
            best = current

        best = best.strip()
        if len(best) >= 1:
            return best

    except Exception:
        pass

    return None


def get_message_text(text_col, attributed_body_col):
    """Get the message text, preferring the text column but falling back to attributedBody."""
    if text_col is not None and text_col.strip():
        return text_col
    return extract_text_from_attributed_body(attributed_body_col)


def export_messages(output_path):
    """Read all messages from chat.db and export to JSON."""
    check_db_access()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT
        m.rowid AS message_id,
        m.text,
        m.attributedBody,
        m.date AS date_ts,
        m.date_read AS date_read_ts,
        m.is_from_me,
        m.service,
        m.cache_has_attachments,
        h.id AS contact_id,
        h.uncanonicalized_id AS contact_raw,
        c.chat_identifier,
        c.display_name AS chat_name,
        c.group_id
    FROM message m
    LEFT JOIN chat_message_join cmj ON m.rowid = cmj.message_id
    LEFT JOIN chat c ON cmj.chat_id = c.rowid
    LEFT JOIN handle h ON m.handle_id = h.rowid
    ORDER BY m.date ASC
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    messages = []
    text_recovered = 0
    for row in rows:
        raw_text = row["text"]
        attributed_body = row["attributedBody"]
        resolved_text = get_message_text(raw_text, attributed_body)

        if resolved_text and not raw_text:
            text_recovered += 1

        msg = {
            "id": row["message_id"],
            "text": resolved_text,
            "date": apple_ts_to_iso(row["date_ts"]),
            "date_read": apple_ts_to_iso(row["date_read_ts"]),
            "is_from_me": bool(row["is_from_me"]),
            "service": row["service"],
            "has_attachments": bool(row["cache_has_attachments"]),
            "contact": row["contact_id"] or row["contact_raw"],
            "chat_id": row["chat_identifier"],
            "chat_name": row["chat_name"],
            "group_id": row["group_id"],
        }
        messages.append(msg)

    # Fetch attachment info for messages that have them
    attach_query = """
    SELECT
        maj.message_id,
        a.filename,
        a.mime_type,
        a.transfer_name
    FROM message_attachment_join maj
    JOIN attachment a ON maj.attachment_id = a.rowid
    """
    cursor.execute(attach_query)
    attachments = {}
    for arow in cursor.fetchall():
        mid = arow["message_id"]
        if mid not in attachments:
            attachments[mid] = []
        attachments[mid].append({
            "filename": arow["filename"],
            "mime_type": arow["mime_type"],
            "name": arow["transfer_name"],
        })

    for msg in messages:
        if msg["has_attachments"] and msg["id"] in attachments:
            msg["attachments"] = attachments[msg["id"]]

    conn.close()

    export_data = {
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_messages": len(messages),
        "text_recovered_from_attributed_body": text_recovered,
        "database_path": DB_PATH,
        "messages": messages,
    }

    output = Path(output_path)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(messages):,} messages to {output.resolve()}")
    print(f"  - {text_recovered:,} messages recovered from attributedBody (text column was empty)")
    return output


def search_messages(
    query,
    export_file=DEFAULT_EXPORT,
    sender=None,
    after=None,
    before=None,
    from_me=None,
    limit=50,
    case_sensitive=False,
):
    """Search exported messages with optional filters."""
    path = Path(export_file)
    if not path.exists():
        print(f"Export file not found: {export_file}")
        print("Run 'python3 imessage_export_v2.py export' first.")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data["messages"]
    pattern = re.compile(re.escape(query), flags=0 if case_sensitive else re.IGNORECASE)

    results = []
    for msg in messages:
        text = msg.get("text") or ""
        if not pattern.search(text):
            continue

        # Apply filters
        if sender and msg.get("contact") and sender.lower() not in (msg["contact"] or "").lower():
            continue
        if from_me is not None and msg.get("is_from_me") != from_me:
            continue
        if after and (msg.get("date") or "") < after:
            continue
        if before and (msg.get("date") or "") > before:
            continue

        results.append(msg)
        if len(results) >= limit:
            break

    # Display results
    if not results:
        print(f'No messages found matching "{query}"')
        return

    print(f'Found {len(results)} result(s) for "{query}"'
          + (f" (showing first {limit})" if len(results) == limit else "")
          + ":\n")

    for msg in results:
        date_str = (msg.get("date") or "unknown date")[:19].replace("T", " ")
        sender_str = "You" if msg.get("is_from_me") else (msg.get("contact") or "unknown")
        chat_label = msg.get("chat_name") or msg.get("chat_id") or ""
        if chat_label:
            chat_label = f" [{chat_label}]"

        text = msg.get("text") or "(no text)"
        # Highlight matches
        highlighted = pattern.sub(lambda m: f"\033[1;33m{m.group()}\033[0m", text)

        print(f"  \033[90m{date_str}\033[0m  \033[36m{sender_str}\033[0m{chat_label}")
        print(f"  {highlighted}")
        if msg.get("attachments"):
            for att in msg["attachments"]:
                print(f"  \033[90m📎 {att.get('name') or att.get('filename', 'attachment')}\033[0m")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Export and search your iMessages locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export messages to JSON")
    export_parser.add_argument(
        "-o", "--output", default=DEFAULT_EXPORT, help=f"Output file (default: {DEFAULT_EXPORT})"
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search exported messages")
    search_parser.add_argument("query", help="Text to search for")
    search_parser.add_argument(
        "-f", "--file", default=DEFAULT_EXPORT, help="Export file to search"
    )
    search_parser.add_argument("--from", dest="sender", help="Filter by sender (phone/email)")
    search_parser.add_argument("--sent", action="store_true", help="Only show messages you sent")
    search_parser.add_argument("--received", action="store_true", help="Only show received messages")
    search_parser.add_argument("--after", help="Only messages after this date (YYYY-MM-DD)")
    search_parser.add_argument("--before", help="Only messages before this date (YYYY-MM-DD)")
    search_parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    search_parser.add_argument("--case-sensitive", action="store_true", help="Case-sensitive search")

    args = parser.parse_args()

    if args.command == "export":
        export_messages(args.output)
    elif args.command == "search":
        from_me = None
        if args.sent:
            from_me = True
        elif args.received:
            from_me = False
        search_messages(
            query=args.query,
            export_file=args.file,
            sender=args.sender,
            after=args.after,
            before=args.before,
            from_me=from_me,
            limit=args.limit,
            case_sensitive=args.case_sensitive,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
