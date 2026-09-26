import json
import os
import time
import curses

LOG_FILE = "logs/events.jsonl"

def load_events():
    events = []
    if not os.path.exists(LOG_FILE):
        return events
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events

def run_dashboard(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)

    while True:
        events = load_events()

        connections = auth_attempts = accepted = rejected = sessions = commands = 0

        for event in events:
            kind = str(event.get("event", "")).lower()
            if "connection" in kind:
                connections += 1
            if "auth" in kind:
                auth_attempts += 1
            if "authentication_success" in kind:
                accepted += 1
            if "reject" in kind or "failed" in kind:
                rejected += 1
            if "session" in kind:
                sessions += 1
            if "command" in kind:
                commands += 1

        stdscr.erase()
        height, width = stdscr.getmaxyx()

        lines = [
            "=" * min(width - 2, 72),
            "        MIRAGE HONEYPOT - LIVE DASHBOARD",
            "=" * min(width - 2, 72),
            "",
            "  STATUS",
            "    [ACTIVE] LOG STREAM",
            "",
            "  STATISTICS",
            f"    Connections    : {connections}",
            f"    Auth Attempts  : {auth_attempts}",
            f"    Accepted       : {accepted}",
            f"    Rejected       : {rejected}",
            f"    Sessions       : {sessions}",
            f"    Commands       : {commands}",
            "",
            "  RECENT ACTIVITY",
        ]

        for row, line in enumerate(lines):
            if row >= height - 2:
                break
            stdscr.addstr(row, 1, line[:width - 2])

        row = len(lines)

        for event in events[-8:]:
            if row >= height - 2:
                break

            timestamp = str(event.get("timestamp", ""))
            if len(timestamp) >= 19:
                timestamp = timestamp[11:19]

            source = str(event.get("source_ip", "-"))
            username = str(event.get("username", "-"))
            kind = str(event.get("event", "event"))

            line = f"    {timestamp}  {source:<15} {username:<12} {kind}"
            stdscr.addstr(row, 1, line[:width - 2])
            row += 1

        stdscr.addstr(height - 1, 1, "Q = quit | Refresh = 1 second")
        stdscr.refresh()

        if stdscr.getch() in (ord("q"), ord("Q")):
            break

        time.sleep(1)

if __name__ == "__main__":
    curses.wrapper(run_dashboard)
