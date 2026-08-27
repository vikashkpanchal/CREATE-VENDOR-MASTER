"""Editable data grid built on ttk.Treeview.

Adds the two things a master-data screen needs that a plain Treeview has
no concept of:

  * **In-place editing** - double-click (or press Enter/F2 on) a cell and an
    entry appears exactly over it. Enter commits, Escape cancels, Tab
    commits and steps to the next cell. Commits are handed to a callback so
    the store can validate them and write a change-log entry; a rejected
    edit puts the old value back and shows why.
  * **Cell selection and copy** - the active cell is outlined, the arrow
    keys walk it around the grid the way they do in Excel (Home/End jump to
    the first/last column, Ctrl+Home/End to the first/last row), and Ctrl+C
    copies either that one cell or the whole selected block as TSV, so it
    pastes straight into Excel. A right-click menu offers the same.
"""

import tkinter as tk
from tkinter import ttk

from vendor_app.gui import theme
from vendor_app.gui.style import (
    SCROLL_H_STYLE, SCROLL_V_STYLE, TREE_STYLE, apply_dark_treeview_style, row_tags,
)


class EditableTable(tk.Frame):
    """A themed, scrollable, editable table.

    `columns`      ordered column keys ("sr_no" is treated as read-only)
    `headers`      key -> wrapped header text
    `widths`       key -> pixel width
    `editable`     set of column keys the user may edit (empty = read-only)
    `on_edit`      called (row_id, column_key, new_value) -> str|None.
                   Return an error message to reject the edit, None to accept.
    `on_sort`      called (column_key) when a header is clicked
    """

    def __init__(self, master, columns, headers, widths, editable=None,
                 on_edit=None, on_sort=None, on_double_click=None, height=None,
                 double_click_edits=True, is_row_locked=None):
        super().__init__(master, bg=theme.BG_CARD, highlightthickness=1,
                         highlightbackground=theme.BORDER_SOFT)
        apply_dark_treeview_style()

        self.columns = list(columns)
        self.headers = headers
        self.editable = set(editable or ())
        self.on_edit = on_edit
        self.on_sort = on_sort
        self.on_double_click = on_double_click
        # When False, double-click is handed to on_double_click (e.g. to open
        # the full record dialog) and in-place editing is reached with
        # Enter / F2 or the right-click menu instead.
        self.double_click_edits = double_click_edits
        # Optional predicate: rows it returns True for cannot be edited at all
        # (used for de-mobbed equipment, whose records are closed).
        self.is_row_locked = is_row_locked

        self._editor = None
        self._active = None        # (row_id, column_key) of the outlined cell
        self._status_tags = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        body = tk.Frame(self, bg=theme.BG_CARD)
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        kwargs = {"columns": self.columns, "show": "headings", "style": TREE_STYLE}
        if height is not None:
            kwargs["height"] = height
        self.tree = ttk.Treeview(body, **kwargs)
        self.tree.grid(row=0, column=0, sticky="nsew")

        for key in self.columns:
            heading = {"text": headers.get(key, key), "anchor": "center"}
            if on_sort is not None:
                heading["command"] = lambda k=key: on_sort(k)
            self.tree.heading(key, **heading)
            anchor = "center" if key in ("sr_no", "vendor_code", "status") else "w"
            self.tree.column(key, width=widths.get(key, 150), minwidth=60,
                             anchor=anchor, stretch=False)

        # Highest-priority visual states first: ttk resolves overlapping tag
        # options by tag_configure() call order, not by an item's tag order.
        self.tree.tag_configure("hover", background=theme.BG_HOVER)
        self.tree.tag_configure("status-blocked", background=theme.DANGER_SOFT)
        self.tree.tag_configure("status-inactive", background=theme.BG_CARD_ALT)
        self.tree.tag_configure("odd", background=theme.BG_CARD)
        self.tree.tag_configure("even", background=theme.BG_ROW_ALT)

        vsb = ttk.Scrollbar(self, orient="vertical", style=SCROLL_V_STYLE, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(self, orient="horizontal", style=SCROLL_H_STYLE, command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # The outline that marks the active cell. A borderless frame is used
        # rather than a tag because Treeview tags colour whole rows, not cells.
        self._cell_marker = tk.Frame(
            self.tree, bg="", highlightthickness=2, highlightbackground=theme.ACCENT
        )

        self._bind_events()
        self._build_menu()

    # ------------------------------------------------------------- events --
    def _bind_events(self):
        self.tree.bind("<Button-1>", self._on_click, add="+")
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Control-c>", self._on_copy)
        self.tree.bind("<Control-C>", self._on_copy)
        self.tree.bind("<Return>", self._on_return)
        self.tree.bind("<F2>", self._on_return)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", self._on_leave)
        self.tree.bind("<Configure>", lambda e: self._place_marker())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._place_marker())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Prior>", "<Next>"):
            self.tree.bind(seq, lambda e: self._cancel_edit(), add="+")

        # Arrow keys move the ACTIVE CELL, not just the selected row, so the
        # grid reads like a spreadsheet: walk to a cell, Ctrl+C it, carry on.
        # These return "break" to stop Treeview's own row-only handling.
        self.tree.bind("<Left>", lambda e: self._move(0, -1))
        self.tree.bind("<Right>", lambda e: self._move(0, 1))
        self.tree.bind("<Up>", lambda e: self._move(-1, 0))
        self.tree.bind("<Down>", lambda e: self._move(1, 0))
        self.tree.bind("<Home>", lambda e: self._move_edge(column="first"))
        self.tree.bind("<End>", lambda e: self._move_edge(column="last"))
        self.tree.bind("<Control-Home>", lambda e: self._move_edge(row="first", column="first"))
        self.tree.bind("<Control-End>", lambda e: self._move_edge(row="last", column="last"))

    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=0, bg=theme.BG_CARD_ALT, fg=theme.TEXT_PRIMARY,
                            activebackground=theme.ACCENT, activeforeground="#ffffff",
                            bd=0, font=(theme.FONT_FAMILY, 10))
        self.menu.add_command(label="Copy cell", command=lambda: self.copy(scope="cell"))
        self.menu.add_command(label="Copy row(s)", command=lambda: self.copy(scope="rows"))
        self.menu.add_command(label="Copy row(s) with headers",
                              command=lambda: self.copy(scope="rows", with_headers=True))
        self.menu.add_separator()
        self.menu.add_command(label="Edit cell", command=self._edit_active)

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        self._cancel_edit()
        row_id = self.tree.identify_row(event.y)
        column_key = self._column_key(self.tree.identify_column(event.x))
        if row_id and column_key:
            self._active = (row_id, column_key)
            self.after(1, self._place_marker)

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        column_key = self._column_key(self.tree.identify_column(event.x))
        if not row_id or not column_key:
            return
        self._active = (row_id, column_key)
        if self.double_click_edits and column_key in self.editable and not self._locked(row_id):
            self._edit_active()
        elif self.on_double_click:
            self.on_double_click(row_id, column_key)
        return "break"

    def _on_return(self, event):
        if self._active:
            self._edit_active()
            return "break"

    def _on_right_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell":
            row_id = self.tree.identify_row(event.y)
            column_key = self._column_key(self.tree.identify_column(event.x))
            if row_id:
                if row_id not in self.tree.selection():
                    self.tree.selection_set(row_id)
                self._active = (row_id, column_key)
                self._place_marker()
        editable = bool(
            self._active and self._active[1] in self.editable and not self._locked(self._active[0])
        )
        self.menu.entryconfigure("Edit cell", state="normal" if editable else "disabled")
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _on_motion(self, event):
        row_id = self.tree.identify_row(event.y)
        if getattr(self, "_hover_row", None) == row_id:
            return
        self._restore(getattr(self, "_hover_row", None))
        if row_id:
            self.tree.item(row_id, tags=self._base_tags(row_id) + ("hover",))
        self._hover_row = row_id

    def _on_leave(self, event):
        self._restore(getattr(self, "_hover_row", None))
        self._hover_row = None

    def _restore(self, row_id):
        if row_id and self.tree.exists(row_id):
            self.tree.item(row_id, tags=self._base_tags(row_id))

    def _base_tags(self, row_id):
        stored = self._status_tags.get(row_id)
        if stored:
            return stored
        return ("even" if self.tree.index(row_id) % 2 == 0 else "odd",)

    def _column_key(self, column_ref):
        """'#3' -> the third column's key."""
        try:
            index = int(str(column_ref).lstrip("#")) - 1
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(self.columns):
            return self.columns[index]
        return None

    # -------------------------------------------------------- navigation --
    def _rows(self):
        return list(self.tree.get_children())

    def _set_active(self, row_id, column_key):
        self._active = (row_id, column_key)
        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self.tree.see(row_id)
        self._place_marker()
        return "break"

    def _move(self, row_step, column_step):
        """Walk the active cell one step, Excel-style."""
        self._cancel_edit()
        rows = self._rows()
        if not rows:
            return "break"
        if not self._active or not self.tree.exists(self._active[0]):
            return self._set_active(rows[0], self.columns[0])

        row_id, column_key = self._active
        if row_step:
            index = rows.index(row_id) if row_id in rows else 0
            row_id = rows[max(0, min(len(rows) - 1, index + row_step))]
        if column_step:
            index = self.columns.index(column_key) if column_key in self.columns else 0
            column_key = self.columns[
                max(0, min(len(self.columns) - 1, index + column_step))
            ]
        return self._set_active(row_id, column_key)

    def _move_edge(self, row=None, column=None):
        self._cancel_edit()
        rows = self._rows()
        if not rows:
            return "break"
        current_row = self._active[0] if self._active and self.tree.exists(self._active[0]) \
            else rows[0]
        current_column = self._active[1] if self._active else self.columns[0]
        if row == "first":
            current_row = rows[0]
        elif row == "last":
            current_row = rows[-1]
        if column == "first":
            current_column = self.columns[0]
        elif column == "last":
            current_column = self.columns[-1]
        return self._set_active(current_row, current_column)

    # ---------------------------------------------------------- cell mark --
    def _place_marker(self):
        if not self._active:
            self._cell_marker.place_forget()
            return
        row_id, column_key = self._active
        if not self.tree.exists(row_id):
            self._cell_marker.place_forget()
            return
        bbox = self.tree.bbox(row_id, self.columns.index(column_key))
        if not bbox:                      # scrolled out of view
            self._cell_marker.place_forget()
            return
        x, y, w, h = bbox
        self._cell_marker.place(x=x, y=y, width=w, height=h)
        self._cell_marker.lift()

    # -------------------------------------------------------------- edit --
    def _locked(self, row_id):
        return bool(self.is_row_locked and self.is_row_locked(row_id))

    def _edit_active(self):
        if not self._active:
            return
        row_id, column_key = self._active
        if column_key not in self.editable or not self.tree.exists(row_id):
            return
        if self._locked(row_id):
            from tkinter import messagebox
            messagebox.showinfo(
                "Record locked",
                "This record is de-mobbed and closed, so it can no longer be edited.\n\n"
                "If the machine has returned to site, add it again as a new record.",
                parent=self.winfo_toplevel(),
            )
            return
        bbox = self.tree.bbox(row_id, self.columns.index(column_key))
        if not bbox:
            self.tree.see(row_id)
            self.update_idletasks()
            bbox = self.tree.bbox(row_id, self.columns.index(column_key))
            if not bbox:
                return

        x, y, w, h = bbox
        current = self.tree.set(row_id, column_key)
        self._cancel_edit()

        editor = tk.Entry(
            self.tree, bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
            insertbackground=theme.TEXT_PRIMARY, relief="flat",
            highlightthickness=2, highlightbackground=theme.ACCENT,
            highlightcolor=theme.ACCENT, font=(theme.FONT_FAMILY, 10),
        )
        editor.insert(0, current)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_force()

        editor.bind("<Return>", lambda e: self._commit_edit())
        editor.bind("<KP_Enter>", lambda e: self._commit_edit())
        editor.bind("<Escape>", lambda e: self._cancel_edit())
        editor.bind("<FocusOut>", lambda e: self._commit_edit())
        editor.bind("<Tab>", lambda e: self._commit_edit(step=1))
        editor.bind("<Shift-Tab>", lambda e: self._commit_edit(step=-1))
        editor.bind("<ISO_Left_Tab>", lambda e: self._commit_edit(step=-1))

        self._editor = (editor, row_id, column_key, current)

    def _commit_edit(self, step=0):
        if not self._editor:
            return "break"
        editor, row_id, column_key, original = self._editor
        try:
            new_value = editor.get()
        except tk.TclError:
            new_value = original
        self._editor = None
        try:
            editor.destroy()
        except tk.TclError:
            pass

        if new_value != original and self.on_edit is not None:
            error = self.on_edit(row_id, column_key, new_value)
            if error:
                # Rejected: restore what was there and say why.
                if self.tree.exists(row_id):
                    self.tree.set(row_id, column_key, original)
                from tkinter import messagebox
                messagebox.showerror("Invalid value", error, parent=self.winfo_toplevel())
                return "break"
        elif new_value != original and self.tree.exists(row_id):
            self.tree.set(row_id, column_key, new_value)

        if step:
            self._step_cell(step)
        self._place_marker()
        return "break"

    def _step_cell(self, step):
        if not self._active:
            return
        row_id, column_key = self._active
        editable_columns = [c for c in self.columns if c in self.editable]
        if not editable_columns:
            return
        try:
            index = editable_columns.index(column_key)
        except ValueError:
            return
        index += step
        if 0 <= index < len(editable_columns):
            self._active = (row_id, editable_columns[index])
            self.after(1, self._edit_active)

    def _cancel_edit(self, event=None):
        if self._editor:
            editor = self._editor[0]
            self._editor = None
            try:
                editor.destroy()
            except tk.TclError:
                pass
        return "break"

    # -------------------------------------------------------------- copy --
    def _on_copy(self, event=None):
        self.copy(scope="auto")
        return "break"

    def copy(self, scope="auto", with_headers=False):
        """Copy to the clipboard as TSV, so it pastes into Excel as cells."""
        selection = self.tree.selection()

        if scope == "cell" or (scope == "auto" and self._active and len(selection) <= 1):
            if not self._active:
                return
            row_id, column_key = self._active
            if not self.tree.exists(row_id):
                return
            text = self.tree.set(row_id, column_key)
        else:
            rows = selection or ([self._active[0]] if self._active else [])
            if not rows:
                return
            lines = []
            if with_headers:
                lines.append("\t".join(
                    self.headers.get(k, k).replace("\n", " ") for k in self.columns
                ))
            for row_id in rows:
                if self.tree.exists(row_id):
                    lines.append("\t".join(
                        str(self.tree.set(row_id, k)) for k in self.columns
                    ))
            text = "\n".join(lines)

        self.clipboard_clear()
        self.clipboard_append(text)
        return text

    # -------------------------------------------------------------- rows --
    def clear(self):
        self._cancel_edit()
        self._active = None
        self._cell_marker.place_forget()
        self._status_tags.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)

    def add_row(self, index, values, iid=None, status=None):
        tags = row_tags(index, status)
        row_id = self.tree.insert("", "end", iid=iid, values=values, tags=tags)
        self._status_tags[row_id] = tags
        return row_id

    def selected_ids(self):
        return list(self.tree.selection())

    def set_headings(self, sort_key=None, sort_desc=False):
        for key in self.columns:
            text = self.headers.get(key, key)
            if key == sort_key:
                lines = text.split("\n")
                lines[-1] += " ▼" if sort_desc else " ▲"
                text = "\n".join(lines)
            self.tree.heading(key, text=text)
