frappe.ui.form.on("Sales Invoice", {
    posting_date: function (frm) {
        if (frm.fields_dict["payment_schedule"]) {
            frm.clear_table("payment_schedule");

            frm.refresh_field("payment_schedule");

        }
    },
    due_date: function (frm) {
        if (frm.fields_dict["payment_schedule"]) {
            frm.clear_table("payment_schedule");

            frm.refresh_field("payment_schedule");
            frm.doc.posting_date = frm.doc.due_date;
            frm.refresh_field("posting_date");

        }
    },
});