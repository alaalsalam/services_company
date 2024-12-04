import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

class CustomJournalEntry(JournalEntry):

  
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
            if child_field["doctype_name"] == "Journal Entry Account": 
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
                "doctype_name": ["in", ["Journal Entry Account", "Purchase Invoice Item"]], 
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
