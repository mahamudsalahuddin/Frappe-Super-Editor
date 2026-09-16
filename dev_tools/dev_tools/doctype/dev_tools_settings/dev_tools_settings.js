// Copyright (c) 2026, Salahuddin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dev Tools Settings", {
	refresh(frm) {
		if (!frm.doc.allow_data_exporter) {
			return;
		}
		frm.set_df_property(
			"export_doctypes",
			"description",
			__("Add DocTypes that should show Export Fixture on form/list. Set the target app (e.g. fusion_hr).")
		);
	},
});
