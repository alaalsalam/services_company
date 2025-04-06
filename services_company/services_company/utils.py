addfrom erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import get_party_details as original_get_party_details
import frappe
def get_party_details(inv):
    frappe.msgprint("hi")
    party_type, party = "", ""

    if inv.doctype == "Sales Invoice":
        party_type = "Customer"
        party = inv.customer
    elif inv.doctype == "Service Invoice":
        party_type = "Customer"  # أو "Supplier" بناءً على منطقك
        party = inv.customer  # أو `inv.supplier` بناءً على منطقك
    else:
        return original_get_party_details(inv)

    if not party:
        frappe.throw(_("Please select {0} first").format(party_type))

    return party_type, party