import frappe
from frappe.utils import add_days, get_first_day_of_week, get_last_day_of_week, getdate


@frappe.whitelist()
def get_employee_from_user(user=None):
    user = frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user})


def get_user_from_employee(employee: str):
    return frappe.get_value("Employee", employee, "user_id")


@frappe.whitelist()
def get_employee_working_hours():
    return {"working_hour": 8, "working_frequency": "Per Day"}


def get_employee_daily_working_norm() -> int:
    return 8


def get_week_dates(date, ignore_weekend=False):
    """Returns the dates map with dates and other details.
    example:
        {
            "start_date": "2021-08-01",
            "end_date": "2021-08-07",
            "key": "Aug 01 - Aug 07",
            "dates": [
                "2021-08-01",
                "2021-08-02",
                ...
            ]
        }
    """

    dates = []
    data = {}
    now = getdate()
    start_date = get_first_day_of_week(date)
    end_date = get_last_day_of_week(date)

    if start_date <= now <= end_date:
        key = "This Week"
    else:
        if ignore_weekend:
            end_date_for_key = add_days(end_date, -2)
        else:
            end_date_for_key = end_date
        key = f"{start_date.strftime('%b %d')} - {end_date_for_key.strftime('%b %d')}"

    data = {"start_date": start_date, "end_date": end_date, "key": key}

    while start_date <= end_date:
        if ignore_weekend and start_date.weekday() in [5, 6]:
            start_date = add_days(start_date, 1)
            continue
        dates.append(start_date)
        start_date = add_days(start_date, 1)
    data["dates"] = dates
    return data


def get_employee_leaves(employee: str, start_date: str, end_date: str):
    """Get the total leave days for given employee for given time range."""

    # nosemgrep
    return frappe.db.sql(
        """
        SELECT from_date, to_date, half_day, half_day_date,total_leave_days,name FROM `tabLeave Application`
            WHERE employee = %(employee)s
            AND (
                (from_date <= %(start_date)s AND to_date >= %(start_date)s)
                OR (from_date >= %(start_date)s AND to_date <= %(end_date)s)
                OR (from_date <= %(end_date)s AND to_date >= %(end_date)s)
                OR (from_date <= %(start_date)s AND to_date >= %(end_date)s)
            )
            AND (docstatus=1 OR docstatus=0)
            AND (status = 'Approved' OR status = 'Open')
            ORDER BY from_date, to_date;
        """,
        {"employee": employee, "start_date": start_date, "end_date": end_date},
        as_dict=True,
    )  # nosemgrep


def get_holidays(employee: str, start_date: str, end_date: str):

    from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

    holiday_name = get_holiday_list_for_employee(employee, raise_exception=False)
    if not holiday_name:
        return []
    holidays = frappe.get_all(
        "Holiday",
        filters={
            "parent": holiday_name,
            "holiday_date": ["between", (getdate(start_date), getdate(end_date))],
        },
        fields=["holiday_date", "description", "weekly_off"],
    )
    return holidays
