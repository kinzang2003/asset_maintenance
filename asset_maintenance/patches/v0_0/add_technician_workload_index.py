# patches/v0_0/add_technician_workload_index.py
#
# WHAT A "PATCH" IS:
# In Frappe, a "patch" is a one-time Python migration script -- similar in spirit
# to Django/Rails migrations, but for arbitrary data/schema fixes rather than
# purely schema changes (which Frappe usually handles automatically by diffing
# DocType JSON on `bench migrate`).
#
# Patches are for things the automatic migration CAN'T infer on its own:
# backfilling data, adding a manual index for a query pattern you only
# discovered after the report was already in use, correcting bad data, etc.
#
# To register this patch, you add its dotted path to patches.txt (see below),
# and Frappe runs it exactly once per site during `bench migrate`, tracked in
# the `tabPatch Log` table so it's never re-run accidentally.

import frappe


def execute():
	"""
	Adds a composite index to speed up the technician workload lookup used in
	AssetTechnician.validate() (frappe.db.count with assigned_technician + status
	filters) and the Maintenance Cost Summary report's GROUP BY.

	This is exactly the kind of real-world 'we shipped it, then noticed a report
	was slow, then added an index' story the TOR's performance bullet is about.
	"""
	table = "tabMaintenance Request"

	# Guard: check the index doesn't already exist before adding it, so this
	# patch is safe to re-run in dev/testing without erroring.
	existing_indexes = frappe.db.sql(f"SHOW INDEX FROM `{table}` WHERE Key_name = 'idx_technician_status'")
	if existing_indexes:
		frappe.logger("asset_maintenance").info("Index idx_technician_status already exists, skipping.")
		return

	frappe.db.sql(f"""
		ALTER TABLE `{table}`
		ADD INDEX idx_technician_status (assigned_technician, status)
	""")
	frappe.logger("asset_maintenance").info("Added composite index idx_technician_status on Maintenance Request.")
