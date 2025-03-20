def validate(doc, method=None):

    from frappe.utils import get_first_day_of_week, get_last_day_of_week, get_date_str
    import frappe

    start_date = get_date_str(get_first_day_of_week(doc.start_date))
    end_date = get_date_str(get_last_day_of_week(doc.start_date))
    frappe.cache.hdel(f"timesheet:{doc.employee}", f"{start_date}-{end_date}")
