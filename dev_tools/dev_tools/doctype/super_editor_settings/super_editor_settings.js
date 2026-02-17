// Copyright (c) 2026, Salahuddin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Super Editor Settings", {
	refresh(frm) {
		if (frappe.session.user !== "Administrator") {
			frm.set_read_only();
			// Force read_only on every field
			frm.meta.fields.forEach((df) => {
				frm.set_df_property(df.fieldname, "read_only", 1);
			});
		}
	},
});
