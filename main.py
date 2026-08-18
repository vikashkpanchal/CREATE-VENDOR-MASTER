#!/usr/bin/env python3
"""Entry point for the Vendor Master Management System desktop application."""

import sys


def main():
    try:
        from vendor_app.gui.main_window import MainWindow
    except ImportError as exc:
        sys.stderr.write(
            "Missing dependency: {exc}\n"
            "Install requirements first:\n"
            "    pip install -r requirements.txt\n".format(exc=exc)
        )
        sys.exit(1)

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
