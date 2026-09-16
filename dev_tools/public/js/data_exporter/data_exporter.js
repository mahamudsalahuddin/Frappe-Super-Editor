// Copyright (c) 2026, Salahuddin and contributors
// License: MIT. See LICENSE
//
// Shows Export Fixture / Export Fixtures on form and list views for DocTypes
// configured under Dev Tools Settings → Allow Data Exporter.

frappe.dev_tools = frappe.dev_tools || {};
frappe.dev_tools.export_apps_by_doctype = frappe.dev_tools.export_apps_by_doctype || {};

$(document).on("app_ready", function () {
	if (!frappe.user.has_role("System Manager")) {
		return;
	}

	// Developer mode is enforced on the server; do not block UI on boot flags.
	frappe.call({
		method: "dev_tools.utils.auto_export_fixtures.get_data_exporter_config",
		callback(r) {
			const cfg = r.message;
			if (!cfg || !cfg.enabled || !cfg.doctypes || !cfg.doctypes.length) {
				return;
			}
			enable_data_exporter(cfg.doctypes);
		},
	});
});

/**
 * Register form/list Export Fixture UI for configured DocTypes.
 * @param {Array<{document_type: string, app: string}>} rows
 */
function enable_data_exporter(rows) {
	const by_doctype = {};
	rows.forEach((row) => {
		if (!row.document_type || !row.app) {
			return;
		}
		if (!by_doctype[row.document_type]) {
			by_doctype[row.document_type] = [];
		}
		if (!by_doctype[row.document_type].includes(row.app)) {
			by_doctype[row.document_type].push(row.app);
		}
	});

	frappe.dev_tools.export_apps_by_doctype = by_doctype;

	Object.keys(by_doctype).forEach((doctype) => {
		register_form_export(doctype, by_doctype[doctype]);
		watch_listview_settings(doctype);
	});

	patch_list_view_export(() => {
		inject_export_into_current_list();
	});

	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", () => {
			setTimeout(inject_export_into_current_list, 200);
		});
	}
}

/**
 * @param {string} doctype
 * @returns {string[]|null}
 */
function get_export_apps(doctype) {
	const apps = frappe.dev_tools.export_apps_by_doctype?.[doctype];
	return apps && apps.length ? apps : null;
}

/**
 * Add Export Fixture on the form view.
 * @param {string} doctype
 * @param {string[]} apps
 */
function register_form_export(doctype, apps) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new() || frm.doctype !== doctype) {
				return;
			}

			if (frm.custom_buttons && frm.custom_buttons[__("Export Fixture")]) {
				return;
			}

			frm.add_custom_button(__("Export Fixture"), () => {
				const run = () => run_fixture_export(doctype, [frm.doc.name], apps);
				if (frm.is_dirty()) {
					frm.save().then(run);
				} else {
					run();
				}
			});
		},
	});
}

/**
 * Keep listview_settings.onload wrapped even when a DocType list JS replaces it.
 *
 * Workflow does ``frappe.listview_settings["Workflow"] = { ... }`` when its
 * list script loads, which would wipe a one-time onload assignment.
 *
 * @param {string} doctype
 */
function watch_listview_settings(doctype) {
	frappe.listview_settings = frappe.listview_settings || {};

	let current = frappe.listview_settings[doctype];
	const descriptor = Object.getOwnPropertyDescriptor(frappe.listview_settings, doctype);
	if (descriptor && descriptor.set && descriptor.get) {
		// Already watching this doctype.
		if (current) {
			wrap_list_onload(doctype, current);
		}
		return;
	}

	Object.defineProperty(frappe.listview_settings, doctype, {
		configurable: true,
		enumerable: true,
		get() {
			return current;
		},
		set(value) {
			current = value || {};
			wrap_list_onload(doctype, current);
		},
	});

	if (current) {
		wrap_list_onload(doctype, current);
	} else {
		current = {};
		wrap_list_onload(doctype, current);
	}
}

/**
 * Wrap ``onload`` so Export Fixtures controls are added when the list opens.
 * @param {string} doctype
 * @param {object} settings
 */
function wrap_list_onload(doctype, settings) {
	if (!settings || settings.__dev_tools_onload_wrapped) {
		return;
	}

	const previous = settings.onload;
	settings.__dev_tools_onload_wrapped = true;
	settings.onload = function (listview) {
		if (typeof previous === "function") {
			previous.call(this, listview);
		}
		add_list_export_controls(listview);
	};
}

/**
 * Patch ListView prototype; retry until the class is available.
 * @param {Function} [on_patched]
 */
function patch_list_view_export(on_patched) {
	const try_patch = () => {
		if (!frappe.views || !frappe.views.ListView) {
			setTimeout(try_patch, 200);
			return;
		}

		if (!frappe.views.ListView.prototype.__dev_tools_export_patched) {
			frappe.views.ListView.prototype.__dev_tools_export_patched = true;

			const original_setup_view = frappe.views.ListView.prototype.setup_view;
			frappe.views.ListView.prototype.setup_view = function () {
				original_setup_view.apply(this, arguments);
				add_list_export_controls(this);
			};

			const original_refresh = frappe.views.ListView.prototype.refresh;
			frappe.views.ListView.prototype.refresh = function () {
				const result = original_refresh.apply(this, arguments);
				const attach = () => add_list_export_controls(this);
				if (result && typeof result.then === "function") {
					return result.then((value) => {
						attach();
						return value;
					});
				}
				attach();
				return result;
			};

			const original_get_actions = frappe.views.ListView.prototype.get_actions_menu_items;
			frappe.views.ListView.prototype.get_actions_menu_items = function () {
				const items = original_get_actions.apply(this, arguments) || [];
				const apps = get_export_apps(this.doctype);
				if (!apps) {
					return items;
				}
				if (items.some((item) => item.label === __("Export Fixtures"))) {
					return items;
				}
				items.push({
					label: __("Export Fixtures"),
					action: () => export_checked_list_rows(this, apps),
					standard: true,
				});
				return items;
			};
		}

		if (typeof on_patched === "function") {
			on_patched();
		}
	};

	try_patch();
}

/**
 * Add a visible Export Fixtures control on the list page.
 * @param {object} listview
 */
function add_list_export_controls(listview) {
	if (!listview || !listview.page || !listview.doctype) {
		return;
	}

	const apps = get_export_apps(listview.doctype);
	if (!apps) {
		return;
	}

	const $page = listview.page.wrapper || $(listview.page.page_head);
	if ($page && $page.find(".dev-tools-export-fixtures-btn").length) {
		return;
	}

	const $btn = listview.page.add_inner_button(__("Export Fixtures"), () => {
		export_checked_list_rows(listview, apps);
	});

	if ($btn && $btn.addClass) {
		$btn.addClass("dev-tools-export-fixtures-btn");
	}

	if (!listview.__dev_tools_export_action_added) {
		listview.__dev_tools_export_action_added = true;
		listview.page.add_actions_menu_item(__("Export Fixtures"), () => {
			export_checked_list_rows(listview, apps);
		});
	}
}

/**
 * Inject controls into the currently open list, if it is configured.
 */
function inject_export_into_current_list() {
	const route = frappe.get_route ? frappe.get_route() : [];
	if (route[0] === "List" && route[1] && get_export_apps(route[1])) {
		if (typeof cur_list !== "undefined" && cur_list && cur_list.doctype === route[1]) {
			add_list_export_controls(cur_list);
			return;
		}
	}

	if (typeof cur_list !== "undefined" && cur_list) {
		add_list_export_controls(cur_list);
	}
}

/**
 * @param {object} listview
 * @param {string[]} apps
 */
function export_checked_list_rows(listview, apps) {
	const names = listview.get_checked_items(true);
	if (!names.length) {
		frappe.msgprint(__("Select at least one row to export."));
		return;
	}
	run_fixture_export(listview.doctype, names, apps);
}

/**
 * @param {string} doctype
 * @param {string[]} names
 * @param {string[]} apps
 */
function run_fixture_export(doctype, names, apps) {
	const export_one = (app) =>
		frappe.call({
			method: "dev_tools.utils.auto_export_fixtures.export_as_fixture",
			args: { doctype, names, app },
			freeze: true,
			freeze_message: __("Exporting fixtures..."),
		});

	Promise.all(apps.map((app) => export_one(app))).then((responses) => {
		const messages = responses
			.map((r) => r.message)
			.filter(Boolean)
			.join("\n");
		frappe.show_alert({
			message: messages || __("Fixtures exported"),
			indicator: "green",
		});
	});
}
