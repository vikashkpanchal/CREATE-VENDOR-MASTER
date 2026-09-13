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

    The size is worked out in real screen pixels and then divided by the
    window-scaling factor, because CustomTkinter multiplies it straight back
    in. Without that step the whole app grows past the edge of the screen as
    soon as Windows is set to anything above 100%.

    Returns the (width, height) actually applied, in screen pixels.
    """
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    width = min(preferred_w, max(min_w or preferred_w, screen_w - margin_w))
    height = min(preferred_h, max(min_h or preferred_h, screen_h - margin_h))
    width, height = min(width, screen_w), min(height, screen_h)

    scale = window_scaling(window) or 1.0
    window.geometry(
        f"{int(width / scale)}x{int(height / scale)}"
        f"+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // y_divisor)}"
    )
    if min_w or min_h:
        window.minsize(int(min(min_w, width) / scale), int(min(min_h, height) / scale))
    return width, height

