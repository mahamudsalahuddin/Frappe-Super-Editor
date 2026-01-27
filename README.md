# Frappe Super Editor

🔧 **Force edit any Frappe / ERPNext field — including child tables — with optional audit ledger, restore support, and automatic cleanup.**

---

## 📌 Overview

**Frappe Super Editor** is a powerful **admin / developer utility app** for **Frappe Framework & ERPNext** that allows you to safely override restrictions and edit data that is normally:

- Read-only
- Locked after submit
- Restricted by workflow
- Hidden or validation-blocked

Unlike raw database edits, Super Editor works **inside Frappe**, respects data structure, and optionally records every change in a **custom ledger** that can be restored later.

---

## ✨ Key Features

- ✏️ Force edit **any field** on any DocType
- 📋 Full **Child Table editing**
  - Add rows
  - Edit existing rows
  - Remove rows
- 🔍 Optional **change tracking ledger**
- ♻️ **Restore previous values** from ledger (safe restore validation)
- 🧹 **Automatic cleanup** of old ledger entries (configurable days)
- 🚫 No pollution of Frappe **Version** timeline (optional)
- 🔒 Admin-only control
- 🚀 Compatible with **Frappe v15 / ERPNext v15**

---

## 🧠 How It Works

1. Adds a ✏️ **Force Edit icon** next to every editable field
2. Opens a dynamic dialog matching the field type
3. Updates data via a controlled backend API
4. Optionally logs:
   - Old value
   - New value
   - User
   - Timestamp
5. Allows **safe restore** if no further changes were made after the edit

---

## 🧩 Use Cases

- Emergency production data fixes
- Correcting historical HR / Payroll records
- Fixing legacy or imported data
- Admin-only maintenance without noisy audit logs
- Temporary corrections with rollback support

---

## 📦 Installation

```bash
bench get-app https://github.com/<your-username>/frappe-super-editor
bench --site yoursite.local install-app dev_tool

```
---
⚙️ Configuration
 - Super Editor Settings (Single DocType)
 - Field	Description
 - Enable Super Editor	Turn feature ON / OFF
 - Track Changes	Enable ledger tracking
 - Track Changes Limit (Days)	Auto-delete ledger entries after N days
