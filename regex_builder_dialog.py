"""Dialog for building a filename regex from keywords and AND/OR operators."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Optional

from regex_pattern_builder import CombineOp, build_filename_regex, preview_filename_regex


class RegexBuilderDialog(tk.Toplevel):
    """Top-level window to compose a regex and apply it to the main search field."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_apply: Callable[[str], None],
        initial_extension: str = "pdf",
    ) -> None:
        """
        Args:
            master: Parent window.
            on_apply: Called with the generated regex when the user clicks Apply.
            initial_extension: Default extension field value.
        """
        super().__init__(master)
        self.title("Keyword regex builder")
        self.minsize(480, 420)
        self.geometry("560x520")
        self.transient(master)
        self._on_apply = on_apply
        self._term_vars: list[tk.StringVar] = []
        self._op_vars: list[tk.StringVar] = []
        self._rows_frame: Optional[ttk.Frame] = None

        self.extension_var = tk.StringVar(value=initial_extension)
        self.case_insensitive_var = tk.BooleanVar(value=True)
        self.preview_var = tk.StringVar(value="")

        self._build_ui()
        self._add_term_row("report")
        self._add_term_row("final")
        self._refresh_preview()
        self.grab_set()
        self.focus_set()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text="Build a regex from keywords. Operators apply left-to-right between terms.",
            wraplength=520,
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, **pad)

        self._rows_frame = ttk.Frame(outer)
        self._rows_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, **pad)

        btn_row = ttk.Frame(outer)
        btn_row.grid(row=2, column=0, columnspan=3, sticky=tk.W, **pad)
        ttk.Button(btn_row, text="Add keyword", command=self._on_add_keyword).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(btn_row, text="Remove last", command=self._on_remove_keyword).pack(
            side=tk.LEFT
        )

        opts = ttk.Frame(outer)
        opts.grid(row=3, column=0, columnspan=3, sticky=tk.W, **pad)
        ttk.Label(opts, text="Extension:").pack(side=tk.LEFT, padx=(0, 6))
        ext_entry = ttk.Entry(opts, textvariable=self.extension_var, width=10)
        ext_entry.pack(side=tk.LEFT, padx=(0, 16))
        ext_entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        ttk.Checkbutton(
            opts,
            text="Case insensitive",
            variable=self.case_insensitive_var,
            command=self._refresh_preview,
        ).pack(side=tk.LEFT)

        ttk.Label(outer, text="Generated regex:").grid(row=4, column=0, sticky=tk.NW, **pad)
        preview = ttk.Entry(outer, textvariable=self.preview_var, state="readonly")
        preview.grid(row=4, column=1, columnspan=2, sticky=tk.EW, **pad)

        actions = ttk.Frame(outer)
        actions.grid(row=5, column=0, columnspan=3, sticky=tk.E, pady=(12, 0))
        ttk.Button(actions, text="Apply to search", command=self._apply).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(actions, text="Close", command=self.destroy).pack(side=tk.LEFT)

        outer.columnconfigure(1, weight=1)

    def _rebuild_term_rows(self) -> None:
        if self._rows_frame is None:
            return
        for child in self._rows_frame.winfo_children():
            child.destroy()

        for index, term_var in enumerate(self._term_vars):
            row = ttk.Frame(self._rows_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"Keyword {index + 1}:", width=12).pack(side=tk.LEFT)
            entry = ttk.Entry(row, textvariable=term_var, width=42)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())

            if index < len(self._op_vars):
                op_row = ttk.Frame(self._rows_frame)
                op_row.pack(fill=tk.X, pady=2)
                ttk.Label(op_row, text="", width=12).pack(side=tk.LEFT)
                op_var = self._op_vars[index]
                ttk.Radiobutton(
                    op_row,
                    text="AND",
                    variable=op_var,
                    value="AND",
                    command=self._refresh_preview,
                ).pack(side=tk.LEFT, padx=(0, 12))
                ttk.Radiobutton(
                    op_row,
                    text="OR",
                    variable=op_var,
                    value="OR",
                    command=self._refresh_preview,
                ).pack(side=tk.LEFT)

    def _add_term_row(self, initial: str = "") -> None:
        if self._term_vars:
            self._op_vars.append(tk.StringVar(value="OR"))
        self._term_vars.append(tk.StringVar(value=initial))
        self._rebuild_term_rows()
        self._refresh_preview()

    def _on_add_keyword(self) -> None:
        self._add_term_row("")

    def _on_remove_keyword(self) -> None:
        if len(self._term_vars) <= 1:
            messagebox.showinfo(
                "Keyword regex builder",
                "At least one keyword is required.",
                parent=self,
            )
            return
        self._term_vars.pop()
        if self._op_vars:
            self._op_vars.pop()
        self._rebuild_term_rows()
        self._refresh_preview()

    def _collect_operators(self) -> list[CombineOp]:
        ops: list[CombineOp] = []
        for var in self._op_vars:
            value = var.get().strip().upper()
            ops.append("AND" if value == "AND" else "OR")
        return ops

    def _refresh_preview(self) -> None:
        keywords = [v.get() for v in self._term_vars]
        preview = preview_filename_regex(
            keywords,
            self._collect_operators(),
            extension=self.extension_var.get(),
            case_insensitive=self.case_insensitive_var.get(),
        )
        self.preview_var.set(preview)

    def _apply(self) -> None:
        keywords = [v.get() for v in self._term_vars]
        try:
            pattern = build_filename_regex(
                keywords,
                self._collect_operators(),
                extension=self.extension_var.get(),
                case_insensitive=self.case_insensitive_var.get(),
            )
        except ValueError as exc:
            messagebox.showwarning("Keyword regex builder", str(exc), parent=self)
            return

        self._on_apply(pattern)
        messagebox.showinfo(
            "Keyword regex builder",
            "Pattern applied. Search mode set to Regex.",
            parent=self,
        )
