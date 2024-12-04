// Copyright (c) 2024, alaalsalam and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Field Property Settings", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Field Properties", {
    doctype_name: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.doctype_name) {
            frappe.model.with_doctype(row.doctype_name, function() {
                let fields = frappe.get_doc("DocType", row.doctype_name).fields;
                let options = [];

                if (row.doctype_name === "Sales Invoice") {
                    options = fields
                        .filter(d => ["posting_date", "remarks"].includes(d.fieldname))
                        .map(d => d.fieldname);
                } else if (row.doctype_name === "Purchase Invoice") {
                    options = fields
                        .filter(d => ["posting_date", "bill_no", "remarks"].includes(d.fieldname))
                        .map(d => d.fieldname);
                } else if (row.doctype_name === "Purchase Invoice Item" || row.doctype_name === "Sales Invoice Item") {
                    options = fields
                        .filter(d => d.fieldname === "rate")
                        .map(d => d.fieldname);
                } else if (row.doctype_name === "Journal Entry" ) {
                    options = fields
                        .filter(d => d.fieldname === "posting_date")
                        .map(d => d.fieldname);
                } else if (row.doctype_name === "Journal Entry Account" ) {
                    options = fields
                        .filter(d => ["credit_in_account_currency"].includes(d.fieldname))
                        .map(d => d.fieldname);
                } else {
                    options = fields.map(d => d.fieldname);
                }

                if (options && options.length > 0) {
                    let option_values = [""].concat(options);

                    frm.fields_dict.field_properties.grid.update_docfield_property(
                        "field_name",
                        "options",
                        option_values
                    );

                    frm.refresh_field("field_properties"); 
                } else {
                    console.log("لم يتم العثور على أي حقول صالحة.");
                }
            });
        } else {
            console.log("لم يتم تحديد اسم Doctype");
        }
    }
});





    // frappe.ui.form.on("Field Property Settings", {
    //     after_save: function (frm) {
    //         if (!frm.doc.field_properties || frm.doc.field_properties.length === 0) {
    //             return;
    //         }
    
    //         frm.doc.field_properties.forEach(row => {
    //             if (row.doctype_name && row.field_name) {
    //                 frappe.call({
    //                     method: "services_company.services_company.overrides.sales_invoice.get_currency_or_percent_fields",
    //                     args: {
    //                         doctype_name: row.doctype_name,
    //                         field_name:row.field_name
    //                     },
    //                     callback: function (response) {
    //                         if (response.message && response.message.length > 0) {
    //                             const fields = response.message;
    
    //                             fields.forEach(field => {
    //                                 frappe.call({
    //                                     method: "frappe.client.insert",
    //                                     args: {
    //                                         doc: {
    //                                             doctype: "Property Setter",
    //                                             doctype_or_field: "DocField",
    //                                             doc_type: field.doctype,
    //                                             field_name: field.fieldname,
    //                                             property: "allow_on_submit",
    //                                             value: 1,
    //                                             property_type: "Check",
    //                                             module: "Services Company"
    //                                         }
    //                                     },
    //                                     callback: function () {
    //                                         console.log(`Property Setter created for field ${field.fieldname} in DocType ${field.doctype}`);
    //                                     }
    //                                 });
    //                             });
    
    //                             frappe.msgprint(__("Fields for DocType " + row.doctype_name + " have been updated successfully."));
    //                         } else {
    //                             frappe.msgprint(__("No Currency or Percent fields found in the specified DocType: " + row.doctype_name));
    //                         }
    //                     }
    //                 });
    //             } else {
    //                 console.warn("Incomplete row: doctype_name and field_name are required.");
    //             }
    //         });
    //     }
    // });
    // 
    frappe.ui.form.on("Field Property Settings", {
        after_save: async function (frm) {
            if (!frm.doc.field_properties || frm.doc.field_properties.length === 0) {
                return;
            }
    
            const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    
            for (const row of frm.doc.field_properties) {
                if (row.doctype_name && row.field_name) {
                    try {
                        const response = await frappe.call({
                            method: "services_company.services_company.overrides.sales_invoice.get_currency_or_percent_fields",
                            args: {
                                doctype_name: row.doctype_name,
                                field_name: row.field_name
                            }
                        });
    
                        if (response.message && response.message.length > 0) {
                            const fields = response.message;
    
                            for (const field of fields) {
                                // التحقق مما إذا كان Property Setter موجودًا
                                const existingPropertySetters = await frappe.call({
                                    method: "frappe.client.get_list",
                                    args: {
                                        doctype: "Property Setter",
                                        filters: {
                                            doc_type: field.doctype,
                                            field_name: field.fieldname,
                                            property: "allow_on_submit"
                                        },
                                        fields: ["name", "value"]
                                    }
                                });
    
    
                                if (existingPropertySetters.message && existingPropertySetters.message.length > 0) {
                                    const propertySetter = existingPropertySetters.message[0];
                                    const newValue = row.allow ? 1 : 0;
    
                                    if (propertySetter.value != newValue) { // تحقق من القيمة
                                        await frappe.call({
                                            method: "frappe.client.set_value",
                                            args: {
                                                doctype: "Property Setter",
                                                name: propertySetter.name,
                                                fieldname: "value",
                                                value: newValue
                                            }
                                        });
                                        console.log(`Updated Property Setter for field ${field.fieldname} in DocType ${field.doctype}`);
                                    } else {
                                        console.log(`Property Setter already exists with the same value for field ${field.fieldname} in DocType ${field.doctype}`);
                                    }
                                } else {
                                    if (row.allow) {
                                        await frappe.call({
                                            method: "frappe.client.insert",
                                            args: {
                                                doc: {
                                                    doctype: "Property Setter",
                                                    doctype_or_field: "DocField",
                                                    doc_type: field.doctype,
                                                    field_name: field.fieldname,
                                                    property: "allow_on_submit",
                                                    value: 1,
                                                    property_type: "Check",
                                                    module: "Services Company"
                                                }
                                            }
                                        });
                                        console.log(`Created Property Setter for field ${field.fieldname} in DocType ${field.doctype}`);
                                    }
                                }
                            }
    
                            frappe.msgprint(__("Fields for DocType " + row.doctype_name + " have been updated successfully."));
                        } else {
                            frappe.msgprint(__("No Currency or Percent fields found in the specified DocType: " + row.doctype_name));
                        }
                    } catch (error) {
                        console.error("Error processing fields for row:", error);
                    }
                } else {
                    console.warn("Incomplete row: doctype_name and field_name are required.");
                }
    
                await delay(50);
            }
        }
    });
    