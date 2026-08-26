"""The two concrete master-data screens, built on RecordsScreen."""

from vendor_app.config import (
    COLUMN_WIDTHS, DISPLAY_COLUMNS, EQUIPMENT_COLUMN_WIDTHS, EQUIPMENT_KEYS,
    EQUIPMENT_LABELS, EQUIPMENT_WRAPPED_LABELS, KEYS, LABELS, STATUS_VALUES, WRAPPED_LABELS,
)
from vendor_app.export import export_equipment_to_excel, export_records_to_excel
from vendor_app.importer import load_records_from_file
from vendor_app.validators import ValidationError
from vendor_app.gui import theme
from vendor_app.gui.records_screen import RecordsScreen
from vendor_app.gui.widgets import secondary_button

VENDOR_COLUMNS = ["sr_no"] + DISPLAY_COLUMNS
EQUIPMENT_COLUMNS = ["sr_no"] + EQUIPMENT_KEYS


class VendorRecordsScreen(RecordsScreen):
    TITLE = "Vendor Records"
    SUBTITLE = ("Every vendor, directly editable. Vendor Code is the primary key "
                "and cannot be changed here.")
    IMPORT_LABEL = "Import Vendors..."
    EXPORT_PREFIX = "Export All"
    paste_keys = tuple(KEYS)
    paste_labels = LABELS
    paste_note = ("Paste vendor rows copied from Excel, one vendor per line. "
                  "There is no row limit.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        # Everything except the primary key is editable in place.
        editable = set(DISPLAY_COLUMNS) - {"vendor_code"}
        super().__init__(
            master, VENDOR_COLUMNS, WRAPPED_LABELS, COLUMN_WIDTHS,
            editable_keys=editable, on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        return self.store.search(query or "")

    def row_id(self, record):
        return record["vendor_code"]

    def row_status(self, record):
        return record.get("status", "Active")

    def row_values(self, record, index):
        values = [index]
        for key in DISPLAY_COLUMNS:
            if key == "status":
                values.append(theme.format_status(record.get("status", "Active")))
            else:
                values.append(record.get(key, ""))
        return values

    def commit(self, row_id, key, value):
        try:
            if key == "status":
                # The grid shows "🟢 Active"; store just the word.
                cleaned = str(value).split()[-1].strip().title()
                if cleaned not in STATUS_VALUES:
                    return f"Status must be one of: {', '.join(STATUS_VALUES)}"
                self.store.set_status(row_id, cleaned)
            else:
                self.store.update_field(row_id, key, value)
        except ValidationError as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        return None

    def read_file(self, path):
        return load_records_from_file(path)

    def import_rows(self, rows, progress=None):
        return self.store.bulk_upsert(rows, progress=progress)

    def export(self, records, path):
        return export_records_to_excel(records, path)

    def delete_record(self, record):
        return bool(record) and self.store.delete(record["vendor_code"])

    def extra_actions(self, parent):
        secondary_button(parent, "+ Add Vendor", self.add_vendor, width=130).pack(side="left")

    def add_vendor(self):
        from vendor_app.gui.edit_dialog import EditVendorDialog
        EditVendorDialog(self, self.store, record=None, on_saved=self._after_dialog)

    def _after_dialog(self):
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()


class EquipmentRecordsScreen(RecordsScreen):
    TITLE = "Equipment Records"
    SUBTITLE = ("Every hired machine, directly editable. A vendor referenced here "
                "is added to the vendor master automatically.")
    IMPORT_LABEL = "Import Equipment..."
    EXPORT_PREFIX = "Export All"
    paste_keys = tuple(EQUIPMENT_KEYS)
    paste_labels = EQUIPMENT_LABELS
    paste_note = ("Paste equipment rows copied from Excel, one machine per line. "
                  "Each row needs at least one of RH/RO Number, Technical ID or Reg No. "
                  "There is no row limit.")

    def __init__(self, master, store, on_data_changed=None):
        self.store = store
        super().__init__(
            master, EQUIPMENT_COLUMNS, EQUIPMENT_WRAPPED_LABELS, EQUIPMENT_COLUMN_WIDTHS,
            editable_keys=set(EQUIPMENT_KEYS), on_data_changed=on_data_changed,
        )

    def fetch(self, query):
        return self.store.search(query or "")

    def row_id(self, record):
        # Records have no single guaranteed key, so the grid uses the row's
        # identity; a stable per-object id keeps edits pointed at the right row.
        return f"eq-{id(record)}"

    def row_values(self, record, index):
        return [index] + [record.get(k, "") for k in EQUIPMENT_KEYS]

    def commit(self, row_id, key, value):
        record = self._rows.get(row_id)
        if record is None:
            return "That row is no longer available - refresh and try again."
        try:
            self.store.update_field(record, key, value)
        except ValidationError as exc:
            return str(exc)
        except Exception as exc:
            return str(exc)
        return None

    def read_file(self, path):
        from vendor_app.gui.equipment_tab import load_equipment_from_file
        return load_equipment_from_file(path)

    def import_rows(self, rows, progress=None):
        return self.store.bulk_upsert(rows, progress=progress)

    def export(self, records, path):
        return export_equipment_to_excel(records, path)

    def delete_record(self, record):
        return bool(record) and self.store.delete(record)
