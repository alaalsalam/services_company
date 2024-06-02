// Copyright (c) 2024, alaalsalam and contributors
// For license information, please see license.txt

// frappe.ui.form.on('Service Invoice', {
// 	// refresh: function(frm) {

// 	// }
// });
// -----------------
// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.accounts");

cur_frm.cscript.tax_table = "Sales Taxes and Charges";

erpnext.accounts.taxes.setup_tax_validations("Sales Invoice");
erpnext.accounts.payment_triggers.setup("Sales Invoice");
erpnext.accounts.pos.setup("Sales Invoice");
erpnext.accounts.taxes.setup_tax_filters("Sales Taxes and Charges");
erpnext.sales_common.setup_selling_controller();
erpnext.accounts.SalesInvoiceController = class SalesInvoiceController extends (
	erpnext.selling.SellingController
) {
	setup(doc) {
		this.setup_posting_date_time_check();
		super.setup(doc);
	}
	company() {
		super.company();
		erpnext.accounts.dimensions.update_dimension(this.frm, this.frm.doctype);
	}
	onload() {
		var me = this;
		super.onload();

		this.frm.ignore_doctypes_on_cancel_all = [
			"POS Invoice",
			"Timesheet",
			"POS Invoice Merge Log",
			"POS Closing Entry",
			"Journal Entry",
			"Payment Entry",
			"Repost Payment Ledger",
			"Repost Accounting Ledger",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
			"Serial and Batch Bundle",
			"Bank Transaction",
		];

		if (!this.frm.doc.__islocal && !this.frm.doc.customer && this.frm.doc.debit_to) {
			// show debit_to in print format
			this.frm.set_df_property("debit_to", "print_hide", 0);
		}

		erpnext.queries.setup_queries(this.frm, "Warehouse", function () {
			return erpnext.queries.warehouse(me.frm.doc);
		});

		if (this.frm.doc.__islocal && this.frm.doc.is_pos) {
			//Load pos profile data on the invoice if the default value of Is POS is 1

			me.frm.script_manager.trigger("is_pos");
			me.frm.refresh_fields();
		}
		erpnext.queries.setup_warehouse_query(this.frm);
	}

	refresh(doc, dt, dn) {
		const me = this;
		super.refresh();
		if (cur_frm.msgbox && cur_frm.msgbox.$wrapper.is(":visible")) {
			// hide new msgbox
			cur_frm.msgbox.hide();
		}

		this.frm.toggle_reqd("due_date", !this.frm.doc.is_return);

		if (this.frm.doc.repost_required && this.frm.doc.docstatus === 1) {
			this.frm.set_intro(
				__(
					"Accounting entries for this invoice needs to be reposted. Please click on 'Repost' button to update."
				)
			);
			this.frm
				.add_custom_button(__("Repost Accounting Entries"), () => {
					this.frm.call({
						doc: this.frm.doc,
						method: "repost_accounting_entries",
						freeze: true,
						freeze_message: __("Reposting..."),
						callback: (r) => {
							if (!r.exc) {
								frappe.msgprint(__("Accounting Entries are reposted"));
								me.frm.refresh();
							}
						},
					});
				})
				.removeClass("btn-default")
				.addClass("btn-warning");
		}

		if (this.frm.doc.is_return) {
			this.frm.return_print_format = "Sales Invoice Return";
		}

		this.show_general_ledger();
		erpnext.accounts.ledger_preview.show_accounting_ledger_preview(this.frm);

		if (doc.docstatus == 1 && doc.outstanding_amount != 0) {
			this.frm.add_custom_button(__("Payment"), () => this.make_payment_entry(), __("Create"));
			this.frm.page.set_inner_btn_group_as_primary(__("Create"));
		}

		if (doc.docstatus == 1 && !doc.is_return) {


			if (doc.outstanding_amount >= 0 || Math.abs(flt(doc.outstanding_amount)) < flt(doc.grand_total)) {
				cur_frm.add_custom_button(__("Return / Credit Note"), this.make_sales_return, __("Create"));
				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}

			if (doc.outstanding_amount > 0) {
				cur_frm.add_custom_button(
					__("Payment Request"),
					function () {
						me.make_payment_request();
					},
					__("Create")
				);

				const payment_is_overdue = doc.payment_schedule
					.map((row) => Date.parse(row.due_date) < Date.now())
					.reduce((prev, current) => prev || current);

				if (payment_is_overdue) {
					this.frm.add_custom_button(
						__("Dunning"),
						() => {
							this.frm.events.create_dunning(this.frm);
						},
						__("Create")
					);
				}
			}
		}

	

		this.set_default_print_format();
		// this.calculate_net_total()
		erpnext.accounts.unreconcile_payment.add_unreconcile_btn(me.frm);

}

	on_submit(doc, dt, dn) {
		var me = this;

		super.on_submit();
		if (frappe.get_route()[0] != "Form") {
			return;
		}
	}

	set_default_print_format() {
		// set default print format to POS type or Credit Note
		if (cur_frm.doc.is_pos) {
			if (cur_frm.pos_print_format) {
				cur_frm.meta._default_print_format = cur_frm.meta.default_print_format;
				cur_frm.meta.default_print_format = cur_frm.pos_print_format;
			}
		} else if (cur_frm.doc.is_return && !cur_frm.meta.default_print_format) {
			if (cur_frm.return_print_format) {
				cur_frm.meta._default_print_format = cur_frm.meta.default_print_format;
				cur_frm.meta.default_print_format = cur_frm.return_print_format;
			}
		} else {
			if (cur_frm.meta._default_print_format) {
				cur_frm.meta.default_print_format = cur_frm.meta._default_print_format;
				cur_frm.meta._default_print_format = null;
			} else if (
				in_list(
					[cur_frm.pos_print_format, cur_frm.return_print_format],
					cur_frm.meta.default_print_format
				)
			) {
				cur_frm.meta.default_print_format = null;
				cur_frm.meta._default_print_format = null;
			}
		}
	}
	tc_name() {
		this.get_terms();
	}
	customer() {
		if (this.frm.doc.is_pos) {
			var pos_profile = this.frm.doc.pos_profile;
		}
		var me = this;
		if (this.frm.updating_party_details) return;

		if (this.frm.doc.__onload && this.frm.doc.__onload.load_after_mapping) return;

		erpnext.utils.get_party_details(
			this.frm,
			"erpnext.accounts.party.get_party_details",
			{
				posting_date: this.frm.doc.posting_date,
				party: this.frm.doc.customer,
				party_type: "Customer",
				account: this.frm.doc.debit_to,
				price_list: this.frm.doc.selling_price_list,
				pos_profile: pos_profile,
			},
			function () {
				me.apply_pricing_rule();
			}
		);

		if (this.frm.doc.customer) {
			frappe.call({
				method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.get_loyalty_programs",
				args: {
					customer: this.frm.doc.customer,
				},
				callback: function (r) {
					if (r.message && r.message.length > 1) {
						select_loyalty_program(me.frm, r.message);
					}
				},
			});
		}
	}



	debit_to() {
		var me = this;
		if (this.frm.doc.debit_to) {
			me.frm.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					fieldname: "account_currency",
					filters: { name: me.frm.doc.debit_to },
				},
				callback: function (r, rt) {
					if (r.message) {
						me.frm.set_value("party_account_currency", r.message.account_currency);
						me.set_dynamic_labels();
					}
				},
			});
		}
	}

	allocated_amount() {
		this.calculate_total_advance();
		this.frm.refresh_fields();
	}

	write_off_outstanding_amount_automatically() {
		if (cint(this.frm.doc.write_off_outstanding_amount_automatically)) {
			frappe.model.round_floats_in(this.frm.doc, ["grand_total", "paid_amount"]);
			// this will make outstanding amount 0
			this.frm.set_value(
				"write_off_amount",
				flt(
					this.frm.doc.grand_total - this.frm.doc.paid_amount - this.frm.doc.total_advance,
					precision("write_off_amount")
				)
			);
		}

		this.calculate_outstanding_amount(false);
		this.frm.refresh_fields();
	}

	write_off_amount() {
		this.set_in_company_currency(this.frm.doc, ["write_off_amount"]);
		this.write_off_outstanding_amount_automatically();
	}

	items_add(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.frm.script_manager.copy_from_first_row("items", row, [
			"income_account",
			"discount_account",
			"cost_center",
		]);
	}

	set_dynamic_labels() {
		super.set_dynamic_labels();
		this.frm.events.hide_fields(this.frm);
	}

	items_on_form_rendered() {
		erpnext.setup_serial_or_batch_no();
	}

	packed_items_on_form_rendered(doc, grid_row) {
		erpnext.setup_serial_or_batch_no();
	}

	make_sales_return() {
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return",
			frm: cur_frm,
		});
	}


	is_pos(frm) {
		this.set_pos_data();
	}

	pos_profile() {
		this.frm.doc.taxes = [];
		this.set_pos_data();
	}

	set_pos_data() {
		if (this.frm.doc.is_pos) {
			this.frm.set_value("allocate_advances_automatically", 0);
			if (!this.frm.doc.company) {
				this.frm.set_value("is_pos", 0);
				frappe.msgprint(__("Please specify Company to proceed"));
			} else {
				var me = this;
				return this.frm.call({
					doc: me.frm.doc,
					method: "set_missing_values",
					callback: function (r) {
						if (!r.exc) {
							if (r.message && r.message.print_format) {
								me.frm.pos_print_format = r.message.print_format;
							}
							me.frm.trigger("update_stock");
							if (me.frm.doc.taxes_and_charges) {
								me.frm.script_manager.trigger("taxes_and_charges");
							}

							frappe.model.set_default_values(me.frm.doc);
							me.set_dynamic_labels();
							me.calculate_taxes_and_totals();
						}
					},
				});
			}
		} else this.frm.trigger("refresh");
	}

	amount() {
		this.write_off_outstanding_amount_automatically();
	}

	change_amount() {
		if (this.frm.doc.paid_amount > this.frm.doc.grand_total) {
			this.calculate_write_off_amount();
		} else {
			this.frm.set_value("change_amount", 0.0);
			this.frm.set_value("base_change_amount", 0.0);
		}

		this.frm.refresh_fields();
	}

	loyalty_amount() {
		this.calculate_outstanding_amount();
		this.frm.refresh_field("outstanding_amount");
		this.frm.refresh_field("paid_amount");
		this.frm.refresh_field("base_paid_amount");
	}

	currency() {
		var me = this;
		super.currency();
		if (this.frm.doc.timesheets) {
			this.frm.doc.timesheets.forEach((d) => {
				let row = frappe.get_doc(d.doctype, d.name);
				set_timesheet_detail_rate(row.doctype, row.name, me.frm.doc.currency, row.timesheet_detail);
			});
			this.frm.trigger("calculate_timesheet_totals");
		}
	}

	is_cash_or_non_trade_discount() {
		this.frm.set_df_property(
			"additional_discount_account",
			"hidden",
			1 - this.frm.doc.is_cash_or_non_trade_discount
		);
		this.frm.set_df_property(
			"additional_discount_account",
			"reqd",
			this.frm.doc.is_cash_or_non_trade_discount
		);

		if (!this.frm.doc.is_cash_or_non_trade_discount) {
			this.frm.set_value("additional_discount_account", "");
		}

		this.calculate_taxes_and_totals();
	}

	// ------------------------------ added by alaalsalam

	

	calculate_net_total() {
		var me = this;
		this.frm.doc.total_commission_rate = this.frm.doc.total_buying_rate = this.frm.doc.total_qty = this.frm.doc.total = this.frm.doc.base_total = this.frm.doc.net_total = this.frm.doc.base_net_total = 0.0;

		$.each(this.frm._items || [], function(i, item) {
			me.frm.doc.total_commission_rate += item.commission_rate;
			me.frm.doc.total_buying_rate += item.buying_rate;
			me.frm.doc.total += item.amount;
			me.frm.doc.total_qty += item.qty;
			me.frm.doc.base_total += item.base_amount;
			me.frm.doc.net_total += item.net_amount;
			me.frm.doc.base_net_total += item.base_net_amount;
		});
	}
	
	calculate_item_values() {
		var me = this;

			for (const item of this.frm._items || []) {
				frappe.model.round_floats_in(item);
				item.net_rate = item.rate;
				item.qty = item.qty === undefined ? (me.frm.doc.is_return ? -1 : 1) : item.qty;
				

				if (!(me.frm.doc.is_return || me.frm.doc.is_debit_note)) {
					item.net_amount = item.amount = flt(item.rate * item.qty, precision("amount", item));
					item.byuing_amount = flt(item.buying_rate * item.qty, precision("amount", item));
					item.commission_amount = flt(item.commission_rate * item.qty, precision("amount", item));
				}
				else {
					// allow for '0' qty on Credit/Debit notes
					let qty = flt(item.qty);
					if (!qty) {
						qty = (me.frm.doc.is_debit_note ? 1 : -1);
						if (me.frm.doc.doctype !== "Purchase Receipt" && me.frm.doc.is_return === 1) {
							// In case of Purchase Receipt, qty can be 0 if all items are rejected
							qty = flt(item.qty);
						}
					}

					item.net_amount = item.amount = flt(item.rate * qty, precision("amount", item));
					item.byuing_amount = flt(item.buying_rate * item.qty, precision("amount", item));

				}

				item.item_tax_amount = 0.0;
				item.total_weight = flt(item.weight_per_unit * item.stock_qty);
				
				if (item.commission_type && item.commission_rate) {
					if (item.commission_type === "Percentage") {
					  item.commission_rate = flt(
						item.rate * (item.commission_percentage / 100),
						precision("commission_rate")
					  );
					  item.buying_rate = flt(item.rate - (item.rate * (item.commission_percentage / 100)), precision("amount", item));
					} else if (item.commission_type === "Amount") {
					  item.commission_percentage = flt(
						(item.commission_rate * 100) / item.rate,
						precision("commission_percentage")
					  );
					  item.buying_rate = flt(item.rate - item.commission_rate, precision("amount", item));
					}
				  }

				me.set_in_company_currency(item, ["price_list_rate", "rate", "amount", "net_rate", "net_amount","buying_rate"]);
			}
		
	}
	calculate_discount_amount() {
		console.log("---------------calculate_discount_amount------------------")
		if (frappe.meta.get_docfield(this.frm.doc.doctype, "commission_type")) {
			console.log("---------------f (frappe.meta.get_docfield(this.frm.doc.doctype, commission_type------------------")

			this.set_commission_rate()
		}
		if (frappe.meta.get_docfield(this.frm.doc.doctype, "discount_amount")) {
			this.set_discount_amount();
			this.set_commission_rate()
			this.apply_discount_amount();
		}
	}
	set_discount_amount() {
		if(this.frm.doc.additional_discount_percentage) {
			this.frm.doc.discount_amount = flt(flt(this.frm.doc[frappe.scrub(this.frm.doc.apply_discount_on)])
				* this.frm.doc.additional_discount_percentage / 100, precision("discount_amount"));
		}
	}
	set_commission_rate() {
		console.log("------------set_commission_rate---------------------")

	  }
	apply_discount_amount() {
		var me = this;
		var distributed_amount = 0.0;
		this.frm.doc.base_discount_amount = 0.0;

		if (this.frm.doc.discount_amount) {
			if(!this.frm.doc.apply_discount_on)
				frappe.throw(__("Please select Apply Discount On"));

			this.frm.doc.base_discount_amount = flt(this.frm.doc.discount_amount * this.frm.doc.conversion_rate,
				precision("base_discount_amount"));

			if (this.frm.doc.apply_discount_on == "Grand Total" && this.frm.doc.is_cash_or_non_trade_discount) {
				return;
			}

			var total_for_discount_amount = this.get_total_for_discount_amount();
			var net_total = 0;
			// calculate item amount after Discount Amount
			if (total_for_discount_amount) {
				$.each(this.frm._items || [], function(i, item) {
					distributed_amount = flt(me.frm.doc.discount_amount) * item.net_amount / total_for_discount_amount;
					item.net_amount = flt(item.net_amount - distributed_amount,
						precision("base_amount", item));
					net_total += item.net_amount;

					// discount amount rounding loss adjustment if no taxes
					if ((!(me.frm.doc.taxes || []).length || total_for_discount_amount==me.frm.doc.net_total || (me.frm.doc.apply_discount_on == "Net Total"))
							&& i == (me.frm._items || []).length - 1) {
						var discount_amount_loss = flt(me.frm.doc.net_total - net_total
							- me.frm.doc.discount_amount, precision("net_total"));
						item.net_amount = flt(item.net_amount + discount_amount_loss,
							precision("net_amount", item));
					}
					item.net_rate = item.qty ? flt(item.net_amount / item.qty, precision("net_rate", item)) : 0;
					me.set_in_company_currency(item, ["net_rate", "net_amount"]);
				});

				this.discount_amount_applied = true;
				this._calculate_taxes_and_totals();
			}
		}
	}

};

// for backward compatibility: combine new and previous states
extend_cscript(cur_frm.cscript, new erpnext.accounts.SalesInvoiceController({ frm: cur_frm }));



cur_frm.fields_dict.cash_bank_account.get_query = function (doc) {
	return {
		filters: [
			["Account", "account_type", "in", ["Cash", "Bank"]],
			["Account", "root_type", "=", "Asset"],
			["Account", "is_group", "=", 0],
			["Account", "company", "=", doc.company],
		],
	};
};

cur_frm.fields_dict.write_off_account.get_query = function (doc) {
	return {
		filters: {
			report_type: "Profit and Loss",
			is_group: 0,
			company: doc.company,
		},
	};
};

// Write off cost center
//-----------------------
cur_frm.fields_dict.write_off_cost_center.get_query = function (doc) {
	return {
		filters: {
			is_group: 0,
			company: doc.company,
		},
	};
};

cur_frm.cscript.income_account = function (doc, cdt, cdn) {
	erpnext.utils.copy_value_in_all_rows(doc, cdt, cdn, "items", "income_account");
};

cur_frm.cscript.expense_account = function (doc, cdt, cdn) {
	erpnext.utils.copy_value_in_all_rows(doc, cdt, cdn, "items", "expense_account");
};

cur_frm.cscript.cost_center = function (doc, cdt, cdn) {
	erpnext.utils.copy_value_in_all_rows(doc, cdt, cdn, "items", "cost_center");
};

cur_frm.set_query("debit_to", function (doc) {
	return {
		filters: {
			account_type: "Receivable",
			is_group: 0,
			company: doc.company,
		},
	};
});

frappe.ui.form.on("Service Invoice", {
	setup: function (frm) {
		frm.fields_dict["items"].grid.get_field("item_code").get_query = function (doc) {
			return {
				filters: {
					is_stock_item: 0,
					disabled: 0,
					is_fixed_asset:0
				},
			};
		};

		frm.add_fetch("customer", "tax_id", "tax_id");
		frm.add_fetch("payment_term", "invoice_portion", "invoice_portion");
		frm.add_fetch("payment_term", "description", "description");

		frm.set_df_property("packed_items", "cannot_add_rows", true);
		frm.set_df_property("packed_items", "cannot_delete_rows", true);

		frm.set_query("account_for_change_amount", function () {
			return {
				filters: {
					account_type: ["in", ["Cash", "Bank"]],
					company: frm.doc.company,
					is_group: 0,
				},
			};
		});

		frm.set_query("unrealized_profit_loss_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					root_type: "Liability",
				},
			};
		});

		frm.set_query("adjustment_against", function () {
			return {
				filters: {
					company: frm.doc.company,
					customer: frm.doc.customer,
					docstatus: 1,
				},
			};
		});

		frm.set_query("additional_discount_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					report_type: "Profit and Loss",
				},
			};
		});

		frm.set_query("income_account", "items", function () {
			return {
				query: "erpnext.controllers.queries.get_income_account",
				filters: {
					company: frm.doc.company,
					disabled: 0,
				},
			};
		});

		

		(frm.custom_make_buttons = {
			"Delivery Note": "Delivery",
			"Sales Invoice": "Return / Credit Note",
			"Payment Request": "Payment Request",
			"Payment Entry": "Payment",
		}),

			(frm.fields_dict["timesheets"].grid.get_field("time_sheet").get_query = function (doc, cdt, cdn) {
				return {
					query: "erpnext.projects.doctype.timesheet.timesheet.get_timesheet",
					filters: { project: doc.project },
				};
			});
				
		// Cost Center in Details Table
		// -----------------------------
		cur_frm.fields_dict["items"].grid.get_field("cost_center").get_query = function (doc) {
			return {
				filters: {
					company: doc.company,
					is_group: 1,
				},
			};
		};

		// discount account
		frm.fields_dict["items"].grid.get_field("discount_account").get_query = function (doc) {
			return {
				filters: {
					report_type: "Profit and Loss",
					company: doc.company,
					is_group: 0,
				},
			};
		};

		frm.fields_dict["items"].grid.get_field("deferred_revenue_account").get_query = function (doc) {
			return {
				filters: {
					root_type: "Liability",
					company: doc.company,
					is_group: 0,
				},
			};
		};

		frm.set_query("company_address", function (doc) {
			if (!doc.company) {
				frappe.throw(__("Please set Company"));
			}

			return {
				query: "frappe.contacts.doctype.address.address.address_query",
				filters: {
					link_doctype: "Company",
					link_name: doc.company,
				},
			};
		});

		frm.set_query("pos_profile", function (doc) {
			if (!doc.company) {
				frappe.throw(__("Please set Company"));
			}

			return {
				query: "erpnext.accounts.doctype.pos_profile.pos_profile.pos_profile_query",
				filters: {
					company: doc.company,
				},
			};
		});

		// set get_query for loyalty redemption account
		frm.fields_dict["loyalty_redemption_account"].get_query = function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			};
		};

		// set get_query for loyalty redemption cost center
		frm.fields_dict["loyalty_redemption_cost_center"].get_query = function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			};
		};

		frm.fields_dict["items"].grid.get_field("item_code").get_query = function (doc) {
			return {
				filters: {
					is_stock_item: 0,
					disabled: 0,
					is_fixed_asset:0
				},
			};
		};

	},
	// When multiple companies are set up. in case company name is changed set default company address
	company: function (frm) {
		if (frm.doc.company) {
			frappe.call({
				method: "erpnext.setup.doctype.company.company.get_default_company_address",
				args: { name: frm.doc.company, existing_address: frm.doc.company_address || "" },
				debounce: 2000,
				callback: function (r) {
					if (r.message) {
						frm.set_value("company_address", r.message);
					} else {
						frm.set_value("company_address", "");
					}
				},
			});
		}
	},

	onload: function (frm) {
		frm.redemption_conversion_factor = null;
	},

	update_stock: function (frm, dt, dn) {
		frm.events.hide_fields(frm);
		frm.trigger("reset_posting_time");
	},

	redeem_loyalty_points: function (frm) {
		frm.events.get_loyalty_details(frm);
	},

	loyalty_points: function (frm) {
		if (frm.redemption_conversion_factor) {
			frm.events.set_loyalty_points(frm);
		} else {
			frappe.call({
				method: "erpnext.accounts.doctype.loyalty_program.loyalty_program.get_redeemption_factor",
				args: {
					loyalty_program: frm.doc.loyalty_program,
				},
				callback: function (r) {
					if (r) {
						frm.redemption_conversion_factor = r.message;
						frm.events.set_loyalty_points(frm);
					}
				},
			});
		}
	},

	hide_fields: function (frm) {
		let doc = frm.doc;
		var parent_fields = [
			"project",
			"due_date",
			"is_opening",
			"source",
			"total_advance",
			"get_advances",
			"advances",
			"from_date",
			"to_date",
		];

		if (cint(doc.is_pos) == 1) {
			hide_field(parent_fields);
		} else {
			for (var i in parent_fields) {
				var docfield = frappe.meta.docfield_map[doc.doctype][parent_fields[i]];
				if (!docfield.hidden) unhide_field(parent_fields[i]);
			}
		}

		frm.refresh_fields();
	},

	get_loyalty_details: function (frm) {
		if (frm.doc.customer && frm.doc.redeem_loyalty_points) {
			frappe.call({
				method: "erpnext.accounts.doctype.loyalty_program.loyalty_program.get_loyalty_program_details",
				args: {
					customer: frm.doc.customer,
					loyalty_program: frm.doc.loyalty_program,
					expiry_date: frm.doc.posting_date,
					company: frm.doc.company,
				},
				callback: function (r) {
					if (r) {
						frm.set_value("loyalty_redemption_account", r.message.expense_account);
						frm.set_value("loyalty_redemption_cost_center", r.message.cost_center);
						frm.redemption_conversion_factor = r.message.conversion_factor;
					}
				},
			});
		}
	},

	set_loyalty_points: function (frm) {
		if (frm.redemption_conversion_factor) {
			let loyalty_amount = flt(
				frm.redemption_conversion_factor * flt(frm.doc.loyalty_points),
				precision("loyalty_amount")
			);
			var remaining_amount =
				flt(frm.doc.grand_total) - flt(frm.doc.total_advance) - flt(frm.doc.write_off_amount);
			if (frm.doc.grand_total && remaining_amount < loyalty_amount) {
				let redeemable_points = parseInt(remaining_amount / frm.redemption_conversion_factor);
				frappe.throw(__("You can only redeem max {0} points in this order.", [redeemable_points]));
			}
			frm.set_value("loyalty_amount", loyalty_amount);
		}
	},

	project: function (frm) {
		if (frm.doc.project) {
			frm.events.add_timesheet_data(frm, {
				project: frm.doc.project,
			});
		}
	},

	async add_timesheet_data(frm, kwargs) {
		if (kwargs === "Sales Invoice") {
			// called via frm.trigger()
			kwargs = Object();
		}

		if (!Object.prototype.hasOwnProperty.call(kwargs, "project") && frm.doc.project) {
			kwargs.project = frm.doc.project;
		}

		const timesheets = await frm.events.get_timesheet_data(frm, kwargs);
		return frm.events.set_timesheet_data(frm, timesheets);
	},

	async get_timesheet_data(frm, kwargs) {
		return frappe
			.call({
				method: "erpnext.projects.doctype.timesheet.timesheet.get_projectwise_timesheet_data",
				args: kwargs,
			})
			.then((r) => {
				if (!r.exc && r.message.length > 0) {
					return r.message;
				} else {
					return [];
				}
			});
	},

	set_timesheet_data: function (frm, timesheets) {
		frm.clear_table("timesheets");
		timesheets.forEach(async (timesheet) => {
			if (frm.doc.currency != timesheet.currency) {
				const exchange_rate = await frm.events.get_exchange_rate(
					frm,
					timesheet.currency,
					frm.doc.currency
				);
				frm.events.append_time_log(frm, timesheet, exchange_rate);
			} else {
				frm.events.append_time_log(frm, timesheet, 1.0);
			}
		});
		frm.trigger("calculate_timesheet_totals");
		frm.refresh();
	},

	async get_exchange_rate(frm, from_currency, to_currency) {
		if (
			frm.exchange_rates &&
			frm.exchange_rates[from_currency] &&
			frm.exchange_rates[from_currency][to_currency]
		) {
			return frm.exchange_rates[from_currency][to_currency];
		}

		return frappe.call({
			method: "erpnext.setup.utils.get_exchange_rate",
			args: {
				from_currency,
				to_currency,
			},
			callback: function (r) {
				if (r.message) {
					// cache exchange rates
					frm.exchange_rates = frm.exchange_rates || {};
					frm.exchange_rates[from_currency] = frm.exchange_rates[from_currency] || {};
					frm.exchange_rates[from_currency][to_currency] = r.message;
				}
			},
		});
	},

	append_time_log: function (frm, time_log, exchange_rate) {
		const row = frm.add_child("timesheets");
		row.activity_type = time_log.activity_type;
		row.description = time_log.description;
		row.time_sheet = time_log.time_sheet;
		row.from_time = time_log.from_time;
		row.to_time = time_log.to_time;
		row.billing_hours = time_log.billing_hours;
		row.billing_amount = flt(time_log.billing_amount) * flt(exchange_rate);
		row.timesheet_detail = time_log.name;
		row.project_name = time_log.project_name;
	},

	calculate_timesheet_totals: function (frm) {
		frm.set_value(
			"total_billing_amount",
			frm.doc.timesheets.reduce((a, b) => a + (b["billing_amount"] || 0.0), 0.0)
		);
		frm.set_value(
			"total_billing_hours",
			frm.doc.timesheets.reduce((a, b) => a + (b["billing_hours"] || 0.0), 0.0)
		);
	},

	refresh: function (frm) {
		if (frm.doc.is_debit_note) {
			frm.set_df_property("return_against", "label", __("Adjustment Against"));
		}

		frm.set_query("item_code", "items", function () {
			return {
				filters: {
					is_stock_item: 0,
					disabled: 0,
					is_fixed_asset:0
				},
			};
		});
	},

	
});

frappe.ui.form.on("Sales Invoice Timesheet", {
	timesheets_remove(frm) {
		frm.trigger("calculate_timesheet_totals");
	},
});

var set_timesheet_detail_rate = function (cdt, cdn, currency, timelog) {
	frappe.call({
		method: "erpnext.projects.doctype.timesheet.timesheet.get_timesheet_detail_rate",
		args: {
			timelog: timelog,
			currency: currency,
		},
		callback: function (r) {
			if (!r.exc && r.message) {
				frappe.model.set_value(cdt, cdn, "billing_amount", r.message);
			}
		},
	});
};

var select_loyalty_program = function (frm, loyalty_programs) {
	var dialog = new frappe.ui.Dialog({
		title: __("Select Loyalty Program"),
		fields: [
			{
				label: __("Loyalty Program"),
				fieldname: "loyalty_program",
				fieldtype: "Select",
				options: loyalty_programs,
				default: loyalty_programs[0],
			},
		],
	});

	dialog.set_primary_action(__("Set Loyalty Program"), function () {
		dialog.hide();
		return frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: "Customer",
				name: frm.doc.customer,
				fieldname: "loyalty_program",
				value: dialog.get_value("loyalty_program"),
			},
			callback: function (r) {},
		});
	});

	dialog.show();
};


