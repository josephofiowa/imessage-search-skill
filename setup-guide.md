# Setup Guide: Granting Full Disk Access

This guide walks the user through granting their terminal app permission to read
the Messages database. Use this as a reference when helping the user — adapt the
language to their comfort level and don't dump the whole thing on them at once.

## Why this is needed

macOS protects the Messages database (where all iMessages and texts are stored)
behind a privacy permission called "Full Disk Access." Without it, the export
script can't read the database. This is a security feature built into macOS —
it's the same mechanism that protects your Photos, Mail, and other personal data
from apps reading them without your permission.

Granting Full Disk Access to your terminal app only lets that app read protected
files. It does NOT give access to the internet, other people, or anything outside
your computer. You can revoke it at any time.

## Identify which terminal app to authorize

The user needs to grant access to whichever app is running the skill. Common ones:

| If they're using...         | They should add...               |
|-----------------------------|----------------------------------|
| Claude Code in Terminal     | **Terminal** (built-in macOS app) |
| Claude Code in iTerm        | **iTerm**                        |
| Claude Code in VS Code      | **Visual Studio Code**           |
| Claude Code in Warp         | **Warp**                         |
| Claude Code in Cursor       | **Cursor**                       |
| Codex CLI                   | Whatever terminal runs it        |
| Running the script manually | Whatever terminal they're using  |

If the user doesn't know which terminal they're using, ask them:
"What app did you open to start this conversation? Does it have a black/dark
window where you typed a command? What's the name in the top-left corner of
your screen (next to the Apple logo)?"

## Step-by-step instructions

### For macOS Ventura (13) and later

1. **Open System Settings**
   - Click the Apple menu () in the top-left corner of your screen
   - Click **System Settings** (it has a gear icon)

2. **Navigate to Privacy & Security**
   - In the left sidebar, scroll down and click **Privacy & Security**
   - You may need to scroll down in the sidebar to find it

3. **Find Full Disk Access**
   - In the main area, scroll down to find **Full Disk Access**
   - Click on it

4. **Add your terminal app**
   - You'll see a list of apps. Click the **+** button at the bottom of the list
   - A file browser will open. Navigate to **Applications** (it should be the
     default location)
   - Find your terminal app (Terminal, iTerm, VS Code, etc.) and select it
   - Click **Open**
   - If prompted, enter your Mac password or use Touch ID to confirm

5. **Make sure the toggle is ON**
   - After adding the app, make sure the toggle switch next to it is turned ON
     (it should be blue/green)

6. **Restart your terminal**
   - **This is important!** Close your terminal app completely (Cmd+Q, not just
     closing the window) and reopen it
   - The permission change only takes effect after restarting the app
   - If using Claude Code, you'll need to start a new session after restarting

### For macOS Monterey (12) and earlier

1. **Open System Preferences**
   - Click the Apple menu () → **System Preferences**

2. **Go to Security & Privacy**
   - Click the **Security & Privacy** icon

3. **Open the Privacy tab**
   - Click the **Privacy** tab at the top

4. **Unlock settings**
   - Click the **lock icon** in the bottom-left corner
   - Enter your password or use Touch ID

5. **Select Full Disk Access**
   - In the left sidebar, scroll down and click **Full Disk Access**

6. **Add your terminal app**
   - Click the **+** button
   - Navigate to Applications, find your terminal, and click Open

7. **Restart your terminal**
   - Same as above — fully quit and reopen the terminal app

## Verifying it worked

After the user says they've completed the steps, verify with:

```bash
test -r ~/Library/Messages/chat.db && echo "ACCESS OK" || echo "NO ACCESS"
```

- **ACCESS OK** — They're good to go. Proceed with the export.
- **NO ACCESS** — Something went wrong. Walk through these checks:

## Common problems and fixes

### "I added it but still get NO ACCESS"
- **Did you restart the terminal?** This is the #1 issue. They need to fully
  quit (Cmd+Q) and reopen the app, not just close and reopen a window.
- **Did you add the right app?** If they're using VS Code but added Terminal,
  it won't work. Check which app they're actually running commands in.

### "I can't find my terminal in the Applications folder"
- **VS Code** might be in ~/Applications or /Applications
- **iTerm** is usually in /Applications as "iTerm.app"
- **Warp** is in /Applications
- They can also drag the app icon from their Dock directly into the Full Disk
  Access list (this works on some macOS versions)

### "It's asking for a password I don't know"
- This is their Mac login password (the one they use to log into the computer)
- If they use Touch ID to unlock their Mac, that should work too
- If they genuinely don't know the password and don't have Touch ID, they'll
  need to reset their Mac password (that's a separate process)

### "I don't see Full Disk Access in the list"
- They might be on a very old macOS version (pre-Mojave / pre-10.14). Full Disk
  Access was introduced in macOS Mojave. If they're on an older version, the
  Messages database might be readable without special permissions — try running
  the export directly.

### "My company manages this Mac and I can't change security settings"
- Managed/MDM Macs may restrict access to privacy settings. The user will need
  to contact their IT department to request Full Disk Access for their terminal.
- This is a firm blocker — there's no workaround without IT involvement.

### "I'm not on a Mac"
- This skill only works on macOS. iMessage data is only stored locally on Macs
  (and iPhones/iPads, but those databases aren't accessible without jailbreaking).
- If they have an iPhone but no Mac, this skill can't help them.

## Revoking access later

If the user wants to remove Full Disk Access after they're done:
1. Go back to System Settings → Privacy & Security → Full Disk Access
2. Toggle OFF the terminal app, or select it and click the minus (-) button
3. No restart needed for revoking — it takes effect immediately
