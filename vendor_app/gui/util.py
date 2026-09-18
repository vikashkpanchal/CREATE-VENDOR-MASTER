"""Small, generic Tk helpers shared across tabs."""


def debounce(widget, state_attr: str, delay_ms: int, fn):
    """Schedule `fn` after `delay_ms` of inactivity, canceling whatever call
    was previously pending under `state_attr` on `widget`.

    Used on live-filter search boxes: without this, a Treeview holding many
    rows gets fully cleared and rebuilt on every single keystroke, which is
    the kind of thing that reads as "the app is lagging" while typing.
    """
    pending_id = getattr(widget, state_attr, None)
    if pending_id is not None:
        widget.after_cancel(pending_id)
    setattr(widget, state_attr, widget.after(delay_ms, fn))


def window_scaling(window) -> float:
    """CustomTkinter's window-scaling factor for `window`, or 1.0.

    On a Windows laptop set to 125% or 150% display scaling, CustomTkinter
    multiplies every geometry string it is handed by this factor. A window
    asked for 1286x678 on a 1366x768 screen is then created 1929 pixels
    wide - a third of it, including whatever sits on the right-hand side,
    lands off the edge of the display with no way to reach it.
    """
    try:
        from customtkinter.windows.widgets.scaling import ScalingTracker
        return float(ScalingTracker.get_window_scaling(window))
    except Exception:
        return 1.0


def fit_on_screen(window, preferred_w, preferred_h, min_w=0, min_h=0,
                  margin_w=80, margin_h=90, y_divisor=3):
    """Size and centre `window` so it always fits the display it opens on.

    `preferred_w` / `preferred_h` are DESIGN pixels - the size the contents
    were laid out for at 100%. Two different scalings then apply to them:

      * widget scaling makes the contents bigger, so a window drawn at 150%
        genuinely needs half as much room again to hold the same fields;
      * window scaling multiplies whatever geometry string it is handed, so
        the figure passed to geometry() has to be divided by it first.

    Both matter. Sizing the window in raw screen pixels while its contents
    were 1.5x bigger is what crushed the CC dialog's address field to two
    pixels of height and left it unmapped - focus could not land in a field
    that was not really there, so the caret never appeared and every
    keystroke was thrown away.

    Returns the (width, height) actually applied, in real screen pixels.
    """
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    scale = window_scaling(window) or 1.0

    # What the contents need on this display, at this scaling...
    wanted_w, wanted_h = preferred_w * scale, preferred_h * scale
    floor_w = (min_w or preferred_w) * scale
    floor_h = (min_h or preferred_h) * scale

    # ...clamped to the display, which always wins: a window bigger than the
    # screen puts its own buttons out of reach.
    width = min(wanted_w, max(floor_w, screen_w - margin_w), screen_w)
    height = min(wanted_h, max(floor_h, screen_h - margin_h), screen_h)

    window.geometry(
        f"{int(width / scale)}x{int(height / scale)}"
        f"+{max(0, int(screen_w - width) // 2)}"
        f"+{max(0, int(screen_h - height) // y_divisor)}"
    )
    if min_w or min_h:
        window.minsize(int(min(floor_w, width) / scale), int(min(floor_h, height) / scale))
    return int(width), int(height)


def grow_to_fit(window, margin_w=80, margin_h=90, y_divisor=3):
    """Grow `window` to the size its contents actually ask for.

    fit_on_screen sizes a window from figures written when it was designed.
    Those figures go stale the moment a field is added, a label wraps onto a
    third line, or the display is at 125% - and a window an inch too short
    does not scroll: Tk simply stops giving room to whatever is packed last,
    which arrives on screen as a field one pixel high that cannot be clicked
    into or typed in. That is the same failure the CC address box had.

    So the window is measured once its contents exist, and grown to what they
    need. It is never shrunk, and never grown past the display: the screen
    still wins, because a window larger than it puts its own buttons out of
    reach. Call it at the end of __init__, after the fields are built.

    Returns the (width, height) in force afterwards, in real screen pixels.
    """
    window.update_idletasks()
    scale = window_scaling(window) or 1.0
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()

    # reqwidth/reqheight are what the packed contents ask for, in real
    # pixels with widget scaling already applied - so they are compared with
    # the window's real size, and only the geometry string is un-scaled.
    width = min(max(window.winfo_width(), window.winfo_reqwidth()),
                max(1, screen_w - margin_w))
    height = min(max(window.winfo_height(), window.winfo_reqheight()),
                 max(1, screen_h - margin_h))
    window.geometry(
        f"{int(width / scale)}x{int(height / scale)}"
        f"+{max(0, int(screen_w - width) // 2)}"
        f"+{max(0, int(screen_h - height) // y_divisor)}"
    )
    return int(width), int(height)


def claim_focus(window, widget=None, tries: int = 8, delay_ms: int = 60):
    """Put the caret in `widget` and keep it there while the window settles.

    A single focus_set() on a freshly created CTkToplevel is not enough on
    Windows. CustomTkinter recolours the title bar by WITHDRAWING the window,
    redrawing it and deiconifying it again a few milliseconds later, restores
    focus to whatever was focused before the dialog existed (10ms), and sets
    the window icon later still (200ms). Any focus claimed before that dance
    finishes is undone by it, and the dialog ends up with the window focused
    but no field inside it - so the caret is invisible, every keystroke goes
    to the window and is discarded, and the field looks broken.

    So focus is claimed repeatedly over the first half-second, until it lands.
    It is never TAKEN from anywhere: each attempt only acts when nothing
    inside this window holds focus, so a field the user has clicked into
    themselves is left exactly as it is.
    """
    import tkinter

    target = widget if widget is not None else window

    def inside(widget):
        """Is `widget` this window, or something within it?"""
        if widget is None:
            return False
        path, root = str(widget), str(window)
        return path == root or path.startswith(root + ".")

    def attempt(remaining):
        if not window.winfo_exists():
            return
        current = window.focus_get()
        # Claim it when nothing in this window holds it: focus outside the
        # application (None), focus still back in the window the dialog was
        # opened from, or the dialog focused with no field in it - which is
        # the broken state, where the caret is invisible and every keystroke
        # is discarded.
        if current is None or current is window or not inside(current):
            try:
                window.lift()
                window.focus_force()
                target.focus_set()
            except tkinter.TclError:
                return
        else:
            return            # a field in here has it; leave it alone
        if remaining > 0:
            window.after(delay_ms, lambda: attempt(remaining - 1))

    window.after(0, lambda: attempt(tries))

    # And again whenever the window is re-entered - alt-tabbing back to a
    # dialog left the window focused and no field in it.
    def on_focus_in(_event=None):
        if window.winfo_exists() and window.focus_get() is window:
            try:
                target.focus_set()
            except tkinter.TclError:
                pass

    window.bind("<FocusIn>", on_focus_in, add="+")


def focus_on_click(widget, target, *parts):
    """Send any click on `parts` to `target`, after every other handler.

    A CTkEntry is a canvas with a real entry drawn on top of it, and a click
    landing on its border or padding hits the canvas instead of the text.
    CustomTkinter then focuses whatever was clicked - it binds that on the
    whole application - so the canvas takes the caret and typing goes
    nowhere. Binding here is not enough on its own, because an application
    binding runs AFTER a widget one; the focus is therefore claimed on the
    idle callback, once every handler for that click has had its turn.
    """
    import tkinter

    def claim(_event=None):
        def settle():
            try:
                if target.winfo_exists():
                    target.focus_set()
            except tkinter.TclError:
                pass
        widget.after_idle(settle)

    for part in (widget,) + parts:
        if part is not None:
            part.bind("<Button-1>", claim, add="+")
