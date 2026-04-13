#!/usr/bin/env python3
"""
iMessage Conversation Indexer
==============================
Takes the raw JSON export from imessage_export.py and organizes it into:
  1. A compact conversation index (conversations_index.json) — one entry per
     conversation with metadata and recent message previews, small enough to
     fit in an LLM's context window.
  2. Individual conversation files (conversations/{id}.json) — full message
     threads loaded on-demand when a conversation matches a search query.

Usage:
  python3 build_index.py <export.json> <output_directory>

Example:
  python3 build_index.py ~/Downloads/imessage_export_raw.json ~/Downloads/imessage_export/
"""

import json
import os
import re
import sys
import hashlib
from collections import defaultdict
from pathlib import Path


def safe_filename(identifier):
    """Convert a contact identifier (phone/email) into a safe filename."""
    if not identifier:
        return "unknown"
    # Create a readable but filesystem-safe name
    clean = re.sub(r'[^\w@.\-+]', '_', str(identifier))
    # If the cleaned name is too long, truncate and add a hash
    if len(clean) > 80:
        h = hashlib.md5(identifier.encode()).hexdigest()[:8]
        clean = clean[:70] + "_" + h
    return clean


def format_date_range(dates):
    """Format a list of ISO date strings into a human-readable range like 'Oct–Nov 2025'."""
    if not dates:
        return "unknown dates"

    valid = [d for d in dates if d]
    if not valid:
        return "unknown dates"

    valid.sort()
    first = valid[0][:10]   # YYYY-MM-DD
    last = valid[-1][:10]

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    try:
        fy, fm = int(first[:4]), int(first[5:7])
        ly, lm = int(last[:4]), int(last[5:7])

        if fy == ly and fm == lm:
            return f"{months[fm-1]} {fy}"
        elif fy == ly:
            return f"{months[fm-1]}–{months[lm-1]} {fy}"
        else:
            return f"{months[fm-1]} {fy} – {months[lm-1]} {ly}"
    except (ValueError, IndexError):
        return f"{first} to {last}"


def build_index(export_path, output_dir):
    """Build the conversation index and per-conversation files."""
    export_path = Path(export_path)
    output_dir = Path(output_dir)

    if not export_path.exists():
        print(f"Error: Export file not found: {export_path}")
        sys.exit(1)

    print(f"Reading export from {export_path}...")
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    print(f"  Found {len(messages):,} total messages")

    # Group messages by conversation
    # Use chat_identifier as primary key, fall back to contact
    conversations = defaultdict(list)
    for msg in messages:
        conv_id = msg.get("chat_id") or msg.get("contact") or "unknown"
        conversations[conv_id].append(msg)

    print(f"  Organized into {len(conversations):,} conversations")

    # Create output directories
    conv_dir = output_dir / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)

    # Build the index
    index_entries = []
    conversation_files = []

    for conv_id, msgs in conversations.items():
        # Sort messages chronologically
        msgs.sort(key=lambda m: m.get("date") or "")

        # Gather all unique contacts in this conversation
        contacts = set()
        for m in msgs:
            if m.get("contact"):
                contacts.add(m["contact"])

        # Compute metadata
        dates = [m.get("date") for m in msgs if m.get("date")]
        total_msgs = len(msgs)
        sent_count = sum(1 for m in msgs if m.get("is_from_me"))
        received_count = total_msgs - sent_count
        first_date = dates[0] if dates else None
        last_date = dates[-1] if dates else None
        has_attachments = any(m.get("has_attachments") for m in msgs)

        # Chat name (for group chats)
        chat_name = None
        for m in msgs:
            if m.get("chat_name"):
                chat_name = m["chat_name"]
                break

        # Count messages that have actual text content (attachments/reactions have null text)
        text_msg_count = sum(1 for m in msgs if m.get("text") and m.get("text").strip())

        # Preview: scan backwards through up to 30 recent messages to find 5 with text.
        # Using a fixed recent slice (e.g. last 5) fails whenever recent messages are
        # all attachment-only or tapback reactions — leaving message_previews empty and
        # making the conversation appear to have no content in the index.
        previews = []
        for m in reversed(msgs[-30:]):
            text = m.get("text") or ""
            if text.strip():
                if len(text) > 200:
                    text = text[:200] + "..."
                sender = "You" if m.get("is_from_me") else (m.get("contact") or "them")
                previews.append({
                    "sender": sender,
                    "text": text,
                    "date": m.get("date", "")[:10]
                })
                if len(previews) >= 5:
                    break

        # Also grab a sample of earlier messages for better keyword coverage.
        # Scan up to 15 messages around the midpoint to find 3 with text.
        if len(msgs) > 10:
            mid = len(msgs) // 2
            half_window = 7
            mid_slice = msgs[max(0, mid - half_window):mid + half_window + 1]
            mid_count = 0
            for m in mid_slice:
                text = m.get("text") or ""
                if text.strip():
                    if len(text) > 150:
                        text = text[:150] + "..."
                    sender = "You" if m.get("is_from_me") else (m.get("contact") or "them")
                    previews.append({
                        "sender": sender,
                        "text": text,
                        "date": m.get("date", "")[:10]
                    })
                    mid_count += 1
                    if mid_count >= 3:
                        break

        # Build the filename for the conversation file
        filename = safe_filename(conv_id) + ".json"

        # Build index entry
        entry = {
            "conversation_id": conv_id,
            "file": filename,
            "contacts": sorted(contacts),
            "chat_name": chat_name,
            "total_messages": total_msgs,
            "messages_with_text": text_msg_count,
            "sent_by_you": sent_count,
            "received": received_count,
            "first_message_date": first_date,
            "last_message_date": last_date,
            "date_range_display": format_date_range(dates),
            "has_attachments": has_attachments,
            "message_previews": previews,
        }
        index_entries.append(entry)

        # Write the full conversation file
        conv_data = {
            "conversation_id": conv_id,
            "contacts": sorted(contacts),
            "chat_name": chat_name,
            "total_messages": total_msgs,
            "messages": msgs,
        }
        conv_file = conv_dir / filename
        with open(conv_file, "w", encoding="utf-8") as f:
            json.dump(conv_data, f, ensure_ascii=False, indent=2)
        conversation_files.append(filename)

    # Sort index by last message date (most recent first)
    index_entries.sort(
        key=lambda e: e.get("last_message_date") or "",
        reverse=True
    )

    # Write the index
    index_data = {
        "generated_from": str(export_path),
        "total_conversations": len(index_entries),
        "total_messages": len(messages),
        "exported_at": data.get("exported_at"),
        "conversations": index_entries,
    }

    index_path = output_dir / "conversations_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\nDone! Output written to {output_dir}/")
    print(f"  conversations_index.json  ({len(index_entries):,} conversations)")
    print(f"  conversations/            ({len(conversation_files):,} files)")
    print()

    # Show some stats
    if index_entries:
        biggest = max(index_entries, key=lambda e: e["total_messages"])
        print(f"  Largest conversation: {biggest['conversation_id']} "
              f"({biggest['total_messages']:,} messages)")
        one_msg = sum(1 for e in index_entries if e["total_messages"] == 1)
        print(f"  Single-message conversations: {one_msg:,}")

        # Estimate index file size
        index_size = os.path.getsize(index_path)
        if index_size > 1_000_000:
            print(f"  Index file size: {index_size / 1_000_000:.1f} MB")
        else:
            print(f"  Index file size: {index_size / 1_000:.0f} KB")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 build_index.py <export.json> <output_directory>")
        print()
        print("Example:")
        print("  python3 build_index.py ~/Downloads/imessage_export_raw.json ~/Downloads/imessage_export/")
        sys.exit(1)

    export_path = sys.argv[1]
    output_dir = sys.argv[2]
    build_index(export_path, output_dir)


if __name__ == "__main__":
    main()
