import frappe
from frappe.utils import  cint,flt, get_link_to_form
from frappe import _, msgprint, throw
import erpnext
import traceback
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)


from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice,make_regional_gl_entries
from erpnext.accounts.utils import  get_account_currency
from erpnext.assets.doctype.asset.depreciation import (
	depreciate_asset,
	get_disposal_account_and_cost_center,
	get_gl_entries_on_asset_disposal,
	get_gl_entries_on_asset_regain,
	reset_depreciation_schedule,
	reverse_depreciation_entry_made_after_disposal,
)
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from erpnext.accounts.general_ledger import (
    make_gl_entries,
    merge_similar_entries,
)
from erpnext.accounts.party import get_party_account


from erpnext.accounts.general_ledger import (
	make_gl_entries,
	make_reverse_gl_entries,
	process_gl_map,
)
from erpnext.accounts.utils import (
	create_gain_loss_journal,
	get_account_currency,
	get_currency_precision,
	get_fiscal_years,
	validate_fiscal_year,
)
from frappe.utils import cint, comma_or, flt, getdate, nowdate
from erpnext.accounts.utils import (
	cancel_exchange_gain_loss_journal,
	get_account_currency,
	get_balance_on,
	get_outstanding_invoices,
	get_party_types_from_account_type,
)
from erpnext.accounts.party import get_party_account

from erpnext.accounts.doctype.bank_account.bank_account import (
	get_bank_account_details,
	get_default_company_bank_account,
	get_party_bank_account,
)
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
	get_party_account_based_on_invoice_discounting,
)
from erpnext.controllers.accounts_controller import AccountsController


class CustomSalesInvoice(SalesInvoice):

  
    def check_if_fields_updated(self, fields_to_check, child_tables):
        """
        تحقق مما إذا كانت الحقول أو الجداول الفرعية قد تغيرت.
        """
        doc_before_update = self.get_doc_before_save()

        accounting_dimensions = [*get_accounting_dimensions(), "cost_center", "project"]

        custom_fields = self.get_custom_fields_and_dimensions()

        fields_to_check += accounting_dimensions + custom_fields

        child_table_fields = self.get_child_table_fields()

        # إضافة الحقول من الجداول الفرعية إلى التحقق
        for child_field in child_table_fields:
            if child_field["doctype_name"] in child_tables:
                child_tables[child_field["doctype_name"]] = (
                    *child_tables.get(child_field["doctype_name"], ()),
                    child_field["field_name"],
                )

   
    def check_if_fields_updated(self, fields_to_check, child_tables):
        
        doc_before_update = self.get_doc_before_save()

        accounting_dimensions = [*get_accounting_dimensions(), "cost_center", "project"]

        custom_fields = self.get_custom_fields_and_dimensions()

        fields_to_check += accounting_dimensions + custom_fields

        child_table_fields = self.get_child_table_fields()

        for child_field in child_table_fields:
            if child_field["doctype_name"] == "Sales Invoice Item": 
                if "items" in child_tables: 
                    child_tables["items"] = tuple(set(child_tables["items"] + (child_field["field_name"],)))

        for field in fields_to_check:
            if doc_before_update.get(field) != self.get(field):
                return True

        for table in child_tables:
            if self.check_if_child_table_updated(
                doc_before_update.get(table), self.get(table), child_tables[table]
            ):
                return True

        return False

    def get_custom_fields_and_dimensions(self):
        
        custom_fields = frappe.get_all(
            "Field Properties",
            fields=["field_name"],
            filters={"parenttype": "Field Property Settings"},
        )

        custom_field_names = [field.field_name for field in custom_fields]
        return custom_field_names

    def get_child_table_fields(self):
        
        child_table_fields = frappe.get_all(
            "Field Properties",
            fields=["doctype_name", "field_name"],
            filters={
                "doctype_name": ["in", ["Sales Invoice Item", "Purchase Invoice Item"]], 
            },
        )

        return child_table_fields

    def check_if_child_table_updated(self, child_table_before_update, child_table_after_update, fields_to_check):
        
        fields_to_check = list(fields_to_check) + get_accounting_dimensions() + ["cost_center", "project"]

        for index, item in enumerate(child_table_before_update):
            for field in fields_to_check:
                if child_table_after_update[index].get(field) != item.get(field):
                    return True

        return False
# @frappe.whitelist()
# def get_currency_or_percent_fields(doctype_name):
#     try:
#         fields_with_doctype = []

#         if doctype_name == "Sales Invoice Item":
#             meta_item = frappe.get_meta("Sales Invoice Item")
#             item_fields = [
#                 {"doctype": "Sales Invoice Item", "fieldname": field.fieldname}
#                 for field in meta_item.fields
#                 if field.fieldtype in ["Currency", "Percent","float"]
#             ]
#             fields_with_doctype.extend(item_fields)

#             meta_parent = frappe.get_meta("Sales Invoice")
#             parent_fields = [
#                 {"doctype": "Sales Invoice", "fieldname": field.fieldname}
#                 for field in meta_parent.fields
#                 if field.fieldtype in ["Currency", "Percent"] or field.fieldname in ["posting_date", "due_date", "payment_schedule","base_in_words","in_words"]
#             ]
#             fields_with_doctype.extend(parent_fields)

#             payment_schedule_fields = frappe.get_meta("Payment Schedule")
#             payment_fields = [
#                 {"doctype": "Payment Schedule", "fieldname": field.fieldname}
#                 for field in payment_schedule_fields.fields
#             ]
#             fields_with_doctype.extend(payment_fields)

#         elif doctype_name == "Purchase Invoice Item":
#             meta_item = frappe.get_meta("Purchase Invoice Item")
#             item_fields = [
#                 {"doctype": "Purchase Invoice Item", "fieldname": field.fieldname}
#                 for field in meta_item.fields
#                 if field.fieldtype in ["Currency", "Percent"]
#             ]
#             fields_with_doctype.extend(item_fields)

#             meta_parent = frappe.get_meta("Purchase Invoice")
#             parent_fields = [
#                 {"doctype": "Purchase Invoice", "fieldname": field.fieldname}
#                 for field in meta_parent.fields
#                 if field.fieldtype in ["Currency", "Percent"] or field.fieldname in ["posting_date", "due_date", "payment_schedule","base_in_words","in_words"]
#             ]
#             fields_with_doctype.extend(parent_fields)

#             payment_schedule_fields = frappe.get_meta("Payment Schedule")
#             payment_fields = [
#                 {"doctype": "Payment Schedule", "fieldname": field.fieldname}
#                 for field in payment_schedule_fields.fields
#             ]
#             fields_with_doctype.extend(payment_fields)

       

#         return fields_with_doctype

#     except Exception as e:
#         frappe.log_error(f"Error fetching fields for {doctype_name}: {str(e)}", "Get Fields Error")
#         return []

@frappe.whitelist()
def get_currency_or_percent_fields(doctype_name,field_name):
    try:
        fields_with_doctype = []

        if doctype_name == "Sales Invoice Item" and field_name =="rate":
            meta_item = frappe.get_meta("Sales Invoice Item")
            item_fields = [
                {"doctype": "Sales Invoice Item", "fieldname": field.fieldname}
                for field in meta_item.fields
                if field.fieldtype in ["Currency", "Percent","float"] or field.fieldname in ["tax_amount","amount"]
            ]
            fields_with_doctype.extend(item_fields)

            meta_taxes = frappe.get_meta("Sales Taxes and Charges")
            taxes_fields = [
                {"doctype": "Sales Taxes and Charges", "fieldname": field.fieldname}
                for field in meta_taxes.fields
                if field.fieldtype in ["Currency", "Percent","float"] or field.fieldname in ["base_total","total","item_wise_tax_detail"]
            ]
            fields_with_doctype.extend(taxes_fields)


            meta_parent = frappe.get_meta("Sales Invoice")
            parent_fields = [
                {"doctype": "Sales Invoice", "fieldname": field.fieldname}
                for field in meta_parent.fields
                if field.fieldtype in ["Currency", "Percent","float"] or field.fieldname in ["base_in_words","in_words","total_by_category"]
            ]
            fields_with_doctype.extend(parent_fields)

            payment_schedule_fields = frappe.get_meta("Payment Schedule")
            payment_fields = [
                {"doctype": "Payment Schedule", "fieldname": field.fieldname}
                for field in payment_schedule_fields.fields
            ]
            fields_with_doctype.extend(payment_fields)

        elif doctype_name == "Purchase Invoice Item" and field_name =="rate":
            meta_item = frappe.get_meta("Purchase Invoice Item")
            item_fields = [
                {"doctype": "Purchase Invoice Item", "fieldname": field.fieldname}
                for field in meta_item.fields
                if field.fieldtype in ["Currency", "Percent","float"]
            ]
            fields_with_doctype.extend(item_fields)

            meta_parent = frappe.get_meta("Purchase Invoice")
            parent_fields = [
                {"doctype": "Purchase Invoice", "fieldname": field.fieldname}
                for field in meta_parent.fields
                if field.fieldtype in ["Currency", "Percent","float"] or field.fieldname in ["base_in_words","in_words","total_by_category"]
            ]
            fields_with_doctype.extend(parent_fields)

            payment_schedule_fields = frappe.get_meta("Payment Schedule")
            payment_fields = [
                {"doctype": "Payment Schedule", "fieldname": field.fieldname}
                for field in payment_schedule_fields.fields
            ]
            fields_with_doctype.extend(payment_fields)

            meta_taxes = frappe.get_meta("Purchase Taxes and Charges")
            taxes_fields = [
                {"doctype": "Purchase Taxes and Charges", "fieldname": field.fieldname}
                for field in meta_taxes.fields
                if field.fieldtype in ["Currency", "Percent","float"] or field.fieldname in ["base_total","total","item_wise_tax_detail"]
            ]
            fields_with_doctype.extend(taxes_fields)

            
        elif doctype_name == "Sales Invoice" and field_name =="posting_date":
            meta_item = frappe.get_meta("Sales Invoice")
            item_fields = [
                {"doctype": "Sales Invoice", "fieldname": field.fieldname}
                for field in meta_item.fields
                if  field.fieldname in ["posting_date", "due_date", "payment_schedule"]
            ]
            fields_with_doctype.extend(item_fields)
           
        elif doctype_name == "Purchase Invoice" and field_name =="posting_date":
            meta_item = frappe.get_meta("Purchase Invoice")
            item_fields = [
                {"doctype": "Purchase Invoice", "fieldname": field.fieldname}
                for field in meta_item.fields
                if  field.fieldname in ["posting_date", "due_date", "payment_schedule"]
            ]
          
            fields_with_doctype.extend(item_fields)    

        elif doctype_name == "Sales Invoice" and field_name == "remarks":
            meta_item = frappe.get_meta("Sales Invoice")
            item_fields = [
                {"doctype": "Sales Invoice", "fieldname": field.fieldname}
                for field in meta_item.fields
                if field.fieldname == "remarks"
            ]
            fields_with_doctype.extend(item_fields)
        elif doctype_name == "Purchase Invoice" and field_name == "remarks":
                    meta_item = frappe.get_meta("Purchase Invoice")
                    item_fields = [
                        {"doctype": "Purchase Invoice", "fieldname": field.fieldname}
                        for field in meta_item.fields
                        if field.fieldname == "remarks"
                    ]
                    fields_with_doctype.extend(item_fields) 
        elif doctype_name == "Purchase Invoice" and field_name == "bill_no":
                    meta_item = frappe.get_meta("Purchase Invoice")
                    item_fields = [
                        {"doctype": "Purchase Invoice", "fieldname": field.fieldname}
                        for field in meta_item.fields
                        if field.fieldname == "bill_no"
                    ]
                    fields_with_doctype.extend(item_fields)  
        elif doctype_name == "Journal Entry" and field_name == "posting_date":
                    meta_item = frappe.get_meta("Journal Entry")
                    item_fields = [
                        {"doctype": "Journal Entry", "fieldname": field.fieldname}
                        for field in meta_item.fields
                        if field.fieldname == "posting_date"
                    ]
                    fields_with_doctype.extend(item_fields)
        elif doctype_name == "Journal Entry Account" and field_name =="credit_in_account_currency":
            meta_item = frappe.get_meta("Journal Entry Account")
            item_fields = [
                {"doctype": "Journal Entry Account", "fieldname": field.fieldname}
                for field in meta_item.fields
                if field.fieldtype in ["Currency", "Percent","float"]
            ]
            fields_with_doctype.extend(item_fields)

            meta_parent = frappe.get_meta("Journal Entry")
            parent_fields = [
                {"doctype": "Journal Entry", "fieldname": field.fieldname}
                for field in meta_parent.fields
                if field.fieldtype in ["Currency", "Percent","float"] 
            ]
            fields_with_doctype.extend(parent_fields)
             
        
        return fields_with_doctype

    except Exception as e:
        frappe.log_error(f"Error fetching fields for {doctype_name}: {str(e)}", "Get Fields Error")
        return []


