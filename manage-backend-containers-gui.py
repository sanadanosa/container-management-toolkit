#!/usr/bin/env python3
import curses
import subprocess
import sys
import time

class BackendManager:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.all_containers = []
        self.filtered_containers = []
        self.selected = set()
        self.current_idx = 0
        self.top_idx = 0
        self.running = True
        self.filter_text = ""
        self.status_msg = "Ready"

        # Initialize Colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)   # Headers
        curses.init_pair(3, curses.COLOR_RED, -1)    # Stopped/Exited
        curses.init_pair(4, curses.COLOR_YELLOW, -1) # Transitioning

        self.refresh_containers()

    def refresh_containers(self):
        try:
            # CORE LOGIC: Remains exactly as you provided
            result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', 'name=.*_backend$', '--format', '{{.Names}}\t{{.Status}}'],
                capture_output=True, text=True, check=True
            )
            lines = result.stdout.strip().split('\n')
            self.all_containers = [line.split('\t') for line in lines if '\t' in line]
            self.apply_filter()
        except Exception as e:
            self.status_msg = f"Refresh Error: {str(e)}"

    def apply_filter(self):
        if not self.filter_text:
            self.filtered_containers = self.all_containers
        else:
            self.filtered_containers = [c for c in self.all_containers if self.filter_text.lower() in c[0].lower()]

        self.current_idx = min(self.current_idx, max(0, len(self.filtered_containers) - 1))
        self.ensure_visible()

    def get_search_input(self):
        height, _ = self.stdscr.getmaxyx()
        try:
            self.stdscr.addstr(height-1, 0, f" SEARCH CITY: ".ljust(18), curses.A_REVERSE)
            curses.echo()
            curses.curs_set(1)
            self.filter_text = self.stdscr.getstr(height-1, 15, 30).decode('utf-8')
            curses.noecho()
            curses.curs_set(0)
            self.apply_filter()
        except curses.error:
            pass

    def ensure_visible(self):
        height, _ = self.stdscr.getmaxyx()
        visible_rows = height - 5
        if visible_rows < 1: return
        if self.current_idx < self.top_idx:
            self.top_idx = self.current_idx
        elif self.current_idx >= self.top_idx + visible_rows:
            self.top_idx = self.current_idx - visible_rows + 1

    def perform_action(self, action: str):
        if not self.filtered_containers: return
        targets = [self.filtered_containers[i][0] for i in self.selected] if self.selected else [self.filtered_containers[self.current_idx][0]]

        self.status_msg = f"Executing {action}..."
        self.draw()

        for container in targets:
            try:
                subprocess.run(['docker', action, container], check=True, capture_output=True)
                self.status_msg = f"SUCCESS: {action.upper()} {container}"
            except subprocess.CalledProcessError as e:
                self.status_msg = f"FAILED: {e.stderr.decode().strip()}"

        self.selected.clear()
        self.refresh_containers()

    def draw(self):
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            visible_rows = height - 5

            # Header Section
            self.stdscr.addstr(0, 0, " 🐳 BACKEND MANAGER", curses.color_pair(1) | curses.A_BOLD)
            self.stdscr.addstr(0, max(0, width-35), f"Total: {len(self.all_containers)} | Shown: {len(self.filtered_containers)}", curses.A_DIM)

            # Command Bar
            keystr = " [/] Search | [SPACE] Select | [S]tart [T]op [R]estart | [F]resh | [Q]uit"
            self.stdscr.addstr(1, 0, keystr.ljust(width-1)[:width-1], curses.A_REVERSE)

            # Table Header
            self.stdscr.addstr(3, 2, "CONTAINER NAME".ljust(45), curses.A_UNDERLINE | curses.A_BOLD)
            self.stdscr.addstr(3, 50, "STATUS", curses.A_UNDERLINE | curses.A_BOLD)

            # List Rows
            for i in range(visible_rows):
                abs_idx = self.top_idx + i
                if abs_idx >= len(self.filtered_containers): break

                name, status = self.filtered_containers[abs_idx]
                row = 4 + i

                sel_marker = " ● " if abs_idx in self.selected else "   "
                line_text = f"{sel_marker}{name.ljust(45)} {status[:30]}"

                style = 0 # Default (White)
                if any(word in status for word in ["Exited", "Stopped", "Dead"]):
                    style = curses.color_pair(3) # RED
                elif any(word in status for word in ["Paused", "Restarting", "Created"]):
                    style = curses.color_pair(4) # YELLOW

                if abs_idx == self.current_idx:
                    style |= curses.A_REVERSE
                if abs_idx in self.selected:
                    style |= curses.A_BOLD

                self.stdscr.addstr(row, 0, line_text.ljust(width-1)[:width-1], style)

            # Bottom Status Bar (The fix: width-1 ensures no crash)
            filter_line = f" FILTER: {self.filter_text if self.filter_text else 'None (Press / to search)'}"
            status_line = f" {self.status_msg}"

            self.stdscr.addstr(height-2, 0, filter_line[:width-1], curses.color_pair(1))
            self.stdscr.addstr(height-1, 0, status_line.ljust(width-1)[:width-1], curses.A_REVERSE)

            self.stdscr.refresh()
        except curses.error:
            # If terminal is too small, this prevents crash
            pass

    def run(self):
        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(3000)

        while self.running:
            self.draw()
            key = self.stdscr.getch()

            if key == ord('q'): self.running = False
            elif key == ord('/'): self.get_search_input()
            elif key in (curses.KEY_UP, ord('k')):
                self.current_idx = max(0, self.current_idx - 1)
                self.ensure_visible()
            elif key in (curses.KEY_DOWN, ord('j')):
                self.current_idx = min(len(self.filtered_containers) - 1, self.current_idx + 1)
                self.ensure_visible()
            elif key == ord(' '):
                if self.current_idx in self.selected: self.selected.remove(self.current_idx)
                else: self.selected.add(self.current_idx)
            elif key == ord('s'): self.perform_action('start')
            elif key == ord('t'): self.perform_action('stop')
            elif key == ord('r'): self.perform_action('restart')
            elif key == ord('f') or key == -1:
                self.refresh_containers()

def main(stdscr):
    manager = BackendManager(stdscr)
    manager.run()

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
