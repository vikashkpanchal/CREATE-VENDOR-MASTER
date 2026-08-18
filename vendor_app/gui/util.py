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
