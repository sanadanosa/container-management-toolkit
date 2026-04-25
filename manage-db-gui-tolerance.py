#!/usr/bin/env python3
import curses
import subprocess
import sys
import time
import difflib
from collections import defaultdict

def normalize_region(region_part: str) -> str:
    region_part = region_part.lower()
    for suffix in ['kota', 'kab', 'kot']:
        if region_part.endswith(suffix):
            return region_part[:-len(suffix)]
    return region_part

class DBPairsManager:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.all_pairs = []
        self.filtered_pairs = []
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
            result = subprocess.run(
                ['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}'],
                capture_output=True, text=True, check=True
            )
            lines = result.stdout.strip().split('\n')
            raw_containers = [line.split('\t') for line in lines if '\t' in line]

            # Filter for DB types
            db_raw = [c for c in raw_containers if c[0].startswith(('postgis', 'redis'))]

            # CORE GROUPING LOGIC (Kept exactly as you had it)
            groups = defaultdict(list)
            unmatched = []
            for name, status in db_raw:
                prefix = 'postgis' if name.startswith('postgis') else 'redis'
                region_part = normalize_region(name[len(prefix):])

                matched = False
                for key in list(groups.keys()):
                    if region_part == key:
                        groups[key].append((prefix, name, status))
                        matched = True
                        break
                if not matched:
                    unmatched.append((prefix, region_part, name, status))

            for prefix, region_part, name, status in unmatched:
                best_score, best_key = 0, None
                for key in list(groups.keys()):
                    score = difflib.SequenceMatcher(None, region_part, key).ratio()
                    if score > 0.8 and score > best_score:
                        best_score, best_key = score, key
                if best_key:
                    groups[best_key].append((prefix, name, status))
                else:
                    groups[region_part].append((prefix, name, status))

            self.all_pairs = []
            for region_key in sorted(groups.keys()):
                group = groups[region_key]
                postgis = next(((n, s) for p, n, s in group if p == 'postgis'), None)
                redis = next(((n, s) for p, n, s in group if p == 'redis'), None)
                self.all_pairs.append({
                    'region': region_key.title() + (" (Unpaired)" if not (postgis and redis) else ""),
                    'postgis': postgis,
                    'redis': redis
                })
            self.apply_filter()
        except Exception as e:
            self.status_msg = f"Refresh Error: {str(e)}"

    def apply_filter(self):
        if not self.filter_text:
            self.filtered_pairs = self.all_pairs
        else:
            self.filtered_pairs = [p for p in self.all_pairs if self.filter_text.lower() in p['region'].lower()]
        self.current_idx = min(self.current_idx, max(0, len(self.filtered_pairs) - 1))
        self.ensure_visible()

    def get_search_input(self):
        height, _ = self.stdscr.getmaxyx()
        try:
            self.stdscr.addstr(height-1, 0, f" SEARCH REGION: ".ljust(18), curses.A_REVERSE)
            curses.echo()
            curses.curs_set(1)
            self.filter_text = self.stdscr.getstr(height-1, 17, 30).decode('utf-8')
            curses.noecho()
            curses.curs_set(0)
            self.apply_filter()
        except curses.error: pass

    def ensure_visible(self):
        height, _ = self.stdscr.getmaxyx()
        visible_rows = height - 5
        if visible_rows < 1: return
        if self.current_idx < self.top_idx:
            self.top_idx = self.current_idx
        elif self.current_idx >= self.top_idx + visible_rows:
            self.top_idx = self.current_idx - visible_rows + 1

    def perform_action(self, action: str):
        if not self.filtered_pairs: return
        targets = [self.filtered_pairs[i] for i in self.selected] if self.selected else [self.filtered_pairs[self.current_idx]]

        for cont in targets:
            for db_type in ['postgis', 'redis']:
                if cont[db_type]:
                    name = cont[db_type][0]
                    self.status_msg = f"{action.upper()}ing {name}..."
                    self.draw()
                    try:
                        subprocess.run(['docker', action, name], check=True, capture_output=True)
                        self.status_msg = f"SUCCESS: {name}"
                    except Exception as e:
                        self.status_msg = f"ERROR: {name}"

        self.selected.clear()
        self.refresh_containers()

    def get_status_style(self, status_str):
        if not status_str: return 0
        if any(word in status_str for word in ["Exited", "Stopped", "Dead", "Missing"]):
            return curses.color_pair(3) # RED
        if any(word in status_str for word in ["Paused", "Restarting", "Created"]):
            return curses.color_pair(4) # YELLOW
        return 0 # White for UP

    def draw(self):
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            visible_rows = height - 5

            # Header
            self.stdscr.addstr(0, 0, " 🗄  DB PAIRS MANAGER (PostGIS + Redis)", curses.color_pair(1) | curses.A_BOLD)
            self.stdscr.addstr(0, max(0, width-35), f"Pairs: {len(self.all_pairs)} | Shown: {len(self.filtered_pairs)}", curses.A_DIM)
            self.stdscr.addstr(1, 0, " [/] Search | [SPACE] Select | [S]tart [T]op [R]estart | [F]resh | [Q]uit".ljust(width-1)[:width-1], curses.A_REVERSE)

            # Table Headers
            self.stdscr.addstr(3, 2, "REGION".ljust(18), curses.A_UNDERLINE | curses.A_BOLD)
            self.stdscr.addstr(3, 20, "POSTGIS STATUS".ljust(25), curses.A_UNDERLINE | curses.A_BOLD)
            self.stdscr.addstr(3, 46, "REDIS STATUS".ljust(25), curses.A_UNDERLINE | curses.A_BOLD)

            for i in range(visible_rows):
                abs_idx = self.top_idx + i
                if abs_idx >= len(self.filtered_pairs): break
                row = 4 + i
                pair = self.filtered_pairs[abs_idx]

                style = curses.A_REVERSE if abs_idx == self.current_idx else 0
                if abs_idx in self.selected: style |= curses.A_BOLD

                # Region column
                marker = " ● " if abs_idx in self.selected else "   "
                self.stdscr.addstr(row, 0, f"{marker}{pair['region'][:15].ljust(17)}", style)

                # PostGIS column
                p_stat = pair['postgis'][1] if pair['postgis'] else "Missing"
                p_style = style | self.get_status_style(p_stat)
                self.stdscr.addstr(row, 20, f" {p_stat[:23].ljust(25)}", p_style)

                # Redis column
                r_stat = pair['redis'][1] if pair['redis'] else "Missing"
                r_style = style | self.get_status_style(r_stat)
                self.stdscr.addstr(row, 46, f" {r_stat[:23].ljust(25)}", r_style)

            # Footer
            self.stdscr.addstr(height-2, 0, f" FILTER: {self.filter_text or 'None'}".ljust(width-1)[:width-1], curses.color_pair(1))
            self.stdscr.addstr(height-1, 0, f" STATUS: {self.status_msg}".ljust(width-1)[:width-1], curses.A_REVERSE)
            self.stdscr.refresh()
        except curses.error: pass

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
                self.current_idx = min(len(self.filtered_pairs) - 1, self.current_idx + 1)
                self.ensure_visible()
            elif key == ord(' '):
                if self.current_idx in self.selected: self.selected.remove(self.current_idx)
                else: self.selected.add(self.current_idx)
            elif key == ord('s'): self.perform_action('start')
            elif key == ord('t'): self.perform_action('stop')
            elif key == ord('r'): self.perform_action('restart')
            elif key == ord('f') or key == -1: self.refresh_containers()

if __name__ == "__main__":
    try: curses.wrapper(lambda stdscr: DBPairsManager(stdscr).run())
    except KeyboardInterrupt: pass
