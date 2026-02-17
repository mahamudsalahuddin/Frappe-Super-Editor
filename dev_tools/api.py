# # Author: Salahuddin Mahamud
# # Date: 2026-01-21
# # Description: Super Editor backend API

# import frappe
# import json
# from frappe.utils import cint, flt

# @frappe.whitelist()
# def force_update(doctype, name, fieldname, value):
#     frappe.only_for("System Manager")

#     doc = frappe.get_doc(doctype, name)

#     doc.flags.ignore_permissions = True
#     doc.flags.ignore_validate = True
#     doc.flags.ignore_links = True
#     doc.flags.ignore_mandatory = True
#     doc.flags.ignore_workflow = True

#     # -------------------------------------------------
#     # ✅ FIX 1: Convert JSON string → Python object
#     # -------------------------------------------------
#     if isinstance(value, str):
#         value = value.strip()
#         if value.startswith("[") or value.startswith("{"):
#             try:
#                 value = json.loads(value)
#             except Exception:
#                 pass

#     # -------------------------------------------------
#     # ✅ CHILD TABLE HANDLING
#     # -------------------------------------------------
#     if isinstance(value, list):

#         # Clear existing rows
#         doc.set(fieldname, [])

#         for row in value:
#             if not isinstance(row, dict):
#                 continue

#             # Remove system fields
#             row.pop("name", None)
#             row.pop("doctype", None)
#             row.pop("parent", None)
#             row.pop("parenttype", None)
#             row.pop("parentfield", None)
#             row.pop("__islocal", None)
#             row.pop("idx", None)

#             doc.append(fieldname, row)

#         doc.save(ignore_permissions=True)

#     # -------------------------------------------------
#     # ✅ SUBMITTED DOC (single field)
#     # -------------------------------------------------
#     elif doc.docstatus == 1:
#         doc.db_set(fieldname, value, update_modified=False)

#     # -------------------------------------------------
#     # ✅ NORMAL FIELD UPDATE
#     # -------------------------------------------------
#     else:
#         doc.set(fieldname, value)
#         doc.save(ignore_permissions=True)

#     frappe.db.commit()

#     return {"status": "success"}










# ======================================================================================================================================





# # Author: Salahuddin Mahamud
# # Date: 2026-01-21
# # Description: Super Editor backend API (Frappe v15 compatible)

# import frappe
# import json

# @frappe.whitelist()
# def force_update(doctype, name, fieldname, value):
#     frappe.only_for("System Manager")

#     doc = frappe.get_doc(doctype, name)

#     # --------------------------------------------------
#     # 🔒 HARD DISABLE ALL SIDE EFFECTS
#     # --------------------------------------------------
#     doc.flags.ignore_permissions = True
#     doc.flags.ignore_validate = True
#     doc.flags.ignore_links = True
#     doc.flags.ignore_mandatory = True
#     doc.flags.ignore_workflow = True
#     doc.flags.ignore_version = True      # timeline off
#     doc.flags.ignore_modified = True     # modified off

#     frappe.flags.ignore_version = True
#     frappe.flags.ignore_modified = True

#     # --------------------------------------------------
#     # Parse JSON safely
#     # --------------------------------------------------
#     if isinstance(value, str):
#         value = value.strip()
#         if value.startswith("[") or value.startswith("{"):
#             try:
#                 value = json.loads(value)
#             except Exception:
#                 pass

#     # --------------------------------------------------
#     # CHILD TABLE UPDATE
#     # --------------------------------------------------
#     if isinstance(value, list):

#         doc.set(fieldname, [])

#         for row in value:
#             if not isinstance(row, dict):
#                 continue

#             # Remove system-managed fields
#             row.pop("name", None)
#             row.pop("doctype", None)
#             row.pop("parent", None)
#             row.pop("parenttype", None)
#             row.pop("parentfield", None)
#             row.pop("__islocal", None)
#             row.pop("idx", None)

#             doc.append(fieldname, row)

#         doc.save(
#             ignore_permissions=True,
#             ignore_version=True
#         )

#     # --------------------------------------------------
#     # SUBMITTED DOCUMENT
#     # --------------------------------------------------
#     elif doc.docstatus == 1:
#         doc.db_set(
#             fieldname,
#             value,
#             update_modified=False,
#             notify=False
#         )

#     # --------------------------------------------------
#     # NORMAL FIELD
#     # --------------------------------------------------
#     else:
#         doc.set(fieldname, value)
#         doc.save(
#             ignore_permissions=True,
#             ignore_version=True
#         )

#     frappe.db.commit()
#     return {"status": "success"}






# ======================================================================================================================================



# Author: Salahuddin Mahamud
# Date: 2026-01-21
# Description: Super Editor backend API with custom ledger tracking

import frappe
import json
from frappe.utils import now_datetime, add_days

@frappe.whitelist()
def force_update(doctype, name, fieldname, value):
    frappe.only_for("System Manager")

    doc = frappe.get_doc(doctype, name)

    # ---------------------------------------------
    # Disable all side effects
    # ---------------------------------------------
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_workflow = True
    doc.flags.ignore_version = True
    doc.flags.ignore_modified = True

    frappe.flags.ignore_version = True
    frappe.flags.ignore_modified = True

    # ---------------------------------------------
    # Parse JSON
    # ---------------------------------------------
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("[") or value.startswith("{"):
            try:
                value = json.loads(value)
            except Exception:
                pass

    # ---------------------------------------------
    # Capture OLD VALUE
    # ---------------------------------------------
    old_value = doc.get(fieldname)

    # ---------------------------------------------
    # CHILD TABLE
    # ---------------------------------------------
    if isinstance(value, list):

        doc.set(fieldname, [])

        for row in value:
            row.pop("name", None)
            row.pop("doctype", None)
            row.pop("parent", None)
            row.pop("parenttype", None)
            row.pop("parentfield", None)
            row.pop("__islocal", None)
            row.pop("idx", None)

            doc.append(fieldname, row)

        doc.save(ignore_permissions=True, ignore_version=True)

        log_ledger(
            doctype, name, fieldname,
            "Child Table",
            old_value, value
        )

    # ---------------------------------------------
    # SUBMITTED DOC
    # ---------------------------------------------
    elif doc.docstatus == 1:
        doc.db_set(
            fieldname,
            value,
            update_modified=False,
            notify=False
        )

        log_ledger(
            doctype, name, fieldname,
            "Field",
            old_value, value
        )

    # ---------------------------------------------
    # NORMAL FIELD
    # ---------------------------------------------
    else:
        doc.set(fieldname, value)
        doc.save(ignore_permissions=True, ignore_version=True)

        log_ledger(
            doctype, name, fieldname,
            "Field",
            old_value, value
        )

    frappe.db.commit()
    return {"status": "success"}


def log_ledger(doctype, name, fieldname, change_type, old, new):
    frappe.get_doc({
        "doctype": "Super Edit Ledger",
        "reference_doctype": doctype,
        "reference_name": name,
        "fieldname": fieldname,
        "change_type": change_type,
        "old_value": frappe.as_json(old),
        "new_value": frappe.as_json(new),
        "changed_by": frappe.session.user,
        "changed_on": now_datetime(),
    }).insert(ignore_permissions=True)


def cleanup_super_edit_ledger():
    # Get number of days from settings
    days = frappe.get_value("Super Editor Settings", None, "track_changes_limit")

    # Fallback to 3 if not set
    if not days:
        days = 3

    # Ensure integer (round fractions)
    try:
        days = round(float(days))
        if days <= 0:
            days = 3
    except Exception:
        days = 3

    # Calculate cutoff date
    cutoff = add_days(now_datetime(), -days)

    # Delete old ledger entries
    frappe.db.delete(
        "Super Edit Ledger",
        {"changed_on": ["<", cutoff]}
    )

    frappe.db.commit()


@frappe.whitelist()
def get_super_editor_access(user=None):
    """Return all super approver users if session user exists in the list."""
    frappe.only_for("System Manager")

    try:
        is_active = frappe.db.get_value(
            "Super Editor Settings",
            "Super Editor Settings",
            "is_active",
        )
        if not is_active:
            return []

        # Get all users from Super Approver List child table (super_approver)
        approvers = frappe.get_all(
            "Super Approver List",
            filters={
                "parent": "Super Editor Settings",
                "parenttype": "Super Editor Settings",
            },
            pluck="user",
        )
        approvers = [u for u in approvers if u]
        # approvers.append("Administrator")

        # Return all users only if session user is in the list
        if frappe.session.user in approvers:
            return approvers
        return []
    except Exception:
        return []