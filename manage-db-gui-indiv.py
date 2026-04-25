#!/usr/bin/env python3

"""
Terminal GUI App for Managing Individual DB Containers (PostGIS + Redis)
- Inspired by htop/btop: Lists all postgis* and redis* containers individually (decoupled, no pairing).
- Navigate with ↑↓ (or j/k), select with Space (toggle multi-select).
- Actions: S=start, T=stop, R=restart selected (or current if none).
- Q=quit, F=refresh list.
- Columns: Name | Status | Type (PostGIS/Redis).
- Requires: Python 3 + curses (stdlib), Docker installed/accessible.

Run: chmod +x manage-db-individual-gui.py && ./manage-db-individual-gui.py
"""

import curses
import subprocess
import sys
import time
from typing import List, Tuple

class DBIndividualManager:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.containers: List[Tuple[str, str, str]] = []  # (name, status, type: 'PostGIS' or 'Redis')
        self.selected: set[int] = set()  # indices
        self.current_idx = 0
        self.top_idx = 0  # For scrolling
        self.running = True
        self.refresh_containers()

    def refresh_containers(self):
        try:
            # Fetch all postgis* and redis* containers
            result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', 'name=^(postgis|redis)', '--format', '{{.Names}}\t{{.Status}}'],
                capture_output=True, text=True, check=True
            )
            lines = result.stdout.strip().split('\n')
            self.containers = []
            for line in lines:
                if not line.strip():
                    continue
                name, status = line.split('\t', 1)
                cont_type = 'PostGIS' if name.startswith('postgis') else 'Redis'
                self.containers.append((name, status, cont_type))
            self.containers.sort(key=lambda x: (x[2], x[0]))  # Sort: PostGIS first, then alpha by name
            self.selected.clear()  # Reset selections on refresh
            self.current_idx = 0
            self.top_idx = 0
        except subprocess.CalledProcessError:
            self.containers = []
            self.stdscr.addstr(0, 0, "Error: Failed to fetch containers (Docker not available?)")
            self.stdscr.refresh()
        except FileNotFoundError:
            self.containers = []
            self.stdscr.addstr(0, 0, "Error: Docker not found in PATH")
            self.stdscr.refresh()

    def ensure_visible(self):
        """Adjust top_idx so current_idx is visible."""
        height, _ = self.stdscr.getmaxyx()
        visible_rows = height - 4  # Header (3 lines) + status bar (1)
        if visible_rows < 1:
            return
        if self.current_idx < self.top_idx:
            self.top_idx = self.current_idx
        elif self.current_idx >= self.top_idx + visible_rows:
            self.top_idx = self.current_idx - visible_rows + 1

    def action_on_container(self, container: str, action: str) -> str:
        try:
            cmd = ['docker', action, container]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return f"{action.upper()}ed: {container}"
        except subprocess.CalledProcessError as e:
            return f"Failed {action} {container}: {e.stderr.strip() or 'Unknown error'}"

    def perform_action(self, action: str):
        if not self.containers:
            return
        targets = [self.containers[i][0] for i in self.selected] if self.selected else [self.containers[self.current_idx][0]]
        for container in targets:
            msg = self.action_on_container(container, action)
            print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)

    def draw(self):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        visible_rows = height - 4  # Account for header (3 lines) + status (1)

        # Header
        self.stdscr.addstr(0, 0, "DB Containers Manager (Individual PostGIS + Redis)", curses.A_BOLD)
        self.stdscr.addstr(0, width-30, f"Total: {len(self.containers)} | Selected: {len(self.selected)}", curses.A_BOLD)

        # Keybinds
        keystr = "↑↓/jk: Nav | Space: Select | S:Start T:Stop R:Restart | F:Refresh | Q:Quit"
        self.stdscr.addstr(1, 0, keystr, curses.A_REVERSE)

        # Table header
        self.stdscr.addstr(2, 0, "Name".ljust(40), curses.A_BOLD)
        self.stdscr.addstr(2, 40, "Status".ljust(30), curses.A_BOLD)
        self.stdscr.addstr(2, 70, "Type".ljust(10), curses.A_BOLD)
        self.stdscr.addstr(2, 80, "Sel", curses.A_BOLD)

        # Rows (with scrolling)
        if visible_rows > 0:
            for rel_idx in range(visible_rows):
                abs_idx = self.top_idx + rel_idx
                if abs_idx >= len(self.containers):
                    break
                row = 3 + rel_idx
                name, status, cont_type = self.containers[abs_idx]
                attrs = curses.A_REVERSE if abs_idx == self.current_idx else 0
                if abs_idx in self.selected:
                    attrs |= curses.A_BOLD
                self.stdscr.addstr(row, 0, name[:37].ljust(40), attrs)
                self.stdscr.addstr(row, 40, status[:27].ljust(30), attrs | (curses.color_pair(1) if 'Exited' in status else 0))
                self.stdscr.addstr(row, 70, cont_type.ljust(10), attrs)
                self.stdscr.addstr(row, 80, "→" if abs_idx in self.selected else "*", attrs)

            # Scroll indicator
            if self.top_idx > 0 or self.top_idx + visible_rows < len(self.containers):
                scroll_info = f"Scroll: {self.top_idx + 1}-{min(self.top_idx + visible_rows, len(self.containers))}/{len(self.containers)}"
                self.stdscr.addstr(2, width - len(scroll_info) - 2, scroll_info, curses.A_DIM)

        # Status bar
        self.stdscr.addstr(height-1, 0, "Press keys to act...", curses.A_REVERSE)
        self.stdscr.refresh()

    def run(self):
        # Basic color setup (if supported)
        try:
            curses.start_color()
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Red for exited
        except:
            pass

        curses.curs_set(0)  # Hide cursor
        curses.cbreak()  # Get keys without Enter
        self.stdscr.keypad(True)  # Special keys

        # Initial draw
        self.draw()

        while self.running:
            try:
                key = self.stdscr.getch()
                if key == ord('q') or key == 27:  # Q or Esc
                    self.running = False
                elif key == curses.KEY_F5 or key == ord('f'):  # F5 or F
                    self.refresh_containers()
                elif key in (curses.KEY_UP, ord('k')):
                    if self.current_idx > 0:
                        self.current_idx -= 1
                        self.ensure_visible()
                elif key in (curses.KEY_DOWN, ord('j')):
                    if self.current_idx < len(self.containers) - 1:
                        self.current_idx += 1
                        self.ensure_visible()
                elif key == ord(' '):  # Space: toggle select
                    if self.current_idx < len(self.containers):
                        if self.current_idx in self.selected:
                            self.selected.discard(self.current_idx)
                        else:
                            self.selected.add(self.current_idx)
                elif key == ord('s'):  # Start
                    self.perform_action('start')
                elif key == ord('t'):  # Stop
                    self.perform_action('stop')
                elif key == ord('r'):  # Restart
                    self.perform_action('restart')
                else:
                    # Ignore unknown keys gracefully
                    pass
                self.draw()
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                # Catch and log any curses/key errors without crashing
                print(f"Key handling error: {e}", file=sys.stderr)
                time.sleep(0.1)  # Brief pause to avoid spam

        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.curs_set(1)
        self.stdscr.refresh()

def main(stdscr):
    manager = DBIndividualManager(stdscr)
    manager.run()

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        print(f"Error running app: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
