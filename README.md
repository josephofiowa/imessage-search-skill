# Search your iMessages with Claude Code & Codex

`imessage-search-skill` is LLM skill that lets you search your entire iMessage history using natural language. Describe what you're looking for — a half-remembered conversation ("Who did I talk to about visiting my office last month?"), a specific thing someone said ("When did [number] and I plan on biking?"), a person you texted about a topic — and the LLM finds it.

It **does not know** the names / contacts of people (yet), so reference phone numbers.

<video src="https://github.com/user-attachments/assets/3af780c3-0786-4f0b-b69a-d975f62dfbed" controls width="100%"></video>

## What is this?

This is a **skill** — a set of instructions and scripts that an LLM (like Claude, Codex, or others) reads to know how to help you with a specific task. **Think of it like a recipe card that teaches the AI how to search your text messages.**

You don't need to understand the code. The LLM handles everything.

## What can it do?

Ask things like:

- *"I want to find a conversation with someone that I can't remember their name or number. I haven't spoken to them in the last three months. I met them within the last three years. We've exchanged fewer than 30 messages total. Messages may have been about camera, visiting my office, and/or mechanical keyboards."*

- *"Help me find every time the number 2019561346 and I texted about Maine. Please return the contents of every message that mentions Maine."*

- *"Find the last time 2019561246 and I discussed going biking. Please provide the date that we discussed going for a bike ride."*

You can keep asking follow-up questions and running new searches against all your messages — the export is done once and then you can query it as many times as you want.

The skill exports your iMessage database, indexes all your conversations, and then uses the LLM to search through them based on your description. It works with 100K+ messages.

## Requirements

- **macOS** (this only works on Macs — iMessage data is stored locally)
- **Python 3.7+** (comes pre-installed on most Macs)
- An LLM tool that supports skills — [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex CLI](https://github.com/openai/codex), or similar

## Quick Start

### Using with Claude Code

1. Install the skill:
   ```bash
   claude skill add https://github.com/josephofiowa/imessage-search-skill
   ```

2. Start Claude Code and ask:
   ```
   Search my iMessages for conversations about [whatever you're looking for]
   ```

3. Claude will walk you through setup (one-time) and then search your messages.

### Using with Codex CLI

Codex supports the same skill format. There are three ways to install, pick whichever you're most comfortable with:

**Option A: Use the built-in skill installer (easiest)**

Open Codex in your terminal and type:
```
$skill-installer install https://github.com/josephofiowa/imessage-search-skill
```
Restart Codex after installing so it picks up the new skill.

**Option B: Clone and copy manually**
```bash
git clone https://github.com/josephofiowa/imessage-search-skill.git
cp -r imessage-search-skill ~/.codex/skills/imessage-search
```

**Option C: Use npx skills (Vercel's skill installer)**
```bash
npx skills add josephofiowa/imessage-search-skill
```

After installing with any method, restart Codex, then ask:
```
Search my iMessages for conversations about [whatever you're looking for]
```

**Important Codex settings for this skill:**

This skill needs to run Python scripts on your local machine and read your Messages database. You'll need to run Codex locally (not Codex Cloud) and use an approval mode that allows script execution:

```bash
# Recommended: auto-approve with workspace-level sandbox
codex --full-auto --sandbox workspace-write

# Or if you prefer to approve each step manually
codex --ask-for-approval on-request
```

If Codex asks about sandboxing or network access, note that this skill runs entirely offline — it reads a local database and writes local files. No network access is needed.

### Using with other LLMs

Point your LLM at the `SKILL.md` file in this repo. The skill is written to be LLM-agnostic — any model that can read files and run shell commands can follow the instructions.

## How it works

1. **Setup** — The skill guides you through granting your terminal app "Full Disk Access" so it can read the Messages database. This is a built-in macOS privacy feature — the skill explains every step.

2. **Export** — A Python script reads your Mac's Messages database (`chat.db`) and exports all messages to a JSON file. This includes messages where macOS stores the text in a binary blob format (common in newer macOS versions).

3. **Index** — A second script organizes your messages by conversation and creates a compact index. This is what makes it possible to search through hundreds of thousands of messages efficiently.

4. **Search** — You describe what you're looking for in plain English. The LLM scans the conversation index, loads promising threads, and presents matches with summaries and relevant quotes.

5. **Follow-up** — Ask follow-up questions, drill into specific conversations, or search for something new — all without re-exporting.

## Privacy

- **Everything stays on your Mac.** The export files are saved to your Downloads folder and never leave your computer (unless your LLM tool sends data to an API — check your tool's privacy settings).
- **Full Disk Access** is a standard macOS permission. You can revoke it at any time in System Settings → Privacy & Security → Full Disk Access.
- **The skill does not access your Contacts.** You'll see phone numbers and emails, not names.

## File structure

```
imessage-search-skill/
├── SKILL.md                        # Main skill instructions (what the LLM reads)
├── README.md                       # This file
├── scripts/
│   ├── imessage_export.py          # Exports messages from chat.db to JSON
│   └── build_index.py             # Builds conversation index for efficient search
└── references/
    └── setup-guide.md             # Detailed Full Disk Access setup walkthrough
```

## Troubleshooting

**"NO ACCESS" when checking permissions**
You need to grant Full Disk Access to your terminal app and restart it. See the setup guide — the skill will walk you through it.

**"I don't see all my messages"**
Make sure iCloud Messages is enabled and synced. The export reads from the local database, which should contain everything if iCloud sync is working.

**"I see phone numbers, not names"**
The Messages database stores contacts by phone number or email. The skill doesn't access your Contacts database. You can look up numbers in your Contacts app.

## License

MIT
