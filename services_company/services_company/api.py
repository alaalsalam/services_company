import frappe
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    def update_item(source, target, source_parent):
        target.party_type = "Customer"
        target.party = source.shipper_name
        target.party_name = source.shipper_name
        # target.paid_to = source.shipper_name
        target.paid_from = source.debit_to
        target.payment_type = "Receive"
        target.custom_total_amount =source.outstanding
        account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")
        target.paid_from_account_currency = account_currency


    doc = get_mapped_doc(
        "Service Invoice",  
        source_name,
        {
            "Service Invoice": {
                "doctype": "Payment Entry",
                "field_map": {
                    "shipper_name": "party",
                    "outstanding": "paid_amount",
                    
                },
                "postprocess": update_item,
            },
        },
        target_doc
    )

@frappe.whitelist()
def make_payment_entry1(source_name, target_doc=None):
    def update_item(source, target, source_parent):
        target.party_type = "Supplier"
        target.party = source.supplier
        target.custom_total_amount =source.outstanding_amount_due_to_company
        target.party_name = source.supplier
        target.paid_to = source.credit_to
        target.payment_type = "Pay"
        account_currency = frappe.db.get_value("Account", source.credit_to, "account_currency")
        
        target.paid_to_account_currency = account_currency


    doc = get_mapped_doc(
        "Service Invoice",  
        source_name,
        {
            "Service Invoice": {
                "doctype": "Payment Entry",
                "field_map": {
                    
                    "outstanding_amount_due_to_company": "paid_amount",
                   
                },
                "postprocess": update_item,
            },
        },
        target_doc
    )

    return doc
@frappe.whitelist()
def update_service_invoice(doc, method):
    # Assuming reference_no links to Service Invoice
        service_invoice = frappe.get_doc("Service Invoice", "ACC-SINV-2025-00014")
        
        # حفظ القيمة الحالية قبل التعديل
        original_outstanding = service_invoice.outstanding_amount_due_to_company
        
        # خصم المبلغ المدفوع
        service_invoice.outstanding_amount_due_to_company -= doc.paid_amount
        
        # حفظ التغييرات
        service_invoice.save()
        
        # عرض رسالة بالقيم قبل وبعد التعديل
       
# @frappe.whitelist()
# def chang_status():
#     source_name = frappe.form_dict.get("source_name")

#     parcel = frappe.get_doc("Parcel", source_name)

#     if parcel.shepment_status != "Delivered":
#         parcel.shepment_status = "Delivered"
#         parcel.save()
#         frappe.db.commit()     
    

