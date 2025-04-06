# Copyright (c) 2024, alaalsalam and contributors
# For license information, please see license.txt

# # import frappe
# from frappe.model.document import Document

# class ServiceInvoice(Document):
# 	pass

# # -------------------------
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _, msgprint, throw
from frappe.contacts.doctype.address.address import get_address_display
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.utils import add_days, cint, cstr, flt, formatdate, get_link_to_form, getdate, nowdate

import erpnext
from erpnext.accounts.deferred_revenue import validate_service_stop_date
from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
	get_loyalty_program_details_with_points,
	validate_loyalty_points,
)
from erpnext.accounts.doctype.repost_accounting_ledger.repost_accounting_ledger import (
	validate_docs_for_deferred_accounting,
	validate_docs_for_voucher_types,
)
from erpnext.accounts.doctype.tax_withholding_category.tax_withholding_category import (
	get_party_tax_withholding_details,
)
from erpnext.accounts.general_ledger import get_round_off_account_and_cost_center
from erpnext.accounts.party import get_due_date, get_party_account, get_party_details
from erpnext.accounts.utils import cancel_exchange_gain_loss_journal, get_account_currency
from erpnext.assets.doctype.asset.depreciation import (
	depreciate_asset,
	get_disposal_account_and_cost_center,
	get_gl_entries_on_asset_disposal,
	get_gl_entries_on_asset_regain,
	reset_depreciation_schedule,
	reverse_depreciation_entry_made_after_disposal,
)
from erpnext.assets.doctype.asset_activity.asset_activity import add_asset_activity
from erpnext.controllers.accounts_controller import validate_account_head
from erpnext.controllers.selling_controller import SellingController
from erpnext.projects.doctype.timesheet.timesheet import get_projectwise_timesheet_data
from erpnext.setup.doctype.company.company import update_company_current_month_sales
from erpnext.stock.doctype.delivery_note.delivery_note import update_billed_amount_based_on_so
from erpnext.stock.doctype.serial_no.serial_no import get_delivery_note_serial_no, get_serial_nos

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class ServiceInvoice(SellingController):
	

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.status_updater = [
			{
				"source_dt": "Sales Invoice Item",
				"target_field": "billed_amt",
				"target_ref_field": "amount",
				"target_dt": "Sales Order Item",
				"join_field": "so_detail",
				"target_parent_dt": "Sales Order",
				"target_parent_field": "per_billed",
				"source_field": "amount",
				"percent_join_field": "sales_order",
				"status_field": "billing_status",
				"keyword": "Billed",
				"overflow_type": "billing",
			}
		]

	def set_indicator(self):
		"""Set indicator for portal"""
		if self.outstanding_amount < 0:
			self.indicator_title = _("Credit Note Issued")
			self.indicator_color = "gray"
		elif self.outstanding_amount > 0 and getdate(self.due_date) >= getdate(nowdate()):
			self.indicator_color = "orange"
			self.indicator_title = _("Unpaid")
		elif self.outstanding_amount > 0 and getdate(self.due_date) < getdate(nowdate()):
			self.indicator_color = "red"
			self.indicator_title = _("Overdue")
		elif cint(self.is_return) == 1:
			self.indicator_title = _("Return")
			self.indicator_color = "gray"
		else:
			self.indicator_color = "green"
			self.indicator_title = _("Paid")

	def validate(self):
		# super().validate()
		self.validate_auto_set_posting_time()
		self.validate_posting_time()
		# validate cash purchase
		if self.is_paid == 1:
			self.validate_cash()
   
		self.validate_credit_to_acc()
		self.validate_debit_to_acc()
  
		self.set_against_income_account()
		self.set_against_expense_account()
  
		self.validate_accounts()
		self.add_remarks()
		self.validate_item_cost_centers()
		self.check_conversion_rate()
		self.set_status()
  


		self.set_tax_withholding()

		# self.clear_unallocated_advances("Sales Invoice Advance", "advances")
		# self.clear_unallocated_advances("Purchase Invoice Advance", "advances")


		validate_service_stop_date(self)



  
#   ala-----------------------------------
#   ala-----------------------------------

	def validate_accounts(self):
		self.validate_write_off_account()
		self.validate_account_for_change_amount()
		self.validate_income_account()
		self.validate_expense_account()

	def validate_for_repost(self):
		self.validate_write_off_account()
		self.validate_account_for_change_amount()
		self.validate_income_account()
		self.validate_expense_account()
  
		validate_docs_for_voucher_types(["Service Invoice"])
		validate_docs_for_deferred_accounting([self.name], [])


	def validate_item_cost_centers(self):
		for item in self.items:
			cost_center_company = frappe.get_cached_value("Cost Center", item.cost_center, "company")
			if cost_center_company != self.company:
				frappe.throw(
					_("Row #{0}: Cost Center {1} does not belong to company {2}").format(
						frappe.bold(item.idx), frappe.bold(item.cost_center), frappe.bold(self.company)
					)
				)

	def validate_income_account(self):
		for item in self.get("items"):
			validate_account_head(item.idx, item.income_account, self.company, "Income")

	def validate_expense_account(self):
		for item in self.get("items"):
			validate_account_head(item.idx, item.expense_account, self.company, "Expense")
   
   
	def set_tax_withholding(self):
		tax_withholding_details = get_party_tax_withholding_details(self)

		if not tax_withholding_details:
			return

		accounts = []
		tax_withholding_account = tax_withholding_details.get("account_head")

		for d in self.taxes:
			if d.account_head == tax_withholding_account:
				d.update(tax_withholding_details)
			accounts.append(d.account_head)

		if not accounts or tax_withholding_account not in accounts:
			self.append("taxes", tax_withholding_details)

		to_remove = [
			d
			for d in self.taxes
			if not d.tax_amount and d.charge_type == "Actual" and d.account_head == tax_withholding_account
		]

		for d in to_remove:
			self.remove(d)

		# calculate totals again after applying TDS
		self.calculate_taxes_and_totals()

	def before_save(self):
		self.set_account_for_mode_of_payment()
		self.set_paid_amount()

	def on_submit(self):
		self.validate_pos_paid_amount()

		if not self.auto_repeat:
			frappe.get_doc("Authorization Control").validate_approving_authority(
				self.doctype, self.company, self.base_grand_total, self
			)

		self.check_prev_docstatus()

		self.update_prevdoc_status()

		self.clear_unallocated_mode_of_payments()

		# this sequence because outstanding may get -ve
		self.make_gl_entries()

		self.check_credit_limit()

		if frappe.db.get_single_value("Selling Settings", "sales_update_frequency") == "Each Transaction":
			update_company_current_month_sales(self.company)
			self.update_project()
		update_linked_doc(self.doctype, self.name, self.inter_company_invoice_reference)


		self.process_common_party_accounting()




	def before_cancel(self):
		super().before_cancel()

	def on_cancel(self):
		check_if_return_invoice_linked_with_payment_entry(self)

		super().on_cancel()




		self.update_prevdoc_status()

		self.make_gl_entries_on_cancel()



		self.db_set("status", "Cancelled")

		if frappe.db.get_single_value("Selling Settings", "sales_update_frequency") == "Each Transaction":
			update_company_current_month_sales(self.company)
			self.update_project()


		self.ignore_linked_doctypes = (
			"GL Entry",
			"Stock Ledger Entry",
			"Repost Item Valuation",
			"Repost Payment Ledger",
			"Repost Payment Ledger Items",
			"Repost Accounting Ledger",
			"Repost Accounting Ledger Items",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
			"Payment Ledger Entry",
			"Serial and Batch Bundle",
		)

		self.delete_auto_created_batches()


	def check_credit_limit(self):
		from erpnext.selling.doctype.customer.customer import check_credit_limit

		validate_against_credit_limit = False
		bypass_credit_limit_check_at_sales_order = frappe.db.get_value(
			"Customer Credit Limit",
			filters={"parent": self.customer, "parenttype": "Customer", "company": self.company},
			fieldname=["bypass_credit_limit_check"],
		)

		if bypass_credit_limit_check_at_sales_order:
			validate_against_credit_limit = True

		for d in self.get("items"):
			if not (d.sales_order or d.delivery_note):
				validate_against_credit_limit = True
				break
		if validate_against_credit_limit:
			check_credit_limit(self.customer, self.company, bypass_credit_limit_check_at_sales_order)


	@frappe.whitelist()
	def set_missing_values(self, for_validate=False):
		pos = self.set_pos_fields(for_validate)

		if not self.debit_to:
			self.debit_to = get_party_account("Customer", self.customer, self.company)
			self.party_account_currency = frappe.db.get_value(
				"Account", self.debit_to, "account_currency", cache=True
			)
		if not self.due_date and self.customer:
			self.due_date = get_due_date(self.posting_date, "Customer", self.customer, self.company)

		super().set_missing_values(for_validate)

		print_format = pos.get("print_format") if pos else None
		if not print_format and not cint(frappe.db.get_value("Print Format", "POS Invoice", "disabled")):
			print_format = "POS Invoice"

		if pos:
			return {
				"print_format": print_format,
				"allow_edit_rate": pos.get("allow_user_to_edit_rate"),
				"allow_edit_discount": pos.get("allow_user_to_edit_discount"),
				"campaign": pos.get("campaign"),
				"allow_print_before_pay": pos.get("allow_print_before_pay"),
			}
		self.set_missing_values_supplier()

	def set_missing_values_supplier(self, for_validate=False):
		if not self.credit_to:
			self.credit_to = get_party_account("Supplier", self.supplier, self.company)
			self.party_account_currency = frappe.get_cached_value(
				"Account", self.credit_to, "account_currency"
			)
		if not self.due_date:
			self.due_date = get_due_date(
				self.posting_date, "Supplier", self.supplier, self.company, self.bill_date
			)

		tds_category = frappe.db.get_value("Supplier", self.supplier, "tax_withholding_category")
		if tds_category and not for_validate:
			self.apply_tds = 1
			self.tax_withholding_category = tds_category
			self.set_onload("supplier_tds", tds_category)

		super().set_missing_values(for_validate)
  
  
	def on_update_after_submit(self):
		if hasattr(self, "repost_required"):
			fields_to_check = [
				"additional_discount_account",
				"cash_bank_account",
				"account_for_change_amount",
				"write_off_account",
				"loyalty_redemption_account",
				"unrealized_profit_loss_account",
				"is_opening",
			]
			child_tables = {
				"items": ("income_account", "expense_account", "discount_account"),
				"taxes": ("account_head",),
			}
			self.needs_repost = self.check_if_fields_updated(fields_to_check, child_tables)
			if self.needs_repost:
				self.validate_for_repost()
				self.db_set("repost_required", self.needs_repost)

	def set_paid_amount(self):
		paid_amount = 0.0
		base_paid_amount = 0.0
		for data in self.payments:
			data.base_amount = flt(data.amount * self.conversion_rate, self.precision("base_paid_amount"))
			paid_amount += data.amount
			base_paid_amount += data.base_amount

		self.paid_amount = paid_amount
		self.base_paid_amount = base_paid_amount

	def set_account_for_mode_of_payment(self):
		for payment in self.payments:
			if not payment.account:
				payment.account = get_bank_cash_account(payment.mode_of_payment, self.company).get("account")




	def validate_debit_to_acc(self):
		if not self.debit_to:
			self.debit_to = get_party_account("Customer", self.customer, self.company)
			if not self.debit_to:
				self.raise_missing_debit_credit_account_error("Customer", self.customer)

		account = frappe.get_cached_value(
			"Account", self.debit_to, ["account_type", "report_type", "account_currency"], as_dict=True
		)

		if not account:
			frappe.throw(_("Debit To is required"), title=_("Account Missing"))

		if account.report_type != "Balance Sheet":
			msg = (
				_("Please ensure {} account is a Balance Sheet account.").format(frappe.bold("Debit To"))
				+ " "
			)
			msg += _(
				"You can change the parent account to a Balance Sheet account or select a different account."
			)
			frappe.throw(msg, title=_("Invalid Account"))

		if self.customer and account.account_type != "Receivable":
			msg = (
				_("Please ensure {} account {} is a Receivable account.").format(
					frappe.bold("Debit To"), frappe.bold(self.debit_to)
				)
				+ " "
			)
			msg += _("Change the account type to Receivable or select a different account.")
			frappe.throw(msg, title=_("Invalid Account"))

		self.party_account_currency = account.account_currency

	def clear_unallocated_mode_of_payments(self):
		self.set("payments", self.get("payments", {"amount": ["not in", [0, None, ""]]}))

		frappe.db.sql(
			"""delete from `tabSales Invoice Payment` where parent = %s
			and amount = 0""",
			self.name,
		)



	def add_remarks(self):
		if not self.remarks:
			if self.po_no and self.po_date:
				self.remarks = _("Customer  {0} Supplier {1}").format(
					self.customer, self.supplier
				)

			else:
				self.remarks = _("No Remarks")

	def validate_auto_set_posting_time(self):
		# Don't auto set the posting date and time if invoice is amended
		if self.is_new() and self.amended_from:
			self.set_posting_time = 1

		self.validate_posting_time()

	def validate_write_off_account(self):
		if flt(self.write_off_amount) and not self.write_off_account:
			self.write_off_account = frappe.get_cached_value("Company", self.company, "write_off_account")

		if flt(self.write_off_amount) and not self.write_off_account:
			msgprint(_("Please enter Write Off Account"), raise_exception=1)

	def validate_account_for_change_amount(self):
		if flt(self.change_amount) and not self.account_for_change_amount:
			msgprint(_("Please enter Account for Change Amount"), raise_exception=1)


	def check_prev_docstatus(self):
		for d in self.get("items"):
			if (
				d.sales_order
				and frappe.db.get_value("Sales Order", d.sales_order, "docstatus", cache=True) != 1
			):
				frappe.throw(_("Sales Order {0} is not submitted").format(d.sales_order))

			if (
				d.delivery_note
				and frappe.db.get_value("Delivery Note", d.delivery_note, "docstatus", cache=True) != 1
			):
				throw(_("Delivery Note {0} is not submitted").format(d.delivery_note))

	def make_gl_entries(self, gl_entries=None, from_repost=False):
		from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries

		auto_accounting_for_stock = erpnext.is_perpetual_inventory_enabled(self.company)
		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if gl_entries:
			# if POS and amount is written off, updating outstanding amt after posting all gl entries

			update_outstanding = "No" if (cint(self.is_paid) or self.write_off_account) else "Yes"

			if self.docstatus == 1:
				make_gl_entries(
					gl_entries,
					update_outstanding=update_outstanding,
					merge_entries=False,
					from_repost=from_repost,
				)

				self.make_exchange_gain_loss_journal()
			elif self.docstatus == 2:
				cancel_exchange_gain_loss_journal(frappe._dict(doctype=self.doctype, name=self.name))
				make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

			if update_outstanding == "No":
				from erpnext.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt

				update_outstanding_amt(
					self.debit_to,
					"Customer",
					self.customer,
					self.doctype,
					self.return_against if cint(self.is_return) and self.return_against else self.name,
				)
			if update_outstanding == "No":
				update_outstanding_amt(
					self.credit_to,
					"Supplier",
					self.supplier,
					self.doctype,
					self.return_against if cint(self.is_return) and self.return_against else self.name,
				)

		elif self.docstatus == 2 :
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def get_gl_entries(self, warehouse_account=None):
		from erpnext.accounts.general_ledger import merge_similar_entries

		self.negative_expense_to_be_booked = 0.0
		gl_entries = []

		
		self.make_customer_gl_entry(gl_entries)
		self.make_item_gl_entries(gl_entries)

		# self.make_tax_gl_entries2(gl_entries)
		# self.make_internal_transfer_gl_entries(gl_entries)
		self.make_supplier_gl_entry(gl_entries)
		self.make_item_gl_entries5(gl_entries)
		
		# self.make_precision_loss_gl_entry(gl_entries)
		# make_discount_gl_entries(self,gl_entries)

		self.make_payment_gl_entries(gl_entries)
		# self.make_write_off_gl_entry(gl_entries)
		# self.make_gle_for_rounding_adjustment(gl_entries)
		# # merge gl entries before adding pos entries
		# gl_entries = merge_similar_entries(gl_entries)

		# self.make_loyalty_point_redemption_gle(gl_entries)
		# # self.make_pos_gl_entries(gl_entries)

		# self.make_write_off_gl_entry(gl_entries)
		# self.make_gle_for_rounding_adjustment(gl_entries)

		return gl_entries
 #---------------------------------------------------------------------
	def make_supplier_gl_entry(self, gl_entries):
		if self.is_multiple_suppliers ==0:
		# Checked both rounding_adjustment and rounded_total
			# because rounded_total had value even before introduction of posting GLE based on rounded total
			grand_total = (
				self.rounded_total if (self.rounding_adjustment and self.rounded_total) else self.grand_total
			)
			base_grand_total = flt(
				self.base_rounded_total
				if (self.base_rounding_adjustment and self.base_rounded_total)
				else self.base_grand_total,
				self.precision("base_grand_total"),
			)

			if grand_total and not self.is_internal_transfer():
				against_voucher = self.name
				if self.is_return and self.return_against and not self.update_outstanding_for_self:
					against_voucher = self.return_against

				# Did not use base_grand_total to book rounding loss gle
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.credit_to,
							"party_type": "Supplier",
							"party": self.supplier,
							"due_date": self.due_date,
							"against": self.against_expense_account,
							"credit": self.total_buying_rate_t,
							# "credit_in_account_currency": base_grand_total
							# if self.party_account_currency == self.company_currency
							# else grand_total,
							"against_voucher": against_voucher,
							"against_voucher_type": self.doctype,
							"project": self.project,
							"cost_center": self.cost_center,
						},
						self.party_account_currency,
						item=self,
					)
				)
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.against_expense_account,
							
							"due_date": self.due_date,
							"against": self.credit_to,
							"debit": self.total_buying_rate_t,
							
							"against_voucher": against_voucher,
							"against_voucher_type": self.doctype,
							"project": self.project,
							"cost_center": self.cost_center,
						},
						self.party_account_currency,
						item=self,
					)
				)


 #---------------------------------------------------------------------
 
	def make_payment_gl_entries(self, gl_entries):
		# Make Cash GL Entries
		if cint(self.is_paid) and self.cash_bank_account and self.paid_amount:
			bank_account_currency = get_account_currency(self.cash_bank_account)
			# CASH, make payment entries
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.credit_to,
						"party_type": "Supplier",
						"party": self.supplier,
						"against": self.cash_bank_account,
						"debit": self.base_paid_amount,
						"debit_in_account_currency": self.base_paid_amount
						if self.party_account_currency == self.company_currency
						else self.paid_amount,
						"against_voucher": self.return_against
						if cint(self.is_return) and self.return_against
						else self.name,
						"against_voucher_type": self.doctype,
						"cost_center": self.cost_center,
						"project": self.project,
					},
					self.party_account_currency,
					item=self,
				)
			)

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.cash_bank_account,
						"against": self.supplier,
						"credit": self.base_paid_amount,
						"credit_in_account_currency": self.base_paid_amount
						if bank_account_currency == self.company_currency
						else self.paid_amount,
						"cost_center": self.cost_center,
					},
					bank_account_currency,
					item=self,
				)
			)



	def make_customer_gl_entry(self, gl_entries):
		# Checked both rounding_adjustment and rounded_total
		# because rounded_total had value even before introduction of posting GLE based on rounded total
		grand_total = (
			self.rounded_total if (self.rounding_adjustment and self.rounded_total) else self.grand_total
		)
		base_grand_total = flt(
			self.base_rounded_total
			if (self.base_rounding_adjustment and self.base_rounded_total)
			else self.base_grand_total,
			self.precision("base_grand_total"),
		)

		if grand_total and not self.is_internal_transfer():
			against_voucher = self.name
			if self.is_return and self.return_against and not self.update_outstanding_for_self:
				against_voucher = self.return_against

			# Did not use base_grand_total to book rounding loss gle
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.debit_to,
						"party_type": "Customer",
						"party": self.customer,
						"due_date": self.due_date,
						"against": self.against_income_account,
						"debit": base_grand_total,
						"debit_in_account_currency": base_grand_total
						if self.party_account_currency == self.company_currency
						else grand_total,
						"against_voucher": against_voucher,
						"against_voucher_type": self.doctype,
						"cost_center": self.cost_center,
						"project": self.project,
					},
					self.party_account_currency,
					item=self,
				)
			)
	# def make_tax_gl_entries1(self, gl_entries):		
	# 		gl_entries.append(
	# 			self.get_gl_dict(
	# 				{
	# 					"account": self.against_income_account,
	# 					"against": self.customer,
	# 					"credit": self.base_grand_total,
	# 					"credit_in_account_currency": self.base_paid_amount,
	# 					"due_date": self.due_date,

	# 					"cost_center": self.cost_center,
	# 				},
					
	# 				item=self,
	# 			)
	# 		)



	def make_tax_gl_entries(self, gl_entries):
		enable_discount_accounting = cint(
			frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
		)

		for tax in self.get("taxes"):
			amount, base_amount = self.get_tax_amounts(tax, enable_discount_accounting)

			if flt(tax.base_tax_amount_after_discount_amount):
				account_currency = get_account_currency(tax.account_head)
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": tax.account_head,
							"against": self.customer,
							"credit": flt(base_amount, tax.precision("tax_amount_after_discount_amount")),
							"credit_in_account_currency": (
								flt(base_amount, tax.precision("base_tax_amount_after_discount_amount"))
								if account_currency == self.company_currency
								else flt(amount, tax.precision("tax_amount_after_discount_amount"))
							),
							"cost_center": tax.cost_center,
						},
						account_currency,
						item=tax,
					)
				)
    

	def make_tax_gl_entries2(self, gl_entries):
		# tax table gl entries
		valuation_tax = {}

		for tax in self.get("taxes"):
			amount, base_amount = self.get_tax_amounts(tax, None)
			if tax.category in ("Total", "Valuation and Total") and flt(base_amount):
				account_currency = get_account_currency(tax.account_head)

				dr_or_cr = "debit" if tax.add_deduct_tax == "Add" else "credit"

				gl_entries.append(
					self.get_gl_dict(
						{
							"account": tax.account_head,
							"against": self.supplier,
							dr_or_cr: base_amount,
							dr_or_cr + "_in_account_currency": base_amount
							if account_currency == self.company_currency
							else amount,
							"cost_center": tax.cost_center,
						},
						account_currency,
						item=tax,
					)
				)
			# accumulate valuation tax
			if (
				self.is_opening == "No"
				and tax.category in ("Valuation", "Valuation and Total")
				and flt(base_amount)
				and not self.is_internal_transfer()
			):
				if not tax.cost_center:
					frappe.throw(
						_("Cost Center is required in row {0} in Taxes table for type {1}").format(
							tax.idx, _(tax.category)
						)
					)
				valuation_tax.setdefault(tax.name, 0)
				valuation_tax[tax.name] += (tax.add_deduct_tax == "Add" and 1 or -1) * flt(base_amount)

		if self.is_opening == "No" and self.negative_expense_to_be_booked and valuation_tax:
			# credit valuation tax amount in "Expenses Included In Valuation"
			# this will balance out valuation amount included in cost of goods sold

			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = self.negative_expense_to_be_booked
			i = 1
			for tax in self.get("taxes"):
				if valuation_tax.get(tax.name):
					if i == len(valuation_tax):
						applicable_amount = amount_including_divisional_loss
					else:
						applicable_amount = self.negative_expense_to_be_booked * (
							valuation_tax[tax.name] / total_valuation_amount
						)
						amount_including_divisional_loss -= applicable_amount

					gl_entries.append(
						self.get_gl_dict(
							{
								"account": tax.account_head,
								"cost_center": tax.cost_center,
								"against": self.supplier,
								"credit": applicable_amount,
								"remarks": self.remarks or _("Accounting Entry for Stock"),
							},
							item=tax,
						)
					)

					i += 1

   
    
	def make_internal_transfer_gl_entries(self, gl_entries):
		if self.is_internal_transfer() and flt(self.base_total_taxes_and_charges):
			account_currency = get_account_currency(self.unrealized_profit_loss_account)
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.unrealized_profit_loss_account,
						"against": self.customer,
						"debit": flt(self.total_taxes_and_charges),
						"debit_in_account_currency": flt(self.base_total_taxes_and_charges),
						"cost_center": self.cost_center,
					},
					account_currency,
					item=self,
				)
			)

	def make_item_gl_entries(self, gl_entries):
		# income account gl entries
		enable_discount_accounting = cint(
			frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
		)

		for item in self.get("items"):
			if flt(item.base_net_amount, item.precision("base_net_amount")):
				if not self.is_internal_transfer():
					income_account = (
						item.income_account
						if (not item.enable_deferred_revenue or self.is_return)
						else item.deferred_revenue_account
					)
					expense_account = (
						item.expense_account
						if (not item.enable_deferred_expense or self.is_return)
						else item.deferred_expense_account
					)

					amount, base_amount = self.get_amount_and_base_amount(
						item, enable_discount_accounting
					)

					account_currency = get_account_currency(income_account)
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": income_account,
								"against": self.customer,
								"credit": flt(base_amount, item.precision("base_net_amount")),
								"credit_in_account_currency": (
									flt(base_amount, item.precision("base_net_amount"))
									if account_currency == self.company_currency
									else flt(amount, item.precision("net_amount"))
								),
        						"remarks": self.get("remarks"),
								"cost_center": item.cost_center,
								"project": item.project or self.project,
							},
							account_currency,
							item=item,
						)
					)
	def make_item_gl_entries5(self, gl_entries):
		if self.is_multiple_suppliers:
			# Enable discount accounting setting
			enable_discount_accounting = cint(
				frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
			)

			for item in self.get("items"):
				if flt(item.base_net_amount, item.precision("base_net_amount")):
					if not self.is_internal_transfer():
						# Determine income and expense accounts
						income_account = (
							item.income_account
							if (not item.enable_deferred_revenue or self.is_return)
							else item.deferred_revenue_account
						)
						expense_account = (
							item.expense_account
							if (not item.enable_deferred_expense or self.is_return)
							else item.deferred_expense_account
						)

						amount, base_amount = self.get_amount_and_base_amount(
							item, enable_discount_accounting
						)

						account_currency = get_account_currency(income_account)
						supplier_account_currency = get_account_currency(item.credit_to)

						# Add GL entry for supplier credit
						gl_entries.append(
							self.get_gl_dict(
								{
									"account": item.credit_to,
									"party_type": "Supplier",
									"party": item.supplier,
									"against": item.expense_account,
									"credit": flt(item.byuing_amount_t, item.precision("byuing_amount_t")),
									"credit_in_account_currency": (
										flt(item.byuing_amount_t, item.precision("byuing_amount_t"))
										if supplier_account_currency == self.company_currency
										else flt(amount, item.precision("net_amount"))
									),
									"remarks": self.get("remarks"),
									"cost_center": item.cost_center,
									"project": item.project or self.project,
								},
								supplier_account_currency,
								item=item,
							)
						)

						# Add GL entry for expense account (debit)
						gl_entries.append(
							self.get_gl_dict(
								{
									"account": item.expense_account,
									"against": item.credit_to,
									"debit": flt(item.byuing_amount_t, item.precision("byuing_amount_t")),
									"debit_in_account_currency": (
										flt(item.byuing_amount_t, item.precision("byuing_amount_t"))
										if account_currency == self.company_currency
										else flt(amount, item.precision("net_amount"))
									),
									"remarks": self.get("remarks"),
									"cost_center": item.cost_center,
									"project": item.project or self.project,
								},
								account_currency,
								item=item,
							)
						)

					# gl_entries.append(
					# 	self.get_gl_dict(
					# 		{
					# 			"account": expense_account,
					# 			"against": self.supplier,
					# 			"debit": flt(base_amount, item.precision("base_net_amount")),
					# 			"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
					# 			"cost_center": item.cost_center,
					# 			"project": item.project or self.project,
					# 		},
					# 		account_currency,
					# 		item=item,
					# 	)
					# )
	# def make_multi_supplier_gl_entries(self, gl_entries)				
	def make_item_gl_entries1(self, gl_entries):
		if self.is_multiple_suppliers:
			# income account gl entries
			enable_discount_accounting = cint(
				frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
			)

			# هنا نحتفظ بمجموع المبالغ لكل حساب
			grouped_entries = {}

			for item in self.get("items"):
				if flt(item.base_net_amount, item.precision("base_net_amount")):
					if not self.is_internal_transfer():
						income_account = (
							item.income_account
							if (not item.enable_deferred_revenue or self.is_return)
							else item.deferred_revenue_account
						)
						expense_account = (
							item.expense_account
							if (not item.enable_deferred_expense or self.is_return)
							else item.deferred_expense_account
						)

						byuing_amount_t = item.byuing_amount_t
						commission_account = item.commission_account
						commission_amount_t = item.commission_amount_t

						amount, base_amount = self.get_amount_and_base_amount(
							item, enable_discount_accounting
						)

						account_currency = get_account_currency(income_account)

						# استخدام حساب المورد لكل عنصر في القيود
						supplier_account = item.credit_to or self.get_default_supplier_account(item)

						# إذا كان الحساب موجودًا بالفعل في grouped_entries نقوم بتحديث المبالغ
						if supplier_account in grouped_entries:
							grouped_entries[supplier_account]["credit"] += flt(byuing_amount_t, item.precision("byuing_amount_t"))
							grouped_entries[supplier_account]["credit_in_account_currency"] += flt(byuing_amount_t, item.precision("byuing_amount_t")) if account_currency == self.company_currency else flt(amount, item.precision("net_amount"))
						else:
							grouped_entries[supplier_account] = {
								"credit": flt(byuing_amount_t, item.precision("byuing_amount_t")),
								"credit_in_account_currency": flt(byuing_amount_t, item.precision("byuing_amount_t")) if account_currency == self.company_currency else flt(amount, item.precision("net_amount")),
								"remarks": self.get("remarks"),
								"cost_center": item.cost_center,
								"project": item.project or self.project,
								"item": item,
								"commission_account": commission_account,
								"commission_amount_t": commission_amount_t,
							}

			# الآن نقوم بإضافة القيود المحاسبية للمجموعة التي تم دمجها
			for supplier_account, entry in grouped_entries.items():
				# القيد الأساسي
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": supplier_account,
							"party_type": "Supplier",
							"party": item.supplier,
							"against": self.debit_to,
							"credit": entry["credit"],
							"credit_in_account_currency": entry["credit_in_account_currency"],
							"remarks": entry["remarks"],
							"cost_center": entry["cost_center"],
							"project": entry["project"],
						},
						account_currency,
						item=entry["item"],
					)
				)

				# القيد الدائن الجديد لقيم العمولة
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": entry["expense_account"],
							
							"against": self.debit_to,
							"d": entry["credit"],
							"credit_in_account_currency": entry["commission_amount_t"] if account_currency == self.company_currency else flt(entry["commission_amount_t"], item.precision("commission_amount_t")),
							"remarks": entry["remarks"],
							"cost_center": entry["cost_center"],
							"project": entry["project"],
						},
						account_currency,
						item=entry["item"],
					)
				)
						


	def make_item_gl_entries2(self, gl_entries):
		# income account gl entries
		enable_discount_accounting = cint(
			frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
		)

		for item in self.get("items"):
			if flt(item.base_net_amount, item.precision("base_net_amount")):
				if not self.is_internal_transfer():
					income_account = (
						item.income_account
						if (not item.enable_deferred_revenue or self.is_return)
						else item.deferred_revenue_account
					)
					expense_account = (
						item.expense_account
						if (not item.enable_deferred_expense or self.is_return)
						else item.deferred_expense_account
					)
					commission_account = (
						item.commission_account
						if (not item.enable_deferred_revenue or self.is_return)
						else item.deferred_revenue_account
					)
					amount, base_amount = self.get_amount_and_base_amount(
						item, enable_discount_accounting
					)

					account_currency = get_account_currency(commission_account)
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": commission_account,
								"against": self.customer,
								"credit": flt(item.commission_amount, item.precision("base_net_amount")),
								"credit_in_account_currency": (
									flt(item.commission_amount, item.precision("base_net_amount"))
									if account_currency == self.company_currency
									else flt(amount, item.precision("net_amount"))
								),
        						"remarks": self.get("remarks"),
								"cost_center": item.cost_center,
								"project": item.project or self.project,
							},
							account_currency,
							item=item,
						)
					)
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": expense_account,
								"party_type": "Supplier",
								"party": item.supplier,
								"due_date": self.due_date,
								"against": self.against_expense_account,
								"credit": item.byuing_amount,
								"credit_in_account_currency": item.byuing_amount
								if self.party_account_currency == self.company_currency
								else item.byuing_amount,
								"against_voucher": self.name,
								"against_voucher_type": self.doctype,
								"cost_center": self.cost_center,
								"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
								"cost_center": item.cost_center,
								"project": item.project or self.project,
							},
							account_currency,
							item=item,
						)
					)


	@property
	def enable_discount_accounting(self):
		if not hasattr(self, "_enable_discount_accounting"):
			self._enable_discount_accounting = cint(
				frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
			)

		return self._enable_discount_accounting

	def make_loyalty_point_redemption_gle(self, gl_entries):
		if cint(self.redeem_loyalty_points):
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.debit_to,
						"party_type": "Customer",
						"party": self.customer,
						"against": "Expense account - "
						+ cstr(self.loyalty_redemption_account)
						+ " for the Loyalty Program",
						"credit": self.loyalty_amount,
						"against_voucher": self.return_against if cint(self.is_return) else self.name,
						"against_voucher_type": self.doctype,
						"cost_center": self.cost_center,
					},
					item=self,
				)
			)
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.loyalty_redemption_account,
						"cost_center": self.cost_center or self.loyalty_redemption_cost_center,
						"against": self.customer,
						"debit": self.loyalty_amount,
						"remark": "Loyalty Points redeemed by the customer",
					},
					item=self,
				)
			)

	def make_pos_gl_entries(self, gl_entries):
		if cint(self.is_paid):
			skip_change_gl_entries = not cint(
				frappe.db.get_single_value("Accounts Settings", "post_change_gl_entries")
			)

			for payment_mode in self.payments:
				if skip_change_gl_entries and payment_mode.account == self.account_for_change_amount:
					payment_mode.base_amount -= flt(self.change_amount)

				if payment_mode.base_amount:
					# POS, make payment entries
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": self.debit_to,
								"party_type": "Customer",
								"party": self.customer,
								"against": payment_mode.account,
								"credit": payment_mode.base_amount,
								"credit_in_account_currency": payment_mode.base_amount
								if self.party_account_currency == self.company_currency
								else payment_mode.amount,
								"against_voucher": self.name,
								"against_voucher_type": self.doctype,
								"cost_center": self.cost_center,
							},
							self.party_account_currency,
							item=self,
						)
					)

					payment_mode_account_currency = get_account_currency(payment_mode.account)
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": payment_mode.account,
								"against": self.customer,
								"debit": payment_mode.base_amount,
								"debit_in_account_currency": payment_mode.base_amount
								if payment_mode_account_currency == self.company_currency
								else payment_mode.amount,
								"cost_center": self.cost_center,
							},
							payment_mode_account_currency,
							item=self,
						)
					)

			if not skip_change_gl_entries:
				self.make_gle_for_change_amount(gl_entries)

	def make_gle_for_change_amount(self, gl_entries):
		if self.change_amount:
			if self.account_for_change_amount:
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.debit_to,
							"party_type": "Customer",
							"party": self.customer,
							"against": self.account_for_change_amount,
							"debit": flt(self.base_change_amount),
							"debit_in_account_currency": flt(self.base_change_amount)
							if self.party_account_currency == self.company_currency
							else flt(self.change_amount),
							"against_voucher": self.return_against
							if cint(self.is_return) and self.return_against
							else self.name,
							"against_voucher_type": self.doctype,
							"cost_center": self.cost_center,
							"project": self.project,
						},
						self.party_account_currency,
						item=self,
					)
				)

				gl_entries.append(
					self.get_gl_dict(
						{
							"account": self.account_for_change_amount,
							"against": self.customer,
							"credit": self.base_change_amount,
							"cost_center": self.cost_center,
						},
						item=self,
					)
				)
			else:
				frappe.throw(_("Select change amount account"), title=_("Mandatory Field"))

	def make_write_off_gl_entry(self, gl_entries):
		# write off entries, applicable if only pos
		if (
			self.is_paid
			and self.write_off_account
			and flt(self.write_off_amount, self.precision("write_off_amount"))
		):
			write_off_account_currency = get_account_currency(self.write_off_account)
			default_cost_center = frappe.get_cached_value("Company", self.company, "cost_center")

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.debit_to,
						"party_type": "Customer",
						"party": self.customer,
						"against": self.write_off_account,
						"credit": flt(self.base_write_off_amount, self.precision("base_write_off_amount")),
						"credit_in_account_currency": (
							flt(self.base_write_off_amount, self.precision("base_write_off_amount"))
							if self.party_account_currency == self.company_currency
							else flt(self.write_off_amount, self.precision("write_off_amount"))
						),
						"against_voucher": self.return_against if cint(self.is_return) else self.name,
						"against_voucher_type": self.doctype,
						"cost_center": self.cost_center,
						"project": self.project,
					},
					self.party_account_currency,
					item=self,
				)
			)
			gl_entries.append(
				self.get_gl_dict(
					{
						"account": self.write_off_account,
						"against": self.customer,
						"debit": flt(self.base_write_off_amount, self.precision("base_write_off_amount")),
						"debit_in_account_currency": (
							flt(self.base_write_off_amount, self.precision("base_write_off_amount"))
							if write_off_account_currency == self.company_currency
							else flt(self.write_off_amount, self.precision("write_off_amount"))
						),
						"cost_center": self.cost_center or self.write_off_cost_center or default_cost_center,
					},
					write_off_account_currency,
					item=self,
				)
			)

	def make_gle_for_rounding_adjustment(self, gl_entries):
		if (
			flt(self.rounding_adjustment, self.precision("rounding_adjustment"))
			and self.base_rounding_adjustment
			and not self.is_internal_transfer()
		):
			round_off_account, round_off_cost_center = get_round_off_account_and_cost_center(
				self.company, "Sales Invoice", self.name, self.use_company_roundoff_cost_center
			)

			gl_entries.append(
				self.get_gl_dict(
					{
						"account": round_off_account,
						"against": self.customer,
						"credit_in_account_currency": flt(
							self.rounding_adjustment, self.precision("rounding_adjustment")
						),
						"credit": flt(
							self.base_rounding_adjustment, self.precision("base_rounding_adjustment")
						),
						"cost_center": round_off_cost_center
						if self.use_company_roundoff_cost_center
						else (self.cost_center or round_off_cost_center),
					},
					item=self,
				)
			)



	def update_project(self):
		if self.project:
			project = frappe.get_doc("Project", self.project)
			project.update_billed_amount()
			project.db_update()

	def verify_payment_amount_is_paiditive(self):
		for entry in self.payments:
			if entry.amount < 0:
				frappe.throw(_("Row #{0} (Payment Table): Amount must be positive").format(entry.idx))

	def verify_payment_amount_is_negative(self):
		for entry in self.payments:
			if entry.amount > 0:
				frappe.throw(_("Row #{0} (Payment Table): Amount must be negative").format(entry.idx))


	def get_returned_amount(self):
		from frappe.query_builder.functions import Sum

		doc = frappe.qb.DocType(self.doctype)
		returned_amount = (
			frappe.qb.from_(doc)
			.select(Sum(doc.grand_total))
			.where((doc.docstatus == 1) & (doc.is_return == 1) & (doc.return_against == self.name))
		).run()

		return abs(returned_amount[0][0]) if returned_amount[0][0] else 0


	def set_status(self, update=False, status=None, update_modified=True):
   
		if self.is_new():
			if self.get("amended_from"):
				self.status = "Draft"
			return

		outstanding_amount = flt(self.outstanding_amount, self.precision("outstanding_amount"))

		total = get_total_in_party_account_currency(self)

		if not status:
			if self.docstatus == 2:
				status = "Cancelled"
			elif self.docstatus == 1:
				if self.is_internal_transfer():
					self.status = "Internal Transfer"
				elif is_overdue(self, total):
					self.status = "Overdue"
				elif 0 < outstanding_amount < total:
					self.status = "Partly Paid"
				elif outstanding_amount > 0 and getdate(self.due_date) >= getdate():
					self.status = "Unpaid"
				elif self.is_return == 0 and frappe.db.get_value(
					"Service Invoice", {"is_return": 1, "return_against": self.name, "docstatus": 1}
				):
					self.status = "Credit Note Issued"
				elif self.is_return == 1:
					self.status = "Return"
					print("Status set to 'Return'.")
				elif outstanding_amount <= 0:
					self.status = "Paid"
				else:
					self.status = "Submitted"

				if (
					self.status in ("Unpaid", "Partly Paid", "Overdue")
					and self.is_discounted
					and get_discounting_status(self.name) == "Disbursed"
				):
					self.status += " and Discounted"
					print(f"Status updated to '{self.status}' due to discounting.")

			else:
				self.status = "Draft"

		if update:
			self.db_set("status", self.status, update_modified=update_modified)

	def calculate_outstanding_amount(self):
		frappe.msgprint("hiiiiii")
		# NOTE:
		# write_off_amount is only for POS Invoice
		# total_advance is only for non POS Invoice
		if self.doc.doctype == "Service Invoice":
			self.calculate_paid_amount()

		if (
			self.doc.is_return
			and self.doc.return_against
			and not self.doc.get("is_paid")
			or self.is_internal_invoice()
		):
			return

		self.doc.round_floats_in(self.doc, ["grand_total", "total_advance", "write_off_amount"])
		self._set_in_company_currency(self.doc, ["write_off_amount"])

		if self.doc.doctype in ["Service Invoice", "Purchase Invoice"]:
			grand_total = self.doc.rounded_total or self.doc.grand_total
			base_grand_total = self.doc.base_rounded_total or self.doc.base_grand_total

			if self.doc.party_account_currency == self.doc.currency:
				total_amount_to_pay = flt(
					grand_total - self.doc.total_advance - flt(self.doc.write_off_amount),
					self.doc.precision("grand_total"),
				)
			else:
				total_amount_to_pay = flt(
					flt(base_grand_total, self.doc.precision("base_grand_total"))
					- self.doc.total_advance
					- flt(self.doc.base_write_off_amount),
					self.doc.precision("base_grand_total"),
				)

			self.doc.round_floats_in(self.doc, ["paid_amount"])
			change_amount = 0

			if self.doc.doctype == "Service Invoice" and not self.doc.get("is_return"):
				self.calculate_change_amount()
				change_amount = (
					self.doc.change_amount
					if self.doc.party_account_currency == self.doc.currency
					else self.doc.base_change_amount
				)

			paid_amount = (
				self.doc.paid_amount
				if self.doc.party_account_currency == self.doc.currency
				else self.doc.base_paid_amount
			)

			self.doc.outstanding_amount = flt(
				total_amount_to_pay - flt(paid_amount) + flt(change_amount),
				self.doc.precision("outstanding_amount"),
			)

			if (
				self.doc.doctype == "Service Invoice"
				and self.doc.get("is_paid")
				and self.doc.get("pos_profile")
				and self.doc.get("is_consolidated")
			):
				write_off_limit = flt(
					frappe.db.get_value("POS Profile", self.doc.pos_profile, "write_off_limit")
				)
				if write_off_limit and abs(self.doc.outstanding_amount) <= write_off_limit:
					self.doc.write_off_outstanding_amount_automatically = 1

			if (
				self.doc.doctype == "Service Invoice"
				and self.doc.get("is_paid")
				and self.doc.get("is_return")
				and not self.doc.get("is_consolidated")
			):
				self.set_total_amount_to_default_mop(total_amount_to_pay)
				self.calculate_paid_amount()
	
	def calculate_paid_amount(self):
		paid_amount = base_paid_amount = 0.0

		if self.doc.is_pos:
			for payment in self.doc.get("payments"):
				payment.amount = flt(payment.amount)
				payment.base_amount = payment.amount * flt(self.doc.conversion_rate)
				paid_amount += payment.amount
				base_paid_amount += payment.base_amount
		elif not self.doc.is_return:
			self.doc.set("payments", [])

		if self.doc.redeem_loyalty_points and self.doc.loyalty_amount:
			base_paid_amount += self.doc.loyalty_amount
			paid_amount += self.doc.loyalty_amount / flt(self.doc.conversion_rate)

		self.doc.paid_amount = flt(paid_amount, self.doc.precision("paid_amount"))
		self.doc.base_paid_amount = flt(base_paid_amount, self.doc.precision("base_paid_amount"))

	def calculate_change_amount(self):
		self.doc.change_amount = 0.0
		self.doc.base_change_amount = 0.0
		grand_total = self.doc.rounded_total or self.doc.grand_total
		base_grand_total = self.doc.base_rounded_total or self.doc.base_grand_total

		if (
			self.doc.doctype == "Sales Invoice"
			and self.doc.paid_amount > grand_total
			and not self.doc.is_return
			and any(d.type == "Cash" for d in self.doc.payments)
		):
			self.doc.change_amount = flt(
				self.doc.paid_amount - grand_total, self.doc.precision("change_amount")
			)

			self.doc.base_change_amount = flt(
				self.doc.base_paid_amount - base_grand_total, self.doc.precision("base_change_amount")
			)

	def calculate_write_off_amount(self):
		if self.doc.get("write_off_outstanding_amount_automatically"):
			self.doc.write_off_amount = flt(
				self.doc.outstanding_amount, self.doc.precision("write_off_amount")
			)
			self.doc.base_write_off_amount = flt(
				self.doc.write_off_amount * self.doc.conversion_rate,
				self.doc.precision("base_write_off_amount"),
			)

			self.calculate_outstanding_amount()
	
	def set_total_amount_to_default_mop(self, total_amount_to_pay):
		total_paid_amount = 0
		for payment in self.doc.get("payments"):
			total_paid_amount += (
				payment.amount
				if self.doc.party_account_currency == self.doc.currency
				else payment.base_amount
			)

		pending_amount = total_amount_to_pay - total_paid_amount

		if pending_amount > 0:
			default_mode_of_payment = frappe.db.get_value(
				"POS Payment Method",
				{"parent": self.doc.pos_profile, "default": 1},
				["mode_of_payment"],
				as_dict=1,
			)

			if default_mode_of_payment:
				self.doc.payments = []
				self.doc.append(
					"payments",
					{
						"mode_of_payment": default_mode_of_payment.mode_of_payment,
						"amount": pending_amount,
						"default": 1,
					},
				)
		
			

	# ------------------------------------- ALa
	def validate_cash(self):
		if not self.cash_bank_account and flt(self.paid_amount):
			frappe.throw(_("Cash or Bank Account is mandatory for making payment entry"))

		if flt(self.paid_amount) + flt(self.write_off_amount) - flt(
			self.get("rounded_total") or self.grand_total
		) > 1 / (10 ** (self.precision("base_grand_total") + 1)):
			frappe.throw(_("""Paid amount + Write Off Amount can not be greater than Grand Total"""))
	def validate_credit_to_acc(self):
		if not self.credit_to:
			self.credit_to = get_party_account("Supplier", self.supplier, self.company)
			if not self.credit_to:
				self.raise_missing_debit_credit_account_error("Supplier", self.supplier)

		account = frappe.get_cached_value(
			"Account", self.credit_to, ["account_type", "report_type", "account_currency"], as_dict=True
		)

		if account.report_type != "Balance Sheet":
			frappe.throw(
				_(
					"Please ensure {} account is a Balance Sheet account. You can change the parent account to a Balance Sheet account or select a different account."
				).format(frappe.bold("Credit To")),
				title=_("Invalid Account"),
			)

		if self.supplier and account.account_type != "Payable":
			frappe.throw(
				_(
					"Please ensure {} account {} is a Payable account. Change the account type to Payable or select a different account."
				).format(frappe.bold("Credit To"), frappe.bold(self.credit_to)),
				title=_("Invalid Account"),
			)

		self.party_account_currency = account.account_currency
  
	def validate_expense_account(self):
		for item in self.get("items"):
			validate_account_head(item.idx, item.expense_account, self.company, "Expense")
	
	def set_against_income_account(self):
		"""Set against account for debit to account"""
		against_acc = []
		for d in self.get("items"):
			if d.income_account and d.income_account not in against_acc:
				against_acc.append(d.income_account)
		self.against_income_account = ",".join(against_acc)
	def set_against_expense_account(self):
		against_accounts = []
		for item in self.get("items"):
			if item.expense_account and (item.expense_account not in against_accounts):
				against_accounts.append(item.expense_account)

		self.against_expense_account = ",".join(against_accounts)
  
	def validate_pos_paid_amount(self):
		if len(self.payments) == 0 and self.is_paid:
			frappe.throw(_("At least one mode of payment is required for Paid invoice."))
   

def get_total_in_party_account_currency(doc):
	total_fieldname = "grand_total" if doc.disable_rounded_total else "rounded_total"
	if doc.party_account_currency != doc.currency:
		total_fieldname = "base_" + total_fieldname

	return flt(doc.get(total_fieldname), doc.precision(total_fieldname))


def is_overdue(doc, total):
	outstanding_amount = flt(doc.outstanding_amount, doc.precision("outstanding_amount"))
	if outstanding_amount <= 0:
		return

	today = getdate()
	if doc.get("is_paid") or not doc.get("payment_schedule"):
		return getdate(doc.due_date) < today

	# calculate payable amount till date
	payment_amount_field = (
		"base_payment_amount" if doc.party_account_currency != doc.currency else "payment_amount"
	)

	payable_amount = sum(
		payment.get(payment_amount_field)
		for payment in doc.payment_schedule
		if getdate(payment.due_date) < today
	)

	return (total - outstanding_amount) < payable_amount


def get_discounting_status(sales_invoice):
	status = None

	invoice_discounting_list = frappe.db.sql(
		"""
		select status
		from `tabInvoice Discounting` id, `tabDiscounted Invoice` d
		where
			id.name = d.parent
			and d.sales_invoice=%s
			and id.docstatus=1
			and status in ('Disbursed', 'Settled')
	""",
		sales_invoice,
	)

	for d in invoice_discounting_list:
		status = d[0]
		if status == "Disbursed":
			break

	return status





def update_linked_doc(doctype, name, inter_company_reference):
	if doctype in ["Sales Invoice", "Purchase Invoice"]:
		ref_field = "inter_company_invoice_reference"
	else:
		ref_field = "inter_company_order_reference"

	if inter_company_reference:
		frappe.db.set_value(doctype, inter_company_reference, ref_field, name)




def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context

	list_context = get_list_context(context)
	list_context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Invoices"),
		}
	)
	return list_context


@frappe.whitelist()
def get_bank_cash_account(mode_of_payment, company):
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)
	if not account:
		frappe.throw(
			_("Please set default Cash or Bank account in Mode of Payment {0}").format(
				get_link_to_form("Mode of Payment", mode_of_payment)
			),
			title=_("Missing Account"),
		)
	return {"account": account}




@frappe.whitelist()
def make_sales_return(source_name, target_doc=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	return make_return_doc("Sales Invoice", source_name, target_doc)


def get_inter_company_details(doc, doctype):
	if doctype in ["Sales Invoice", "Sales Order", "Delivery Note"]:
		parties = frappe.db.get_all(
			"Supplier",
			fields=["name"],
			filters={"disabled": 0, "is_internal_supplier": 1, "represents_company": doc.company},
		)
		company = frappe.get_cached_value("Customer", doc.customer, "represents_company")

		if not parties:
			frappe.throw(
				_("No Supplier found for Inter Company Transactions which represents company {0}").format(
					frappe.bold(doc.company)
				)
			)

		party = get_internal_party(parties, "Supplier", doc)
	else:
		parties = frappe.db.get_all(
			"Customer",
			fields=["name"],
			filters={"disabled": 0, "is_internal_customer": 1, "represents_company": doc.company},
		)
		company = frappe.get_cached_value("Supplier", doc.supplier, "represents_company")

		if not parties:
			frappe.throw(
				_("No Customer found for Inter Company Transactions which represents company {0}").format(
					frappe.bold(doc.company)
				)
			)

		party = get_internal_party(parties, "Customer", doc)

	return {"party": party, "company": company}


def get_internal_party(parties, link_doctype, doc):
	if len(parties) == 1:
		party = parties[0].name
	else:
		# If more than one Internal Supplier/Customer, get supplier/customer on basis of address
		if doc.get("company_address") or doc.get("shipping_address"):
			party = frappe.db.get_value(
				"Dynamic Link",
				{
					"parent": doc.get("company_address") or doc.get("shipping_address"),
					"parenttype": "Address",
					"link_doctype": link_doctype,
				},
				"link_name",
			)

			if not party:
				party = parties[0].name
		else:
			party = parties[0].name

	return party




def get_received_items(reference_name, doctype, reference_fieldname):
	reference_field = "inter_company_invoice_reference"
	if doctype == "Purchase Order":
		reference_field = "inter_company_order_reference"

	filters = {
		reference_field: reference_name,
		"docstatus": 1,
	}

	target_doctypes = frappe.get_all(
		doctype,
		filters=filters,
		as_list=True,
	)

	if target_doctypes:
		target_doctypes = list(target_doctypes[0])

	received_items_map = frappe._dict(
		frappe.get_all(
			doctype + " Item",
			filters={"parent": ("in", target_doctypes)},
			fields=[reference_fieldname, "qty"],
			as_list=1,
		)
	)

	return received_items_map






def update_taxes(
	doc,
	party=None,
	party_type=None,
	company=None,
	doctype=None,
	party_address=None,
	company_address=None,
	shipping_address_name=None,
	master_doctype=None,
):
	# Update Party Details
	party_details = get_party_details(
		party=party,
		party_type=party_type,
		company=company,
		doctype=doctype,
		party_address=party_address,
		company_address=company_address,
		shipping_address=shipping_address_name,
	)

	# Update taxes and charges if any
	doc.taxes_and_charges = party_details.get("taxes_and_charges")
	doc.set("taxes", party_details.get("taxes"))


def update_address(doc, address_field, address_display_field, address_name):
	doc.set(address_field, address_name)
	fetch_values = get_fetch_values(doc.doctype, address_field, address_name)

	for key, value in fetch_values.items():
		doc.set(key, value)

	doc.set(address_display_field, get_address_display(doc.get(address_field)))




def update_multi_mode_option(doc, pos_profile):
	def append_payment(payment_mode):
		payment = doc.append("payments", {})
		payment.default = payment_mode.default
		payment.mode_of_payment = payment_mode.mop
		payment.account = payment_mode.default_account
		payment.type = payment_mode.type

	doc.set("payments", [])
	invalid_modes = []
	mode_of_payments = [d.mode_of_payment for d in pos_profile.get("payments")]
	mode_of_payments_info = get_mode_of_payments_info(mode_of_payments, doc.company)

	for row in pos_profile.get("payments"):
		payment_mode = mode_of_payments_info.get(row.mode_of_payment)
		if not payment_mode:
			invalid_modes.append(get_link_to_form("Mode of Payment", row.mode_of_payment))
			continue

		payment_mode.default = row.default
		append_payment(payment_mode)

	if invalid_modes:
		if invalid_modes == 1:
			msg = _("Please set default Cash or Bank account in Mode of Payment {}")
		else:
			msg = _("Please set default Cash or Bank account in Mode of Payments {}")
		frappe.throw(msg.format(", ".join(invalid_modes)), title=_("Missing Account"))


def get_all_mode_of_payments(doc):
	return frappe.db.sql(
		"""
		select mpa.default_account, mpa.parent, mp.type as type
		from `tabMode of Payment Account` mpa,`tabMode of Payment` mp
		where mpa.parent = mp.name and mpa.company = %(company)s and mp.enabled = 1""",
		{"company": doc.company},
		as_dict=1,
	)


def get_mode_of_payments_info(mode_of_payments, company):
	data = frappe.db.sql(
		"""
		select
			mpa.default_account, mpa.parent as mop, mp.type as type
		from
			`tabMode of Payment Account` mpa,`tabMode of Payment` mp
		where
			mpa.parent = mp.name and
			mpa.company = %s and
			mp.enabled = 1 and
			mp.name in %s
		group by
			mp.name
		""",
		(company, mode_of_payments),
		as_dict=1,
	)

	return {row.get("mop"): row for row in data}


def get_mode_of_payment_info(mode_of_payment, company):
	return frappe.db.sql(
		"""
		select mpa.default_account, mpa.parent, mp.type as type
		from `tabMode of Payment Account` mpa,`tabMode of Payment` mp
		where mpa.parent = mp.name and mpa.company = %s and mp.enabled = 1 and mp.name = %s""",
		(company, mode_of_payment),
		as_dict=1,
	)



def check_if_return_invoice_linked_with_payment_entry(self):
	# If a Return invoice is linked with payment entry along with other invoices,
	# the cancellation of the Return causes allocated amount to be greater than paid

	if not frappe.db.get_single_value("Accounts Settings", "unlink_payment_on_cancellation_of_invoice"):
		return

	payment_entries = []
	if self.is_return and self.return_against:
		invoice = self.return_against
	else:
		invoice = self.name

	payment_entries = frappe.db.sql_list(
		"""
		SELECT
			t1.name
		FROM
			`tabPayment Entry` t1, `tabPayment Entry Reference` t2
		WHERE
			t1.name = t2.parent
			and t1.docstatus = 1
			and t2.reference_name = %s
			and t2.allocated_amount < 0
		""",
		invoice,
	)

	links_to_pe = []
	if payment_entries:
		for payment in payment_entries:
			payment_entry = frappe.get_doc("Payment Entry", payment)
			if len(payment_entry.references) > 1:
				links_to_pe.append(payment_entry.name)
		if links_to_pe:
			payment_entries_link = [
				get_link_to_form("Payment Entry", name, label=name) for name in links_to_pe
			]
			message = _("Please cancel and amend the Payment Entry")
			message += " " + ", ".join(payment_entries_link) + " "
			message += _("to unallocate the amount of this Return Invoice before cancelling it.")
			frappe.throw(message)


def make_discount_gl_entries(self, gl_entries):
	if self.doctype == "Purchase Invoice":
		enable_discount_accounting = cint(
			frappe.db.get_single_value("Buying Settings", "enable_discount_accounting")
		)
	elif self.doctype == "Service Invoice":
		enable_discount_accounting = cint(
			frappe.db.get_single_value("Selling Settings", "enable_discount_accounting")
		)

	if self.doctype == "Purchase Invoice":
		dr_or_cr = "credit"
		rev_dr_cr = "debit"
		supplier_or_customer = self.supplier

	else:
		dr_or_cr = "debit"
		rev_dr_cr = "credit"
		supplier_or_customer = self.customer

	if enable_discount_accounting:
		for item in self.get("items"):
			if item.get("discount_amount") and item.get("discount_account"):
				discount_amount = item.discount_amount * item.qty
				if self.doctype == "Purchase Invoice":
					income_or_expense_account = (
						item.expense_account
						if (not item.enable_deferred_expense or self.is_return)
						else item.deferred_expense_account
					)
				else:
					income_or_expense_account = (
						item.income_account
						if (not item.enable_deferred_revenue or self.is_return)
						else item.deferred_revenue_account
					)

				account_currency = get_account_currency(item.discount_account)
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": item.discount_account,
							"against": supplier_or_customer,
							dr_or_cr: flt(
								discount_amount * self.get("conversion_rate"),
								item.precision("discount_amount"),
							),
							dr_or_cr + "_in_account_currency": flt(
								discount_amount, item.precision("discount_amount")
							),
							"cost_center": item.cost_center,
							"project": item.project,
						},
						account_currency,
						item=item,
					)
				)

				account_currency = get_account_currency(income_or_expense_account)
				gl_entries.append(
					self.get_gl_dict(
						{
							"account": income_or_expense_account,
							"against": supplier_or_customer,
							rev_dr_cr: flt(
								discount_amount * self.get("conversion_rate"),
								item.precision("discount_amount"),
							),
							rev_dr_cr + "_in_account_currency": flt(
								discount_amount, item.precision("discount_amount")
							),
							"cost_center": item.cost_center,
							"project": item.project or self.project,
						},
						account_currency,
						item=item,
					)
				)

	if (
		(enable_discount_accounting or self.get("is_cash_or_non_trade_discount"))
		and self.get("additional_discount_account")
		and self.get("discount_amount")
	):
		gl_entries.append(
			self.get_gl_dict(
				{
					"account": self.additional_discount_account,
					"against": supplier_or_customer,
					dr_or_cr: self.base_discount_amount,
					"cost_center": self.cost_center or erpnext.get_default_cost_center(self.company),
				},
				item=self,
			)
		)