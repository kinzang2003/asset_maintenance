# maintenance_cost_summary.py
#
# WHAT THIS FILE IS:
# Frappe "Script Reports" have a query_report.json (config: filters, columns)
# and a matching .py file with an execute() function that returns
# (columns, data) for the report builder UI to render.
#
# WHY RAW SQL HERE (and not frappe.get_list / the ORM):
# The ORM is great for simple filtered reads (see get_open_requests_for_technician
# in maintenance_api.py for that pattern). But for aggregation across multiple
# related tables -- sums, group-by, joins -- writing it in the ORM either isn't
# possible directly or means pulling everything into Python and aggregating
# there, which is slow and doesn't scale. This is the "design and optimize
# database queries" bullet in the TOR, demonstrated for real.
#
# frappe.db.sql() sends the query straight to MariaDB and lets the database
# engine do the aggregation, using its own indexes -- much faster at scale than
# looping over ORM objects in Python.

import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Technician", "fieldname": "assigned_technician", "fieldtype": "Link",
		 "options": "Asset Technician", "width": 180},
		{"label": "Total Requests", "fieldname": "total_requests", "fieldtype": "Int", "width": 120},
		{"label": "Resolved", "fieldname": "resolved_count", "fieldtype": "Int", "width": 100},
		{"label": "Total Estimated Cost (Nu.)", "fieldname": "total_estimated", "fieldtype": "Currency", "width": 180},
		{"label": "Total Actual Cost (Nu.)", "fieldname": "total_actual", "fieldtype": "Currency", "width": 180},
		{"label": "Cost Variance (Nu.)", "fieldname": "variance", "fieldtype": "Currency", "width": 150},
	]


def get_data(filters):
	# %(param)s placeholders -- NEVER use Python f-strings/.format() to build SQL
	# with user input. frappe.db.sql's parameterized queries prevent SQL injection,
	# the same principle as parameterized queries in any framework (psycopg2, JDBC, etc).
	conditions = ""
	params = {}

	if filters.get("priority"):
		conditions += " AND mr.priority = %(priority)s"
		params["priority"] = filters["priority"]

	if filters.get("from_date"):
		conditions += " AND mr.creation >= %(from_date)s"
		params["from_date"] = filters["from_date"]

	query = f"""
		SELECT
			mr.assigned_technician AS assigned_technician,
			COUNT(*) AS total_requests,
			SUM(CASE WHEN mr.status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved_count,
			COALESCE(SUM(mr.estimated_cost), 0) AS total_estimated,
			COALESCE(SUM(mr.actual_cost), 0) AS total_actual,
			COALESCE(SUM(mr.actual_cost), 0) - COALESCE(SUM(mr.estimated_cost), 0) AS variance
		FROM `tabMaintenance Request` mr
		WHERE mr.docstatus < 2
			AND mr.assigned_technician IS NOT NULL
			{conditions}
		GROUP BY mr.assigned_technician
		ORDER BY total_requests DESC
	"""
	# `tabMaintenance Request` — Frappe prefixes every DocType's MariaDB table with
	# "tab". This is why you can write raw SQL against DocTypes at all: they really
	# are just regular InnoDB tables under the hood, DocType JSON is just the schema
	# definition used to generate/migrate them.
	#
	# docstatus < 2 excludes Cancelled documents (0=Draft, 1=Submitted, 2=Cancelled)
	# -- a very common real-world filter in Frappe reports that's easy to forget.

	return frappe.db.sql(query, params, as_dict=True)
	# as_dict=True returns [{"assigned_technician": ..., "total_requests": ...}, ...]
	# instead of raw tuples -- much easier to map onto the columns list above.


# ---------------------------------------------------------------------------
# INDEXING NOTE (part of "optimize database queries")
# ---------------------------------------------------------------------------
# This query filters/groups on assigned_technician, status, priority, and creation.
# In a production migration (a "patch", see docs/CONCEPTS.md) you'd want to confirm
# MariaDB has indexes covering these, e.g.:
#
#   ALTER TABLE `tabMaintenance Request` ADD INDEX idx_technician_status (assigned_technician, status);
#
# Frappe auto-indexes Link fields and fields marked `in_standard_filter` in the
# DocType JSON, but composite indexes for specific query patterns like this one
# are something you add deliberately once you see a report is slow -- exactly
# the kind of judgment call the TOR's "ensure system performance, scalability"
# bullet is testing for.
