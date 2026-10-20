"""GUI for searching files by pattern, exporting CSV, and copying with progress."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Literal, Optional

from copy_files import CopyProgress, copy_file_list, filter_sources_not_in_dest
from csv_export import save_paths_csv
from file_matcher import MatchMode, SearchProgress, find_matching_files

OperationKind = Literal["search", "copy"]


class FileTypeCopierApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("File Type Copier")
        self.minsize(640, 520)
        self.geometry("720x560")

        self._search_results: list[Path] = []
        self._search_thread: Optional[threading.Thread] = None
        self._copy_thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._active_operation: Optional[OperationKind] = None
        self._busy = False

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Search directory
        ttk.Label(main, text="Directory to search:").grid(row=0, column=0, sticky=tk.W, **pad)
        self.search_dir_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.search_dir_var, width=56).grid(
            row=0, column=1, sticky=tk.EW, **pad
        )
        ttk.Button(main, text="Browse…", command=self._browse_search_dir).grid(
            row=0, column=2, **pad
        )

        # Pattern
        ttk.Label(main, text="Search pattern:").grid(row=1, column=0, sticky=tk.W, **pad)
        self.pattern_var = tk.StringVar(value="*.pdf")
        ttk.Entry(main, textvariable=self.pattern_var, width=56).grid(
            row=1, column=1, sticky=tk.EW, **pad
        )
        mode_frame = ttk.Frame(main)
        mode_frame.grid(row=1, column=2, sticky=tk.W, **pad)
        self.match_mode_var = tk.StringVar(value="glob")
        ttk.Radiobutton(
            mode_frame, text="Glob", variable=self.match_mode_var, value="glob"
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            mode_frame, text="Regex", variable=self.match_mode_var, value="regex"
        ).pack(anchor=tk.W)

        ttk.Label(
            main,
            text="Glob examples: *.pdf, report_*.docx  |  Regex matches file names only",
            font=("Segoe UI", 8),
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=8)

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            main, text="Include subfolders", variable=self.recursive_var
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, **pad)

        batch_frame = ttk.LabelFrame(main, text="Batch settings (search and copy)", padding=8)
        batch_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, **pad)
        ttk.Label(batch_frame, text="Batch size (files):").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.batch_size_var = tk.StringVar(value="100")
        batch_size_spin = ttk.Spinbox(
            batch_frame,
            from_=0,
            to=10000,
            width=8,
            textvariable=self.batch_size_var,
        )
        batch_size_spin.grid(row=0, column=1, sticky=tk.W)
        ttk.Label(batch_frame, text="0 = off").grid(row=0, column=2, sticky=tk.W, padx=8)

        ttk.Label(batch_frame, text="Pause between batches (sec):").grid(
            row=0, column=3, sticky=tk.W, padx=(16, 8)
        )
        self.batch_pause_var = tk.StringVar(value="0.5")
        ttk.Spinbox(
            batch_frame,
            from_=0,
            to=60,
            increment=0.5,
            width=8,
            textvariable=self.batch_pause_var,
        ).grid(row=0, column=4, sticky=tk.W)

        ttk.Label(
            batch_frame,
            text=(
                "Tip: use glob *.pdf on server shares; copy to local SSD; "
                "Search → Save CSV → Copy. Batch 50–100, pause 0.5–2 s on slow links."
            ),
            font=("Segoe UI", 8),
            wraplength=640,
        ).grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(8, 0))

        # CSV output
        ttk.Label(main, text="Save list (CSV):").grid(row=5, column=0, sticky=tk.W, **pad)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.csv_path_var, width=56).grid(
            row=5, column=1, sticky=tk.EW, **pad
        )
        ttk.Button(main, text="Browse…", command=self._browse_csv).grid(row=5, column=2, **pad)

        btn_row = ttk.Frame(main)
        btn_row.grid(row=6, column=0, columnspan=3, sticky=tk.W, **pad)
        self.search_btn = ttk.Button(btn_row, text="Search", command=self._run_search)
        self.search_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.save_csv_btn = ttk.Button(
            btn_row, text="Save CSV", command=self._save_csv, state=tk.DISABLED
        )
        self.save_csv_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.cancel_btn = ttk.Button(
            btn_row, text="Cancel", command=self._request_cancel, state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT)

        # Results summary
        self.results_label_var = tk.StringVar(value="No search yet.")
        ttk.Label(main, textvariable=self.results_label_var).grid(
            row=7, column=0, columnspan=3, sticky=tk.W, **pad
        )

        # List preview
        list_frame = ttk.LabelFrame(main, text="Results (first 500 paths)", padding=4)
        list_frame.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW, **pad)
        self.results_list = tk.Listbox(list_frame, height=8, font=("Consolas", 9))
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.results_list.yview)
        self.results_list.configure(yscrollcommand=scroll.set)
        self.results_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Copy destination
        ttk.Separator(main, orient=tk.HORIZONTAL).grid(
            row=9, column=0, columnspan=3, sticky=tk.EW, pady=8
        )
        ttk.Label(main, text="Copy files to:").grid(row=10, column=0, sticky=tk.W, **pad)
        self.copy_dest_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.copy_dest_var, width=56).grid(
            row=10, column=1, sticky=tk.EW, **pad
        )
        ttk.Button(main, text="Browse…", command=self._browse_copy_dest).grid(
            row=10, column=2, **pad
        )

        self.copy_btn = ttk.Button(main, text="Copy all listed files", command=self._start_copy)
        self.copy_btn.grid(row=11, column=0, columnspan=3, sticky=tk.W, **pad)

        pre_copy_frame = ttk.LabelFrame(main, text="Pre-copy check (destination vs list)", padding=8)
        pre_copy_frame.grid(row=12, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.pre_copy_status_var = tk.StringVar(
            value="Not run yet. Click Copy to compare file names with the destination folder."
        )
        ttk.Label(
            pre_copy_frame,
            textvariable=self.pre_copy_status_var,
            wraplength=640,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        # Progress
        prog_frame = ttk.LabelFrame(main, text="Progress", padding=8)
        prog_frame.grid(row=13, column=0, columnspan=3, sticky=tk.EW, **pad)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            prog_frame, variable=self.progress_var, maximum=100.0, length=400, mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 6))

        self.progress_detail_var = tk.StringVar(
            value="Total: 0  |  Copied: 0  |  Skipped: 0  |  Failed: 0  |  0.0%"
        )
        ttk.Label(prog_frame, textvariable=self.progress_detail_var).pack(anchor=tk.W)
        self.current_file_var = tk.StringVar(value="Current file: —")
        ttk.Label(prog_frame, textvariable=self.current_file_var).pack(anchor=tk.W)

        main.columnconfigure(1, weight=1)
        main.rowconfigure(8, weight=1)

    def _parse_batch_settings(self) -> tuple[int, float, int] | None:
        """
        Read batch size, pause, and progress throttle from the UI.

        Returns:
            Tuple of (batch_size, batch_pause_seconds, progress_every), or None if invalid.
        """
        try:
            batch_size = int(self.batch_size_var.get().strip())
            batch_pause = float(self.batch_pause_var.get().strip())
        except ValueError:
            messagebox.showwarning(
                "Invalid batch settings",
                "Batch size must be an integer and pause must be a number.",
            )
            return None

        if batch_size < 0:
            messagebox.showwarning("Invalid batch settings", "Batch size cannot be negative.")
            return None
        if batch_pause < 0:
            messagebox.showwarning("Invalid batch settings", "Pause cannot be negative.")
            return None

        if batch_size > 0:
            progress_every = max(1, batch_size // 10)
        else:
            progress_every = 10

        return batch_size, batch_pause, progress_every

    def _reset_pre_copy_status(self) -> None:
        """Clear the pre-copy destination check message."""
        self.pre_copy_status_var.set(
            "Not run yet. Click Copy to compare file names with the destination folder."
        )

    def _set_pre_copy_status(
        self,
        *,
        already_in_dest: int,
        remaining: int,
        csv_path: Optional[Path] = None,
        csv_updated: bool = False,
    ) -> None:
        """
        Show how many names already exist in the destination and any CSV changes.

        Args:
            already_in_dest: Sources removed because the file name exists in dest.
            remaining: Sources still queued to copy.
            csv_path: Save list path when set in the UI.
            csv_updated: True when the CSV file was rewritten after filtering.
        """
        if already_in_dest:
            lines = [
                (
                    f"Already in destination: {already_in_dest} file name(s) "
                    f"(removed from copy list)."
                ),
                f"Remaining to copy: {remaining}.",
            ]
        else:
            lines = [
                "Already in destination: 0 (no listed names found there).",
                f"Remaining to copy: {remaining}.",
            ]

        if csv_path is not None and csv_updated:
            lines.append(
                f"CSV updated: removed {already_in_dest} row(s); "
                f"wrote {remaining} path(s) to:\n{csv_path.resolve()}"
            )
        elif csv_path is not None and already_in_dest:
            lines.append(f"CSV not modified: {csv_path.resolve()}")
        elif already_in_dest:
            lines.append(
                "CSV not updated — enter a path under Save list (CSV) to rewrite the file."
            )
        else:
            lines.append("CSV not modified.")

        self.pre_copy_status_var.set("\n".join(lines))

    def _browse_search_dir(self) -> None:
        path = filedialog.askdirectory(title="Select directory to search")
        if path:
            self.search_dir_var.set(path)

    def _browse_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.csv_path_var.set(path)

    def _browse_copy_dest(self) -> None:
        path = filedialog.askdirectory(title="Select destination for copied files")
        if path:
            self.copy_dest_var.set(path)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.search_btn.configure(state=state)
        self.copy_btn.configure(state=state if self._search_results else tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)
        if not busy and self._search_results:
            self.save_csv_btn.configure(state=tk.NORMAL)

    def _request_cancel(self) -> None:
        self._cancel_event.set()
        self.results_label_var.set("Cancelling…")

    def _run_search(self) -> None:
        if self._busy or self._search_thread is not None:
            return

        root_text = self.search_dir_var.get().strip()
        if not root_text:
            messagebox.showwarning("Missing input", "Enter a directory to search.")
            return

        batch_settings = self._parse_batch_settings()
        if batch_settings is None:
            return
        batch_size, batch_pause, progress_every = batch_settings

        root_path = Path(root_text)
        pattern = self.pattern_var.get().strip()
        mode: MatchMode = (
            "regex" if self.match_mode_var.get() == "regex" else "glob"
        )

        self._cancel_event.clear()
        self._active_operation = "search"
        self._set_busy(True)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(12)
        self.progress_detail_var.set("Searching…")
        self.current_file_var.set("Scanned: 0  |  Matched: 0")
        self.results_label_var.set("Searching…")

        def worker() -> None:
            cancelled = False
            matches: list[Path] = []

            def on_progress(p: SearchProgress) -> None:
                self.after(0, lambda: self._update_search_progress(p))

            try:
                matches = find_matching_files(
                    root_path,
                    pattern,
                    mode,
                    recursive=self.recursive_var.get(),
                    should_cancel=self._cancel_event.is_set,
                    on_progress=on_progress,
                    batch_size=batch_size,
                    batch_pause_seconds=batch_pause if batch_size > 0 else 0.0,
                    progress_every=progress_every,
                )
            except (ValueError, NotADirectoryError, OSError) as exc:
                self.after(0, lambda: messagebox.showerror("Search failed", str(exc)))
                self.after(0, self._search_finished)
                return

            cancelled = self._cancel_event.is_set()
            self.after(
                0,
                lambda: self._search_complete(matches, cancelled),
            )

        self._search_thread = threading.Thread(target=worker, daemon=True)
        self._search_thread.start()

    def _update_search_progress(self, p: SearchProgress) -> None:
        self.progress_detail_var.set("Searching…")
        self.current_file_var.set(
            f"Scanned: {p.scanned}  |  Matched: {p.matched}  |  In: {p.current_dir}"
        )

    def _search_complete(self, matches: list[Path], cancelled: bool) -> None:
        self._search_results = matches
        self._reset_pre_copy_status()
        self._refresh_results_list()

        count = len(matches)
        if cancelled:
            self.results_label_var.set(f"Search cancelled — found {count} file(s) so far.")
        else:
            self.results_label_var.set(f"Found {count} file(s).")

        self.save_csv_btn.configure(state=tk.NORMAL if count else tk.DISABLED)
        self.copy_btn.configure(state=tk.NORMAL if count else tk.DISABLED)

        csv_text = self.csv_path_var.get().strip()
        if csv_text and count and not cancelled:
            try:
                save_paths_csv(matches, Path(csv_text))
                messagebox.showinfo(
                    "CSV saved",
                    f"Wrote {count} path(s) to:\n{Path(csv_text).resolve()}",
                )
            except OSError as exc:
                messagebox.showerror("CSV save failed", str(exc))

        self._search_finished()

    def _search_finished(self) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(0.0)
        self.progress_detail_var.set(
            "Total: 0  |  Copied: 0  |  Skipped: 0  |  Failed: 0  |  0.0%"
        )
        self.current_file_var.set("Current file: —")
        self._search_thread = None
        self._active_operation = None
        self._cancel_event.clear()
        self._set_busy(False)

    def _refresh_results_list(self) -> None:
        self.results_list.delete(0, tk.END)
        for path in self._search_results[:500]:
            self.results_list.insert(tk.END, str(path))
        if len(self._search_results) > 500:
            self.results_list.insert(
                tk.END, f"… and {len(self._search_results) - 500} more (see CSV)"
            )

    def _save_csv(self) -> None:
        if not self._search_results:
            messagebox.showwarning("No results", "Run a search first.")
            return
        csv_text = self.csv_path_var.get().strip()
        if not csv_text:
            self._browse_csv()
            csv_text = self.csv_path_var.get().strip()
        if not csv_text:
            return
        try:
            save_paths_csv(self._search_results, Path(csv_text))
            messagebox.showinfo(
                "CSV saved",
                f"Wrote {len(self._search_results)} path(s) to:\n{Path(csv_text).resolve()}",
            )
        except OSError as exc:
            messagebox.showerror("CSV save failed", str(exc))

    def _start_copy(self) -> None:
        if self._busy or self._copy_thread is not None:
            return
        if not self._search_results:
            messagebox.showwarning("No files", "Run a search first.")
            return

        dest_text = self.copy_dest_var.get().strip()
        if not dest_text:
            messagebox.showwarning("Missing input", "Enter a destination folder for copies.")
            return

        batch_settings = self._parse_batch_settings()
        if batch_settings is None:
            return
        batch_size, batch_pause, progress_every = batch_settings

        dest = Path(dest_text)
        sources, already_in_dest = filter_sources_not_in_dest(
            self._search_results, dest
        )
        already_count = len(already_in_dest)
        csv_text = self.csv_path_var.get().strip()
        csv_path = Path(csv_text) if csv_text else None
        csv_updated = False

        if already_in_dest:
            self._search_results = sources
            self._refresh_results_list()
            self.results_label_var.set(
                f"{len(sources)} file(s) to copy "
                f"({already_count} already in destination, removed from list)."
            )
            if csv_path is not None:
                try:
                    save_paths_csv(sources, csv_path)
                    csv_updated = True
                except OSError as exc:
                    self._set_pre_copy_status(
                        already_in_dest=already_count,
                        remaining=len(sources),
                        csv_path=csv_path,
                        csv_updated=False,
                    )
                    messagebox.showerror("CSV update failed", str(exc))
                    return

        self._set_pre_copy_status(
            already_in_dest=already_count,
            remaining=len(sources),
            csv_path=csv_path,
            csv_updated=csv_updated,
        )

        if not sources:
            messagebox.showinfo(
                "Nothing to copy",
                "Every listed file name already exists in the destination folder.",
            )
            return

        self._cancel_event.clear()
        self._active_operation = "copy"
        self._set_busy(True)
        self.progress_var.set(0.0)
        self.progress_detail_var.set(
            "Total: {0}  |  Copied: 0  |  Skipped: 0  |  Failed: 0  |  0.0%".format(
                len(sources)
            )
        )
        self.current_file_var.set("Current file: —")

        def worker() -> None:
            def on_progress(p: CopyProgress) -> None:
                self.after(0, lambda: self._update_progress(p))

            try:
                copied, skipped, failed = copy_file_list(
                    sources,
                    dest,
                    on_progress,
                    batch_size=batch_size,
                    batch_pause_seconds=batch_pause if batch_size > 0 else 0.0,
                    progress_every=progress_every,
                    should_cancel=self._cancel_event.is_set,
                )
            except OSError as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror("Copy failed", str(exc)),
                )
                self.after(0, self._copy_finished)
                return

            cancelled = self._cancel_event.is_set()
            if cancelled:
                summary = (
                    f"Copy cancelled.\n"
                    f"Copied: {copied}, skipped: {skipped}, failed: {failed}"
                )
                title = "Copy cancelled"
            else:
                summary = f"Copied: {copied}, skipped: {skipped}, failed: {failed}"
                title = "Copy complete"

            self.after(
                0,
                lambda: messagebox.showinfo(title, summary),
            )
            self.after(0, self._copy_finished)

        self._copy_thread = threading.Thread(target=worker, daemon=True)
        self._copy_thread.start()

    def _update_progress(self, p: CopyProgress) -> None:
        self.progress_var.set(p.percent)
        self.progress_detail_var.set(
            f"Total: {p.total}  |  Copied: {p.copied}  |  "
            f"Skipped: {p.skipped}  |  Failed: {p.failed}  |  {p.percent:.1f}%"
        )
        if p.current_name:
            self.current_file_var.set(f"Current file: {p.current_name}")
        else:
            self.current_file_var.set("Current file: —")

    def _copy_finished(self) -> None:
        self._copy_thread = None
        self._active_operation = None
        self._cancel_event.clear()
        self._set_busy(False)
        if self._search_results:
            self.copy_btn.configure(state=tk.NORMAL)


def main() -> None:
    """Launch the application."""
    app = FileTypeCopierApp()
    app.mainloop()


if __name__ == "__main__":
    main()
