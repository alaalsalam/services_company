import frappe
from frappe.utils import  cint,flt, get_link_to_form
from frappe import _, msgprint, throw
import erpnext
import traceback
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
from frappe.model.meta import get_meta


from erpnext.accounts.utils import  get_account_currency
from erpnext.assets.doctype.asset.depreciation import (
	depreciate_asset,
	get_disposal_account_and_cost_center,
	get_gl_entries_on_asset_disposal,
	get_gl_entries_on_asset_regain,
	reset_depreciation_schedule,
	reverse_depreciation_entry_made_after_disposal,
)

from frappe import _, qb, throw
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.functions import Sum
from frappe.utils import cint, cstr, flt, formatdate, get_link_to_form, getdate, nowdate

import erpnext
from erpnext.accounts.deferred_revenue import validate_service_stop_date
from erpnext.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt
from erpnext.accounts.doctype.repost_accounting_ledger.repost_accounting_ledger import (
	validate_docs_for_deferred_accounting,
	validate_docs_for_voucher_types,
)
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	check_if_return_invoice_linked_with_payment_entry,
	get_total_in_party_account_currency,
	is_overdue,
	unlink_inter_company_doc,
	update_linked_doc,
	validate_inter_company_party,
)
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import (
	get_party_tax_withholding_details,
)
from erpnext.accounts.general_ledger import (
	get_round_off_account_and_cost_center,
	make_gl_entries,
	make_reverse_gl_entries,
	merge_similar_entries,
)
from erpnext.accounts.party import get_due_date, get_party_account
from erpnext.accounts.utils import get_account_currency, get_fiscal_year
from erpnext.assets.doctype.asset.asset import is_cwip_accounting_enabled
from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account
from erpnext.buying.utils import check_on_hold_or_closed_status
from erpnext.controllers.accounts_controller import validate_account_head
from erpnext.controllers.buying_controller import BuyingController
from erpnext.stock import get_warehouse_account_map
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
	get_item_account_wise_additional_cost,
	update_billed_amount_based_on_po,
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


class CustomSalesInvoices(PurchaseInvoice):

  
    def check_if_fields_updated(self, fields_to_check, child_tables):
       
        doc_before_update = self.get_doc_before_save()

        accounting_dimensions = [*get_accounting_dimensions(), "cost_center", "project"]

        custom_fields = self.get_custom_fields_and_dimensions()

        fields_to_check += accounting_dimensions + custom_fields

        child_table_fields = self.get_child_table_fields()

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

        # دمج الحقول `child_tables`
        for child_field in child_table_fields:
            if child_field["doctype_name"] == "Purchase Invoice Item": 
                if "items" in child_tables: 
                    child_tables["items"] = tuple(set(child_tables["items"] + (child_field["field_name"],)))

        for field in fields_to_check:
            if doc_before_update.get(field) != self.get(field):
               # frappe.msgprint(f"Field '{field}' has been updated.")
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
