from . import __version__ as app_version

app_name = "services_company"
app_title = "Services Company"
app_publisher = "alaalsalam"
app_description = "Custom app dedicated to service companies that supports creating a service invoice, submitting a purchase record, a sale record, and the profit percentage in the same doctype"
app_email = "alaalsalam101@gmail.com"
app_license = "MIT"

override_doctype_class = {
    # "Sales Invoice": "services_company.services_company.overrides.sales_invoice.CustomSalesInvoice",
    #"AccountsController": "services_company.services_company.overrides.accounts_controller.CustomAccountsController"
    "Purchase Invoice":"services_company.services_company.overrides.purchase_invoice.CustomSalesInvoices",
    "Journal Entry":"services_company.services_company.overrides.journal_entry.CustomJournalEntry"
 
}
doctype_js = {
    
    
    # "Sales Invoice" : "public/js/sales_invoice.js",
    "Purchase Invoice" : "public/js/purchase_invoice.js",
    "Delivery Note":"public/js/delivery_note.js"
   

 

 }
doc_events = {
    "Payment Entry": {
        "on_submit": "services_company.services_company.api.update_service_invoice"
    }
}
# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/services_company/css/services_company.css"
# app_include_js = "/assets/services_company/js/services_company.js"

# include js, css files in header of web template
# web_include_css = "/assets/services_company/css/services_company.css"
# web_include_js = "/assets/services_company/js/services_company.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "services_company/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "services_company.utils.jinja_methods",
#	"filters": "services_company.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "services_company.install.before_install"
# after_install = "services_company.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "services_company.uninstall.before_uninstall"
# after_uninstall = "services_company.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "services_company.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
#	"*": {
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"services_company.tasks.all"
#	],
#	"daily": [
#		"services_company.tasks.daily"
#	],
#	"hourly": [
#		"services_company.tasks.hourly"
#	],
#	"weekly": [
#		"services_company.tasks.weekly"
#	],
#	"monthly": [
#		"services_company.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "services_company.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "services_company.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "services_company.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["services_company.utils.before_request"]
# after_request = ["services_company.utils.after_request"]

# Job Events
# ----------
# before_job = ["services_company.utils.before_job"]
# after_job = ["services_company.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"services_company.auth.validate"
# ]
