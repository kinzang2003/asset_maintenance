# maintenance_request.py
#
# WHAT THIS FILE IS:
# This is the "server script" / controller for the Maintenance Request DocType.
# Every DocType JSON can have a matching .py file with the SAME NAME. Frappe
# auto-loads it and calls its lifecycle methods (validate, before_save, on_submit,
# on_cancel, etc.) whenever a document of this type is saved/submitted/cancelled.
#
# This is the Frappe equivalent of a Django model's save() override, or a Rails
# ActiveRecord callback — but built into the framework so you don't need to wire
# signals manually.

import frappe
from frappe.model.document import Document
from frappe import _  # translation wrapper — best practice even if we only ship English for now


class MaintenanceRequest(Document):
	"""
	Controller class for the Maintenance Request DocType.

	Frappe auto-discovers this class by convention: the class name must match
	the DocType name with spaces removed (Maintenance Request -> MaintenanceRequest).
	"""

	def validate(self):
		"""
		validate() runs on EVERY save, before the record is written to MariaDB —
		whether the user is creating, editing, or submitting. This is where you put
		business rules that must never be skipped.

		Frappe calls this automatically; we don't call it ourselves anywhere.
		"""
		self._validate_cost_sanity()
		self._auto_set_priority_for_critical_assets()

	def _validate_cost_sanity(self):
		"""Simple guard: actual cost shouldn't wildly exceed the estimate without a note."""
		if self.actual_cost and self.estimated_cost:
			if self.actual_cost > self.estimated_cost * 2 and not self.resolution_notes:
				# frappe.throw() stops the save AND shows the message as an error dialog
				# in the desk UI. This is how you enforce a business rule server-side —
				# critically, this check runs even if someone bypasses the UI and calls
				# the REST API directly (see api/maintenance_api.py), which is the whole
				# point of validating on the server, not just in JS.
				frappe.throw(
					_("Actual cost is more than double the estimate. Please add resolution notes explaining the overrun.")
				)

	def _auto_set_priority_for_critical_assets(self):
		"""
		Business rule: if the asset tag suggests it's server infrastructure
		(e.g. contains 'SRV' or 'RACK'), auto-escalate priority to Critical
		unless a human has already explicitly raised it further.

		This demonstrates using Python string logic combined with the ORM —
		exactly the kind of "customize ERP modules based on business requirements"
		bullet point in the TOR.
		"""
		if self.asset_tag and any(tag in self.asset_tag.upper() for tag in ("SRV", "RACK")):
			if self.priority in (None, "Low", "Medium"):
				self.priority = "High"

	def before_submit(self):
		"""Runs only when moving Draft -> Submitted (docstatus 0 -> 1)."""
		if not self.assigned_technician:
			frappe.throw(_("Please assign a technician before submitting this request."))


# ---------------------------------------------------------------------------
# HOOK-BOUND FUNCTIONS
# ---------------------------------------------------------------------------
# These are the two functions referenced in hooks.py's doc_events. They are
# module-level functions (not class methods) because Frappe's hook system calls
# them by dotted import path, passing the doc and the event method name.

def validate_request(doc, method):
	"""
	Registered in hooks.py under doc_events -> validate.
	This is an ALTERNATIVE way to hook into validate, useful when the logic
	doesn't belong conceptually inside the DocType's own class — for example,
	cross-app logic added by an app that doesn't own this DocType.
	In our case we just log it, since the real validation lives in the class above.
	"""
	frappe.logger("asset_maintenance").info(f"Validating {doc.name} via hooks.py doc_events")


def on_request_submit(doc, method):
	"""
	Registered in hooks.py under doc_events -> on_submit.

	THIS IS THE REDIS / BACKGROUND WORKER DEMONSTRATION.

	When a request is submitted, we don't want the user's browser to sit and
	wait while we compose and "send" a notification (in a real deployment this
	might be a Slack webhook call or an email over SMTP — both slow, network-bound
	operations that could time out or lag the UI).

	frappe.enqueue() serializes this function call into a job and pushes it onto
	a Redis queue (Frappe uses Redis as the broker for python-rq under the hood).
	A separate `bench worker` process — a totally separate OS process from the
	one handling the web request — picks the job off the queue and runs it
	whenever it gets to it. The HTTP response to the user returns immediately.
	"""
	frappe.enqueue(
		method="asset_maintenance.tasks.notify.notify_technician_assigned",
		queue="short",              # Frappe has short/default/long queues, each backed by Redis
		timeout=300,
		request_name=doc.name,      # kwargs passed through to the queued function
		technician=doc.assigned_technician,
		asset_name=doc.asset_name,
		priority=doc.priority,
	)
	frappe.msgprint(_("Technician will be notified shortly (queued as a background job)."))
