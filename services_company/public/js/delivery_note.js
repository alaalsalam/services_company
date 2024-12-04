frappe.ui.form.on('Delivery Note Item', {
    item_code: function(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);

        if (row.sales_order_item) {
            // جلب الحقول ordered_qty و delivered_qty من Sales Order Item
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Sales Order Item",
                    filters: { name: row.sales_order_item },
                    fieldname: ["ordered_qty", "delivered_qty"]
                },
                callback: function(response) {
                    const ordered_qty = response.message.ordered_qty || 0;
                    const delivered_qty_so = response.message.delivered_qty || 0;

                    // جلب الكمية المسلّمة من Delivery Notes الأخرى
                    frappe.call({
                        method: "frappe.db.get_value",
                        args: {
                            doctype: "Delivery Note Item",
                            fieldname: ["SUM(qty) AS delivered_qty"],
                            filters: { sales_order_item: row.sales_order_item }
                        },
                        callback: function(res) {
                            const delivered_qty_dn = res.message.delivered_qty || 0;

                            // حساب الكمية المتبقية بناءً على Sales Order Item
                            const remaining_qty = ordered_qty - (delivered_qty_so + delivered_qty_dn);

                            // تحديث القيم في الحقول
                            frappe.model.set_value(cdt, cdn, "ordered_qty", ordered_qty);
                            frappe.model.set_value(cdt, cdn, "delivered_qty", delivered_qty_so + delivered_qty_dn);
                            frappe.model.set_value(cdt, cdn, "remaining_qty", remaining_qty);
                        }
                    });
                }
            });
        }
    }
});
