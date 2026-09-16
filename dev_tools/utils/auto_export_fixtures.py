# Copyright (c) 2026, Salahuddin and contributors
# License: MIT. See LICENSE

"""Export selected documents as app fixtures (JSON + hooks filters).

Enabled via **Dev Tools Settings** → Allow Data Exporter and the Export DocTypes
child table. Form/list Export Fixture buttons call :func:`export_as_fixture`.
Role save/delete still auto-syncs when Role is listed in that child table.
"""

from __future__ import annotations

import json
import os
import re

import frappe
from frappe.utils.data import cint

# DocTypes whose fixture filters use a field other than ``name``.
_FILTER_FIELD_BY_DOCTYPE = {
	"Role": "role_name",
	"Role Profile": "role_profile",
}


def _is_exporter_enabled() -> bool:
	"""Return True when Allow Data Exporter is on and developer mode is active."""
	if not frappe.conf.developer_mode:
		return False
	try:
		return bool(cint(frappe.db.get_single_value("Dev Tools Settings", "allow_data_exporter")))
	except Exception:
		return False


def _should_skip_auto() -> bool:
	"""Skip automatic Role export during install/migrate or when disabled."""
	return bool(
		frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_fixtures
		or frappe.flags.in_patch
		or not _is_exporter_enabled()
	)


def _filter_field(doctype: str) -> str:
	"""Return the hooks filter field used for ``doctype`` fixtures."""
	return _FILTER_FIELD_BY_DOCTYPE.get(doctype, "name")


def _fixture_path(app: str, doctype: str) -> str:
	"""Return absolute path to ``fixtures/<scrubbed_doctype>.json``."""
	return frappe.get_app_path(app, "fixtures", frappe.scrub(doctype) + ".json")


def _get_exporter_rows(doctype: str | None = None) -> list[dict]:
	"""Return configured export rows from Dev Tools Settings.

	Args:
		doctype: If set, only rows for this DocType are returned.
	"""
	if not _is_exporter_enabled():
		return []

	rows = frappe.get_all(
		"Data Exporter DocType",
		filters={
			"parent": "Dev Tools Settings",
			"parenttype": "Dev Tools Settings",
		},
		fields=["document_type", "app"],
	)
	out = []
	for row in rows:
		if not row.document_type or not row.app:
			continue
		if doctype and row.document_type != doctype:
			continue
		out.append({"document_type": row.document_type, "app": row.app})
	return out


def _identity_values(doctype: str, names: list[str]) -> list[str]:
	"""Map document names to the values stored in fixture filters."""
	field = _filter_field(doctype)
	if field == "name":
		return list(dict.fromkeys(names))

	values = []
	for name in names:
		value = frappe.db.get_value(doctype, name, field) or name
		values.append(value)
	return list(dict.fromkeys(values))


def _values_from_filters(filters, field: str) -> list[str]:
	"""Extract the ``in`` list for ``field`` from a fixture filters structure."""
	if not filters:
		return []
	for condition in filters:
		if (
			isinstance(condition, (list, tuple))
			and len(condition) >= 3
			and condition[0] == field
			and condition[1] == "in"
		):
			return list(condition[2])
	return []


def _values_from_json(app: str, doctype: str) -> list[str]:
	"""Read identity values already present in the fixture JSON file."""
	path = _fixture_path(app, doctype)
	if not os.path.exists(path):
		return []
	with open(path, encoding="utf-8") as handle:
		data = json.load(handle)
	if not isinstance(data, list):
		return []

	field = _filter_field(doctype)
	values = []
	for row in data:
		if not row:
			continue
		values.append(row.get(field) or row.get("name"))
	return [v for v in values if v]


def _get_fixture_entry(app: str, doctype: str) -> dict | str | None:
	"""Return the fixture entry for ``doctype`` from an app's hooks, if any."""
	for fixture in frappe.get_hooks("fixtures", app_name=app) or []:
		if isinstance(fixture, str) and fixture == doctype:
			return fixture
		if not isinstance(fixture, dict):
			continue
		if (fixture.get("dt") or fixture.get("doctype")) == doctype:
			return fixture
	return None


def _ensure_values_in_hooks(app: str, doctype: str, values: list[str]) -> str | None:
	"""Append missing identity values to the DocType fixture filter in hooks.py.

	Returns:
		A short status note for the caller, or None when hooks were updated cleanly.
	"""
	hooks_path = frappe.get_app_path(app, "hooks.py")
	if not os.path.exists(hooks_path):
		return f"hooks.py not found for app {app}"

	with open(hooks_path, encoding="utf-8") as handle:
		content = handle.read()

	field = _filter_field(doctype)
	dt_re = re.escape(doctype)
	field_re = re.escape(field)

	pattern = re.compile(
		rf'("dt":\s*"{dt_re}".*?"{field_re}",\s*"in",\s*\[)(.*?)(\n\s*\])',
		re.DOTALL,
	)
	match = pattern.search(content)
	if match:
		body = match.group(2)
		new_body = body
		for value in values:
			if f'"{value}"' in new_body:
				continue
			stripped = new_body.rstrip()
			if stripped and not stripped.endswith(","):
				stripped += ","
			new_body = stripped + f'\n                    "{value}",'
		if new_body != body:
			content = content[: match.start(2)] + new_body + content[match.end(2) :]
			with open(hooks_path, "w", encoding="utf-8") as handle:
				handle.write(content)
		return None

	# No editable filter block — append a new fixtures entry when possible.
	existing = _get_fixture_entry(app, doctype)
	if existing is not None:
		return (
			f"Found {doctype} in {app} hooks fixtures, but could not update its "
			f"filter list automatically. Fixture JSON was still written."
		)

	updated, ok = _append_fixture_entry(content, doctype, field, values)
	if not ok:
		return (
			f"Could not add {doctype} to {app} hooks fixtures automatically. "
			f"Fixture JSON was still written — add the fixture entry in hooks.py."
		)

	with open(hooks_path, "w", encoding="utf-8") as handle:
		handle.write(updated)
	return None


def _fixture_entry_literal(doctype: str, field: str, values: list[str], *, indent: str = "\t") -> str:
	"""Return a Python literal for one fixtures list entry."""
	inner = indent
	values_lit = ",\n".join(f'{inner}\t\t\t\t"{value}"' for value in values)
	return (
		f"{inner}{{\n"
		f'{inner}\t"dt": "{doctype}",\n'
		f'{inner}\t"filters": [\n'
		f"{inner}\t\t[\n"
		f'{inner}\t\t\t"{field}",\n'
		f'{inner}\t\t\t"in",\n'
		f"{inner}\t\t\t[\n"
		f"{values_lit},\n"
		f"{inner}\t\t\t],\n"
		f"{inner}\t\t]\n"
		f"{inner}\t],\n"
		f"{inner}}},\n"
	)


def _append_fixture_entry(
	content: str, doctype: str, field: str, values: list[str]
) -> tuple[str, bool]:
	"""Insert a new filtered fixture dict into hooks, creating ``fixtures`` if needed."""
	entry = _fixture_entry_literal(doctype, field, values)
	match = re.search(r"fixtures\s*=\s*\[", content)
	if not match:
		# First-time: app has no fixtures list yet — append one at end of hooks.py.
		block = "\n\nfixtures = [\n" + entry + "]\n"
		return content.rstrip() + block, True

	bracket_start = match.end() - 1
	depth = 0
	in_str = False
	quote = ""
	escape = False

	for index in range(bracket_start, len(content)):
		char = content[index]
		if in_str:
			if escape:
				escape = False
			elif char == "\\":
				escape = True
			elif char == quote:
				in_str = False
			continue

		if char in "'\"":
			in_str = True
			quote = char
			continue

		if char == "[":
			depth += 1
		elif char == "]":
			depth -= 1
			if depth == 0:
				return content[:index] + entry + content[index:], True

	return content, False


def _ensure_fixtures_dir(app: str) -> tuple[str, bool]:
	"""Create ``<app>/fixtures`` if missing.

	Returns:
		(directory path, True if the directory was newly created)
	"""
	fixtures_dir = frappe.get_app_path(app, "fixtures")
	created = not os.path.isdir(fixtures_dir)
	os.makedirs(fixtures_dir, exist_ok=True)
	return fixtures_dir, created


def _docname_for_value(doctype: str, value: str) -> str | None:
	"""Resolve a fixture identity value to the document name."""
	field = _filter_field(doctype)
	if field == "name":
		return value if frappe.db.exists(doctype, value) else None
	return frappe.db.get_value(doctype, {field: value}, "name")


def _load_fixture_docs(app: str, doctype: str) -> list[dict]:
	"""Load existing fixture rows from disk (empty list if missing/invalid)."""
	path = _fixture_path(app, doctype)
	if not os.path.exists(path):
		return []
	with open(path, encoding="utf-8") as handle:
		data = json.load(handle)
	return data if isinstance(data, list) else []


def _fresh_doc_dict(doctype: str, name: str) -> dict:
	"""Load a document from the database, bypassing document cache."""
	frappe.clear_document_cache(doctype, name)
	return frappe.get_doc(doctype, name).as_dict()


def _post_process_fixture_docs(docs: list[dict]) -> list[dict]:
	"""Strip volatile keys the same way Frappe ``export_json`` does."""
	del_keys = ("modified_by", "creation", "owner", "idx", "lft", "rgt")
	for doc in docs:
		for key in del_keys:
			doc.pop(key, None)
		for value in doc.values():
			if not isinstance(value, list):
				continue
			for child in value:
				if not isinstance(child, dict):
					continue
				for key in (*del_keys, "docstatus", "doctype", "modified", "name"):
					child.pop(key, None)
	return docs


def _write_fixture_file(app: str, doctype: str, docs: list[dict]) -> tuple[str, bool]:
	"""Write processed fixture docs to ``fixtures/<doctype>.json``.

	Creates the ``fixtures`` folder on first export if it does not exist.

	Returns:
		(file path, True if the fixtures directory was newly created)
	"""
	_dir, created = _ensure_fixtures_dir(app)
	path = _fixture_path(app, doctype)
	with open(path, "w", encoding="utf-8") as handle:
		handle.write(frappe.as_json(_post_process_fixture_docs(docs), ensure_ascii=False))
	return path, created


def _fetch_docs_for_values(doctype: str, values: list[str]) -> list[dict]:
	"""Fetch fresh document dicts for the given fixture identity values."""
	docs = []
	for value in values:
		name = _docname_for_value(doctype, value)
		if not name:
			frappe.throw(f"{doctype} '{value}' not found")
		docs.append(_fresh_doc_dict(doctype, name))
	return docs


def _export_fixture_json(app: str, doctype: str, values: list[str]) -> tuple[str, bool]:
	"""Update fixture JSON for ``values`` with a fresh DB snapshot.

	Rows for other identity values already in the file are kept. Matching rows
	are replaced so re-export after an update overwrites previous content.

	Returns:
		(file path, True if the fixtures directory was newly created)
	"""
	field = _filter_field(doctype)
	existing_docs = _load_fixture_docs(app, doctype)
	refresh_set = set(values)

	kept = []
	for row in existing_docs:
		identity = row.get(field) or row.get("name")
		if identity in refresh_set:
			continue
		kept.append(row)

	return _write_fixture_file(app, doctype, kept + _fetch_docs_for_values(doctype, values))


def _rewrite_fixture_json(app: str, doctype: str, values: list[str]) -> tuple[str, bool]:
	"""Replace the fixture file with a fresh export of exactly ``values``."""
	if not values:
		return _write_fixture_file(app, doctype, [])
	return _write_fixture_file(app, doctype, _fetch_docs_for_values(doctype, values))


def _sync_fixture(app: str, doctype: str, values: list[str], *, remove: bool = False) -> str:
	"""Merge values into hooks + JSON for one app/doctype pair.

	Args:
		app: Target app name.
		doctype: DocType being exported.
		values: Identity values (name / role_name / …).
		remove: If True, drop ``values`` instead of adding them.

	Returns:
		User-facing status message.
	"""
	fixture = _get_fixture_entry(app, doctype)
	existing = []
	if isinstance(fixture, dict):
		existing.extend(_values_from_filters(fixture.get("filters"), _filter_field(doctype)))
	existing.extend(_values_from_json(app, doctype))

	names = list(dict.fromkeys(existing))
	note = None
	created_dir = False

	if remove:
		remove_set = set(values)
		names = [name for name in names if name not in remove_set]
		if names:
			note = _ensure_values_in_hooks(app, doctype, names)
		_path, created_dir = _rewrite_fixture_json(app, doctype, names)
	else:
		for value in values:
			if value not in names:
				names.append(value)
		note = _ensure_values_in_hooks(app, doctype, names)
		# Always re-fetch the selected docs so updates overwrite JSON.
		_path, created_dir = _export_fixture_json(app, doctype, values)

	message = f"Exported {doctype} → {app}/fixtures/{frappe.scrub(doctype)}.json"
	if created_dir:
		message = f"{message} (created fixtures folder)"
	if note:
		message = f"{message}. Note: {note}"
	return message


@frappe.whitelist()
def get_data_exporter_config() -> dict:
	"""Return exporter enablement and configured DocType → app mappings."""
	frappe.only_for("System Manager")
	enabled = _is_exporter_enabled()
	if not enabled:
		return {"enabled": False, "doctypes": []}
	return {"enabled": True, "doctypes": _get_exporter_rows()}


@frappe.whitelist()
def export_as_fixture(doctype: str, names, app: str | None = None) -> str:
	"""Export selected documents as fixtures for the configured target app.

	Args:
		doctype: DocType of the documents.
		names: Document name or list of names (JSON string accepted).
		app: Optional app override; otherwise taken from Dev Tools Settings.
	"""
	frappe.only_for("System Manager")

	if not frappe.conf.developer_mode:
		frappe.throw("Developer mode must be enabled to export fixtures.")

	if not _is_exporter_enabled():
		frappe.throw("Enable Allow Data Exporter in Dev Tools Settings.")

	if isinstance(names, str):
		names = frappe.parse_json(names)
	if not isinstance(names, list):
		names = [names]
	names = [name for name in names if name]
	if not names:
		frappe.throw("Select at least one document to export.")

	rows = _get_exporter_rows(doctype)
	if not rows:
		frappe.throw(f"{doctype} is not configured in Dev Tools Settings → Export DocTypes.")

	if app:
		rows = [row for row in rows if row["app"] == app] or [{"document_type": doctype, "app": app}]

	if app and app not in frappe.get_installed_apps():
		frappe.throw(f"App {app} is not installed.")

	values = _identity_values(doctype, names)
	messages = []
	try:
		for row in rows:
			target_app = row["app"]
			if target_app not in frappe.get_installed_apps():
				frappe.throw(f"App {target_app} is not installed.")
			messages.append(_sync_fixture(target_app, doctype, values))
	except Exception:
		frappe.log_error(title="Export Fixture failed")
		raise

	return "\n".join(messages)


def auto_export_role(doc, method: str | None = None) -> None:
	"""On Role save/delete, sync fixtures when Role is listed in Export DocTypes."""
	if _should_skip_auto():
		return

	rows = _get_exporter_rows("Role")
	if not rows:
		return

	role_name = doc.role_name or doc.name
	try:
		for row in rows:
			_sync_fixture(
				row["app"],
				"Role",
				[role_name],
				remove=(method == "on_trash"),
			)
	except Exception:
		frappe.log_error(title="Auto-export Role fixture failed")
		raise
