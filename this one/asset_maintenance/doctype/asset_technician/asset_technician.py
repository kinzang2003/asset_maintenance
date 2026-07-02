# asset_technician.py
#
# A minimal controller — not every DocType needs complex logic. This shows that
# the .py file is still required (Frappe expects it to exist), but it's fine for
# it to be this small when the DocType is simple reference/master data.

import frappe
from frappe.model.document import Document


class AssetTechnician(Document):
	def validate(self):
		# Simple example of cross-record validation using the Frappe ORM's
		# query builder — count how many OPEN requests this technician already has,
		# and warn (not block) if they're overloaded.
		if not self.is_new():
			open_count = frappe.db.count(
				"Maintenance Request",
				filters={"assigned_technician": self.name, "status": ["in", ["Open", "In Progress"]]},
			)
			if open_count >= 5:
				frappe.msgprint(
					f"Note: {self.technician_name} currently has {open_count} open requests assigned.",
					indicator="orange",
					alert=True,
				)
