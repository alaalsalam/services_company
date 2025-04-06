import frappe
from frappe.tests.utils import FrappeTestCase

class TestTaskManager(FrappeTestCase):
    def test_create_task(self):
        # إنشاء مستند جديد مع تصحيح اسم الحقل
        task = frappe.get_doc({
            "doctype": "Task Manager",
            "task_name": "Test Task",  # إزالة المسافة الزائدة
            "description": "This is a test task",
            "status": "Open"
        })
        
        # إدخال المستند في قاعدة البيانات
        task.insert()
        
        # تنفيذ commit لحفظ التغييرات في قاعدة البيانات
        frappe.db.commit()
        
        # تأكد من أن المستند تم إنشاؤه بشكل صحيح
        self.assertEqual(task.task_name, "Test Task")
        self.assertEqual(task.status, "Open")

        # تحقق من وجود المستند في قاعدة البيانات
        created_task = frappe.get_doc("Task Manager", task.name)
        self.assertEqual(created_task.task_name, "Test Task")
