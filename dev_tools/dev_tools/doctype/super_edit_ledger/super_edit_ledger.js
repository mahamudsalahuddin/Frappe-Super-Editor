frappe.ui.form.on("Super Edit Ledger", {
    refresh(frm) {
        frm.add_custom_button("Restore", async () => {
            if (!frm.doc || !frm.doc.reference_doctype || !frm.doc.reference_name || !frm.doc.fieldname) {
                frappe.throw("Invalid ledger entry.");
                return;
            }

            const latest_doc = await frappe.db.get_doc(frm.doc.reference_doctype, frm.doc.reference_name);
            if (!latest_doc) {
                frappe.throw("Document not found.");
                return;
            }

            let current_value = latest_doc[frm.doc.fieldname];
            let logged_value = frm.doc.new_value;

            // 🔹 Try to parse logged_value if it's JSON
            if (typeof logged_value === "string") {
                try {
                    const parsed = JSON.parse(logged_value);
                    logged_value = parsed;
                } catch (e) {
                    // not JSON, keep as string
                }
            }

            // ===== Compare values properly =====
            const is_same = (() => {
                // both arrays
                if (Array.isArray(current_value) && Array.isArray(logged_value)) {
                    return JSON.stringify(current_value) === JSON.stringify(logged_value);
                }
                // both objects
                if (typeof current_value === "object" && current_value !== null &&
                    typeof logged_value === "object" && logged_value !== null) {
                    return JSON.stringify(current_value) === JSON.stringify(logged_value);
                }
                // both numbers (or one is string of a number)
                if (!isNaN(current_value) && !isNaN(logged_value)) {
                    return Number(current_value) === Number(logged_value);
                }
                // fallback string comparison
                return String(current_value) === String(logged_value);
            })();

            if (!is_same) {
                frappe.throw("Cannot restore. The field has been modified after this ledger entry.");
                return;
            }

            // ===== Restore value =====
            frappe.call({
                method: "dev_tools.api.force_update",
                args: {
                    doctype: frm.doc.reference_doctype,
                    name: frm.doc.reference_name,
                    fieldname: frm.doc.fieldname,
                    value: frm.doc.old_value
                },
                callback() {
                    frappe.show_alert({
                        message: "Restored successfully!",
                        indicator: "green"
                    });
                    frm.reload_doc();
                }
            });
        }, __("Actions"));
    }
});
