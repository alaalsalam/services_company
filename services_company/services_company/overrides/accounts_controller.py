import frappe
from erpnext.accounts.accounts_controller import AccountsController
from erpnext.controllers.accounts_controller import check_if_child_table_updated
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)

class CustomAccountsController(AccountsController):
   
    def check_if_fields_updated(self, fields_to_check, child_tables):
    
        doc_before_update = self.get_doc_before_save()

        accounting_dimensions = [*get_accounting_dimensions(), "cost_center", "project"]

        custom_fields = self.get_custom_fields_and_dimensions()

        fields_to_check += accounting_dimensions + custom_fields

        child_table_fields = self.get_child_table_fields()

        # دمج الحقول `child_tables`
        for child_field in child_table_fields:
            if child_field["doctype_name"] == "Sales Invoice Item": 
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
                frappe.msgprint(f"Child table '{table}' has been updated.")
                return True

            frappe.msgprint("No fields or child tables have been updated.")
            return False

    def get_custom_fields_and_dimensions(self):
        
        custom_fields = frappe.get_all(
            "Field Properties",
            fields=["field_name"],
            filters={"parenttype": "Field Property Settings"},
        )

        custom_field_names = [field.field_name for field in custom_fields]
        frappe.msgprint(f"Custom Fields: {custom_field_names}")
        return custom_field_names

    def get_child_table_fields(self):
        
        child_table_fields = frappe.get_all(
            "Field Properties",
            fields=["doctype_name", "field_name"],
            filters={
                "doctype_name": ["in", ["Sales Invoice Item", "Purchase Invoice Item"]], 
            },
        )

        frappe.msgprint(f"Child Table Fields: {child_table_fields}")
        return child_table_fields

    def check_if_child_table_updated(self, child_table_before_update, child_table_after_update, fields_to_check):
        
        fields_to_check = list(fields_to_check) + get_accounting_dimensions() + ["cost_center", "project"]

        for index, item in enumerate(child_table_before_update):
            for field in fields_to_check:
                if child_table_after_update[index].get(field) != item.get(field):
                    frappe.msgprint(f"Field '{field}' in child table has been updated.")
                    return True

        return False
#  import frappe
# from erpnext.controllers.accounts_controller import check_if_child_table_updated
# from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
#     get_accounting_dimensions,

# )


# from erpnext.accounts.general_ledger import (
# 	make_gl_entries,
# 	make_reverse_gl_entries,
# 	process_gl_map,
# )
# from erpnext.accounts.utils import (
# 	create_gain_loss_journal,
# 	get_account_currency,
# 	get_currency_precision,
# 	get_fiscal_years,
# 	validate_fiscal_year,
# )
# from frappe.utils import cint, comma_or, flt, getdate, nowdate
# from erpnext.accounts.utils import (
# 	cancel_exchange_gain_loss_journal,
# 	get_account_currency,
# 	get_balance_on,
# 	get_outstanding_invoices,
# 	get_party_types_from_account_type,
# )
# from erpnext.accounts.party import get_party_account

# from erpnext.accounts.doctype.bank_account.bank_account import (
# 	get_bank_account_details,
# 	get_default_company_bank_account,
# 	get_party_bank_account,
# )
# from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
# 	get_party_account_based_on_invoice_discounting,
# )
# from erpnext.controllers.accounts_controller import AccountsController



# class CustomSalesInvoice(AccountsController):
#     def check_if_fields_updated(self, fields_to_check, child_tables):
#             """
#             تحقق مما إذا كانت الحقول أو الجداول الفرعية قد تغيرت.
#             """
#             # جلب نسخة المستند قبل الحفظ
#             doc_before_update = self.get_doc_before_save()

#             # الأبعاد المحاسبية
#             accounting_dimensions = [*get_accounting_dimensions(), "cost_center", "project"]

#             # الحقول المخصصة من الدالة
#             custom_fields = self.get_custom_fields_and_dimensions()

#             # دمج جميع الحقول التي سيتم التحقق منها
#             fields_to_check += accounting_dimensions + custom_fields

#             # التحقق من الحقول الرئيسية
#             for field in fields_to_check:
#                 if doc_before_update.get(field) != self.get(field):
#                     frappe.msgprint(f"Fields to Check: {fields_to_check}")

#                     return True

#             # التحقق من الجداول الفرعية
#             for table in child_tables:
#                 if check_if_child_table_updated(
#                     doc_before_update.get(table), self.get(table), child_tables[table]
#                 ):
#                     return True

#             return False

#     def get_custom_fields_and_dimensions(self):
#         """
#         استعلام لجلب الحقول المخصصة من Field Properties.
#         """
#         # استعلام لجلب الحقول المخصصة
#         custom_fields = frappe.get_all(
#             "Field Properties",
#             fields=["field_name"],
#             filters={"parenttype": "Field Property Settings"},
#         )

#         # استخراج أسماء الحقول فقط
#         custom_field_names = [field.field_name for field in custom_fields]

#         return custom_field_names   

# def get_custom_fields_and_dimensions(self):
#         """
#         استعلام لجلب الحقول المخصصة من Field Properties.
#         """
#         # استعلام لجلب الحقول المخصصة
#         custom_fields = frappe.get_all(
#             "Field Properties",
#             fields=["field_name"],
#             filters={"parenttype": "Field Property Settings"},
#         )

#         # استخراج أسماء الحقول فقط
#         custom_field_names = [field.field_name for field in custom_fields]

#         return custom_field_names


#     def on_update_after_submit(self):
#         """
#         التحقق من التحديثات على المستند بعد الإرسال.
#         """
#         frappe.msgprint("Checking for updates...")
        
#         # الحقول الأساسية للتحقق
#         fields_to_check = [
#             "additional_discount_account",
#             "cash_bank_account",
#             "account_for_change_amount",
#             "write_off_account",
#             "loyalty_redemption_account",
#             "unrealized_profit_loss_account",
#             "is_opening",
#             "remarks",
#             # "posting_date",
#             # "total",
#         ]
        
#         # الجداول الفرعية للتحقق
#         child_tables = {
#             "items": ("income_account", "expense_account", "discount_account"),
#             "taxes": ("account_head",),
#         }
        
#         # إضافة الحقول المخصصة إلى الحقول الأساسية
#         custom_fields = self.get_custom_fields_and_dimensions()
#         fields_to_check += custom_fields

#         # التحقق من التغييرات
#         self.needs_repost = self.check_if_fields_updated(fields_to_check, child_tables)

#         # تنفيذ عملية التحديث إذا كان هناك تغييرات
#         if self.needs_repost:
#             frappe.msgprint("Fields updated. Reposting accounting entries...")
#             self.validate_for_repost()
#             self.repost_accounting_entries()
#         else:
#             frappe.msgprint("No updates detected.")

#     def on_change(self) :
#         frappe.msgprint("hiii")

#     def on_save(self):
#         # قم بإضافة رسالة طباعة للتأكد من أن الكود يعمل
#         frappe.msgprint("CustomSalesInvoice: Overridden before_save is working!")
#         super().on_save()     
       