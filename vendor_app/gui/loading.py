"""Modal progress dialog for long-running work.

Imports and exports run on a background thread while this dialog stays on
screen and keeps repainting, so the window never freezes into an
unresponsive grey/black rectangle mid-upload. The worker never touches Tk;
it reports progress through a queue that the UI polls on the main thread,
which is the only thread allowed to talk to Tkinter.
"""

import queue
import threading
import traceback

import customtkinter as ctk

from vendor_app.gui import theme


class LoadingDialog(ctk.CTkToplevel):
    """Run `work(report)` off-thread behind a modal progress dialog.

    `work` is called with a `report(done, total, message="")` callable it may
    invoke as often as it likes. When it returns, `on_done(result, error)` is
    called on the main thread and the dialog closes.
    """

    POLL_MS = 60

    def __init__(self, master, title: str, work, on_done=None, subtitle: str = ""):
        super().__init__(master)
        self.work = work
        self.on_done = on_done
        self._queue = queue.Queue()
        self._result = None
        self._error = None

        self.configure(fg_color=theme.BG_SURFACE)
        self.title(title)
        screen_h, screen_w = self.winfo_screenheight(), self.winfo_screenwidth()
        width, height = 470, 186
        self.geometry(
            f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//3)}"
        )
        self.resizable(False, False)
        self.transient(master)
        # No close button / Escape: the work must finish or fail on its own.
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self._build(title, subtitle)
        self.after(60, self._start)

    def _build(self, title, subtitle):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=24, pady=22)

        ctk.CTkLabel(
            box, text=title, font=theme.h2_font(), text_color=theme.TEXT_PRIMARY, anchor="w"
        ).pack(anchor="w")

        self.status_label = ctk.CTkLabel(
            box, text=subtitle or "Please wait...", font=theme.small_font(),
            text_color=theme.TEXT_SECONDARY, anchor="w", wraplength=400, justify="left",
        )
        self.status_label.pack(anchor="w", pady=(6, 14))

        self.bar = ctk.CTkProgressBar(
            box, height=10, corner_radius=6,
            fg_color=theme.BG_INPUT, progress_color=theme.ACCENT,
        )
        self.bar.pack(fill="x")
        # Indeterminate until the worker reports a total it can measure.
        self.bar.configure(mode="indeterminate")
        self.bar.start()

        self.count_label = ctk.CTkLabel(
            box, text="", font=theme.small_font(), text_color=theme.TEXT_MUTED, anchor="w"
        )
        self.count_label.pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------ running --
    def _start(self):
        try:
            self.grab_set()
            self.lift()          # keep it above the window it is blocking
            self.focus_force()
        except Exception:
            pass

        def report(done=None, total=None, message=""):
            self._queue.put(("progress", (done, total, message)))

        def runner():
            try:
                result = self.work(report)
                self._queue.put(("done", result))
            except Exception as exc:  # surfaced to the caller, never swallowed
                self._queue.put(("error", (exc, traceback.format_exc())))

        threading.Thread(target=runner, daemon=True).start()
        self.after(self.POLL_MS, self._poll)

    def _poll(self):
        finished = False
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    self._apply_progress(*payload)
                elif kind == "done":
                    self._result, finished = payload, True
                elif kind == "error":
                    self._error, finished = payload, True
        except queue.Empty:
            pass

        if finished:
            self._finish()
        else:
            self.after(self.POLL_MS, self._poll)

    def _apply_progress(self, done, total, message):
        if message:
            self.status_label.configure(text=message)
        if done is None or not total:
            return
        if str(self.bar.cget("mode")) != "determinate":
            self.bar.stop()
            self.bar.configure(mode="determinate")
        self.bar.set(min(1.0, done / total))
        self.count_label.configure(text=f"{done:,} of {total:,} rows")

    def _finish(self):
        try:
            self.bar.stop()
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.on_done:
            error = self._error[0] if self._error else None
            self.on_done(self._result, error)


def run_with_loading(master, title, work, on_done=None, subtitle=""):
    """Convenience wrapper - see LoadingDialog."""
    return LoadingDialog(master, title, work, on_done=on_done, subtitle=subtitle)
