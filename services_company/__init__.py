
__version__ = '0.0.1'
import frappe 
import erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category as tax_withholding_module
def custom_get_party_details(inv):
    party_type, party = "", ""

    if inv.doctype == "Sales Invoice":
        party_type = "Customer"
        party = inv.customer
    elif inv.doctype == "Service Invoice":
        party_type = "Customer"
        party = inv.customer
    else:
        party_type = "Supplier"
        party = inv.supplier

    if not party:
        frappe.throw(_("Please select {0} first").format(party_type))

    return party_type, party

# Replace the original function with the custom function
tax_withholding_module.get_party_details = custom_get_party_details
