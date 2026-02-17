// Author: Salahuddin Mahamud
// Date: 2026-01-21
// Description: Super Editor – Force edit any field (including child tables)

$(document).on("app_ready", function () {
    const user = frappe.session.user;

    // Only allow users with required role
    if (!frappe.user.has_role("System Manager")) {
        return;
    }

    let approver_flag = false;
    frappe.call({
        method: "dev_tools.api.get_super_editor_access",
        args: { user },
        callback(r) {
            if (r.message && r.message.length > 0) {
                r.message.forEach((allowed_user) => {
                    if (allowed_user === user) {
                        approver_flag = true;
                    }
                });
            }
            if (!approver_flag) {
                return;
            }
            enable_super_editor();
        }
    });
});

function enable_super_editor() {
    frappe.db.get_single_value("Super Editor Settings", "is_active")
        .then(enabled => {
            if (!enabled) return;

            const original_refresh = frappe.ui.form.Form.prototype.refresh;

            frappe.ui.form.Form.prototype.refresh = function () {
                original_refresh.apply(this, arguments);

                if (this.__super_edit_applied) return;
                this.__super_edit_applied = true;

                setTimeout(() => addEditIcons(this), 300);
            };
        });
}

/* ========================================================= */
/* ADD ICONS */
/* ========================================================= */

function addEditIcons(frm) {
    if (!frm?.fields_dict) return;
    if (frm.doc.doctype == "Super Editor Settings"){
        return;
    } 

    Object.entries(frm.fields_dict).forEach(([fieldname, field]) => {
        if (!field?.$wrapper) return;
        if (field.df.hidden) return;

        if (["Section Break", "Column Break", "HTML"].includes(field.df.fieldtype)) return;
        if (field.$wrapper.find(".super-edit-icon").length) return;

        const icon = $(`<span class="super-edit-icon">✏️</span>`)
            .css({
                cursor: "pointer",
                marginLeft: "6px",
                color: "#ff9800",
                fontSize: "14px"
            })
            .attr("title", "Force Edit")
            .on("click", () => {
                if (field.df.fieldtype === "Table") {
                    openChildTableEditor(frm, field);
                } else {
                    openFieldEditor(frm, fieldname, field.df);
                }
            });

        const label = field.$wrapper.find(".control-label, label").first();
        if (label.length) label.append(icon);
    });
}

/* ========================================================= */
/* FIELD EDITOR */
/* ========================================================= */

function openFieldEditor(frm, fieldname, df) {

    const dialog_field = {
        ...df,
        fieldname: "value",
        read_only: 0,
        allow_on_submit: 1,
        reqd: 0
    };

    const d = new frappe.ui.Dialog({
        title: `Force Edit: ${df.label}`,
        fields: [dialog_field],
        primary_action_label: "Update",
        primary_action(values) {

            const final_value = normalizeValue(df, values.value);

            forceUpdate(frm, fieldname, final_value);
            d.hide();
        }
    });

    d.set_value("value", frm.doc[fieldname]);
    d.show();
}

/* ========================================================= */
/* CHILD TABLE EDITOR */
/* ========================================================= */

function openChildTableEditor(frm, field) {

    const child_doctype = field.df.options;
    const meta = frappe.get_meta(child_doctype);

    // --------------------------------------------------
    // Child fields (force editable)
    // --------------------------------------------------
    const child_fields = meta.fields
        .filter(df =>
            !["Section Break", "Column Break", "HTML", "Button"].includes(df.fieldtype) &&
            !["parent", "parenttype", "parentfield", "idx"].includes(df.fieldname)
        )
        .map(df => ({
            ...df,
            read_only: 0,
            allow_on_submit: 1
        }));

    // --------------------------------------------------
    // 🔥 VERY IMPORTANT: clean rows BEFORE dialog
    // --------------------------------------------------
    const table_data = (frm.doc[field.df.fieldname] || []).map(row => {
        const clean = { ...row };

        delete clean.name;
        delete clean.parent;
        delete clean.parenttype;
        delete clean.parentfield;
        delete clean.doctype;
        delete clean.idx;
        delete clean.docstatus;
        delete clean.modified;
        delete clean.modified_by;
        delete clean.creation;
        delete clean.owner;

        clean.__islocal = 1;   // 🔥 force grid to treat as editable

        return clean;
    });

    const d = new frappe.ui.Dialog({
        title: `Force Edit: ${field.df.label}`,
        size: "extra-large",
        fields: [{
            fieldname: "table",
            fieldtype: "Table",
            label: field.df.label,
            fields: child_fields,
            data: table_data,
            editable_grid: 1,
            in_place_edit: true,
            cannot_add_rows: false,
            cannot_delete_rows: false
        }],
        primary_action_label: "Update",
        primary_action(values) {

            // Final sanitize
            const final_rows = values.table.map(row => {
                const r = { ...row };
                delete r.__islocal;
                return r;
            });

            forceUpdate(frm, field.df.fieldname, final_rows);
            d.hide();
        }
    });

    d.show();

    // 🔥 FORCE GRID REFRESH
    const grid = d.fields_dict.table.grid;
    grid.df.editable_grid = 1;
    grid.refresh();
}


/* ========================================================= */
/* VALUE NORMALIZER */
/* ========================================================= */

function normalizeValue(df, value) {

    if (value === "" || value === undefined) {

        if (df.fieldtype === "Int") return 0;
        if (["Float", "Currency", "Percent"].includes(df.fieldtype)) return 0.0;
        if (df.fieldtype === "Check") return 0;
        if (["Link", "Date", "Datetime"].includes(df.fieldtype)) return null;

        return "";
    }

    if (df.fieldtype === "Int") return parseInt(value) || 0;

    if (["Float", "Currency", "Percent"].includes(df.fieldtype))
        return parseFloat(value) || 0.0;

    if (df.fieldtype === "Check") return value ? 1 : 0;

    return value;
}

/* ========================================================= */
/* API CALL */
/* ========================================================= */

function forceUpdate(frm, fieldname, value) {

    frappe.call({
        method: "dev_tools.api.force_update",
        args: {
            doctype: frm.doctype,
            name: frm.doc.name,
            fieldname: fieldname,
            value: value
        },
        callback() {
            frappe.show_alert({
                message: "Updated successfully",
                indicator: "green"
            });
            frm.reload_doc();
        }
    });
}
