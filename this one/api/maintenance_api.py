# maintenance_api.py
#
# WHAT THIS FILE IS:
# Custom REST API endpoints, built on top of Frappe's built-in web framework.
#
# Frappe ALREADY auto-generates a full REST API for every DocType for free, e.g.:
#   GET  /api/resource/Maintenance Request
#   GET  /api/resource/Maintenance Request/MR-2026-00001
#   POST /api/resource/Maintenance Request
#
# So why write custom endpoints at all? Because real integrations rarely want
# raw CRUD — they want a purpose-built endpoint with its own validation, response
# shape, and business logic. This file shows that pattern, which is exactly what
# the TOR means by "Build REST APIs and integrate external systems."
#
# Authentication: Frappe handles this via API Key + API Secret (sent as
# "Authorization: token <api_key>:<api_secret>" header) or session cookies.
# We don't have to write auth code ourselves — @frappe.whitelist() plugs into
# Frappe's existing auth/permission layer automatically.

import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def submit_external_request(asset_name: str, asset_tag: str = None, description: str = "",
                             priority: str = "Medium"):
	"""
	Custom endpoint an external system (e.g. an asset-tracking tool, a helpdesk bot,
	or an IoT sensor pipeline) can call to file a maintenance request without going
	through the Frappe desk UI at all.

	URL:    POST /api/method/asset_maintenance.api.maintenance_api.submit_external_request
	Auth:   Authorization: token <api_key>:<api_secret>   (sent as an HTTP header)
	Body (JSON):
		{
		  "asset_name": "Rack Fan Unit 3",
		  "asset_tag": "SRV-014",
		  "description": "Fan making grinding noise, temp rising",
		  "priority": "High"
		}

	@frappe.whitelist(allow_guest=False) means:
	  - This function is reachable over HTTP (whitelisted).
	  - allow_guest=False means the caller MUST be authenticated — this is the
	    "authentication mechanisms" bullet from the TOR in action.
	"""
	if not asset_name:
		# frappe.throw() raises a proper HTTP 417/400-style error with a JSON body
		# the caller can parse -- this IS the "data exchange formats (JSON)" bullet.
		frappe.throw(_("asset_name is required"))

	doc = frappe.get_doc({
		"doctype": "Maintenance Request",
		"asset_name": asset_name,
		"asset_tag": asset_tag,
		"description": description or "Filed via external API — no description provided.",
		"priority": priority,
	})
	doc.insert(ignore_permissions=False)
	# ignore_permissions=False (the default) means the calling API user's role
	# permissions are still enforced -- an external system authenticated as a
	# low-privilege user still can't bypass the DocType's permission rules.

	frappe.db.commit()
	# Explicit commit: Frappe normally auto-commits at the end of a web request,
	# but for whitelisted methods called via background workers or scripts, being
	# explicit avoids surprises. In a plain web request this line is often optional,
	# shown here for clarity on *why* commits matter in a request/response DB flow.

	return {
		"status": "success",
		"request_id": doc.name,
		"message": f"Maintenance request {doc.name} created and queued for triage.",
	}


@frappe.whitelist()
def get_open_requests_for_technician(technician: str):
	"""
	GET /api/method/asset_maintenance.api.maintenance_api.get_open_requests_for_technician?technician=John Wangdi

	Returns all open/in-progress requests assigned to a given technician.
	Demonstrates using frappe.get_list -- the ORM's safe query builder -- instead
	of writing raw SQL by hand for a simple filtered read (compare this with the
	raw-SQL report file, where raw SQL genuinely is the right tool).
	"""
	if not technician:
		frappe.throw(_("technician is required as a query parameter"))

	requests = frappe.get_list(
		"Maintenance Request",
		filters={
			"assigned_technician": technician,
			"status": ["in", ["Open", "In Progress"]],
		},
		fields=["name", "asset_name", "priority", "status", "creation"],
		order_by="priority desc, creation asc",
	)
	return {"technician": technician, "count": len(requests), "requests": requests}


@frappe.whitelist(methods=["POST"])
def mark_resolved(request_id: str, resolution_notes: str, actual_cost: float = 0):
	"""
	POST /api/method/asset_maintenance.api.maintenance_api.mark_resolved

	Purpose-built "action" endpoint (as opposed to a generic field update) —
	this is a common REST pattern in ERP integrations: expose a verb, not just
	raw CRUD, so external callers can't put the document into an invalid state.

	methods=["POST"] restricts this endpoint to POST only (blocks accidental
	state changes via GET, which is a REST best practice).
	"""
	doc = frappe.get_doc("Maintenance Request", request_id)

	if doc.status == "Closed":
		frappe.throw(_("This request is already closed."))

	doc.resolution_notes = resolution_notes
	doc.actual_cost = actual_cost
	doc.status = "Resolved"
	doc.save()
	frappe.db.commit()

	return {"status": "success", "request_id": doc.name, "new_status": doc.status}
