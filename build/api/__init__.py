import frappe
from frappe import _, throw
from frappe.utils import add_days, getdate, nowdate
from .employee import (
    get_employee_from_user,
    get_employee_working_hours,
    get_employee_daily_working_norm,
    get_week_dates,
    get_employee_leaves,
    get_holidays,
)

now = nowdate()

# http://build.localhost/api/method/build.api.get?employee=HR-EMP-00001

@frappe.whitelist()
def get(employee: str, start_date=now, max_week: int = 4):
    from time import time

    start_time = time()
    res = get_timesheet_data(employee, start_date, max_week)
    end_time = time()
    res["time"] = f"{end_time - start_time} seconds"
    return res


def get_timesheet_data(employee: str, start_date=now, max_week: int = 4):
    """Get timesheet data for the given employee for the given number of weeks."""
    if not employee:
        employee = get_employee_from_user()

    def generate_week_data(
        start_date, max_week, employee=None, leaves=None, holidays=None
    ):
        data = {}
        daily_norm = get_employee_daily_working_norm()
        for i in range(max_week):
            week_dates = get_week_dates(start_date)
            cache_key = f'{week_dates.get("start_date")}-{week_dates.get("end_date")}'

            week_key = week_dates["key"]

            cached_data = frappe.cache.hget(f"timesheet:{employee}", cache_key)

            if cached_data:
                data[week_dates["key"]] = cached_data
                start_date = add_days(getdate(week_dates["end_date"]), 1)
                continue

            tasks, total_hours = ({}, 0)
            if employee:
                holiday_dates = (
                    [holiday["holiday_date"] for holiday in holidays]
                    if holidays
                    else []
                )
                tasks, total_hours = get_timesheet(week_dates["dates"], employee)

                leave_total = 0
                week_leaves = [
                    leave
                    for leave in leaves
                    if leave["from_date"] <= week_dates["dates"][-1]
                    and leave["to_date"] >= week_dates["dates"][0]
                ]
                for leave in week_leaves:
                    if leave["half_day"]:
                        leave_total += daily_norm / 2
                    else:
                        num_days = 0
                        for date in week_dates["dates"]:
                            if (
                                date not in holiday_dates
                                and leave["from_date"] <= date <= leave["to_date"]
                            ):
                                num_days += 1
                        leave_total += daily_norm * num_days

            data[week_key] = {
                **week_dates,
                "total_hours": total_hours,
                "tasks": tasks,
            }
            start_date = add_days(getdate(week_dates["start_date"]), -1)
            frappe.cache.hset(f"timesheet:{employee}", cache_key, data[week_key])
        return data

    hour_detail = get_employee_working_hours()
    res = {**hour_detail}

    if not employee and frappe.session.user == "Administrator":
        res["data"] = generate_week_data(start_date, max_week)
        res["holidays"] = []
        res["leaves"] = []
        return res

    if not frappe.db.exists("Employee", employee):
        throw(_("No employee found for current user."), frappe.DoesNotExistError)

    holidays = get_holidays(
        employee,
        add_days(start_date, -max_week * 7),
        add_days(start_date, max_week * 7),
    )

    leaves = get_employee_leaves(
        start_date=add_days(start_date, -max_week * 7),
        end_date=add_days(start_date, max_week * 7),
        employee=employee,
    )
    res["leaves"] = leaves
    res["holidays"] = holidays
    res["data"] = generate_week_data(start_date, max_week, employee, leaves, holidays)
    return res


def get_timesheet(dates: list, employee: str):
    """Return the time entry from Timesheet Detail child table based on the list of dates and for the given employee.
    example:
        {
            "Task 1": {
                "name": "TS-00001",
                "data": [
                    {
                        "task": "Task 1",
                        "name": "TS-00001",
                        "hours": 8,
                        "description": "Task 1 description",
                        "from_time": "2021-08-01",
                        "to_time": "2021-08-01",
                    },
                    ...
                ]
            },
            ...
        }
    """
    data = {}
    total_hours = 0
    timesheet_logs = frappe.get_all(
        "Timesheet",
        filters={
            "employee": employee,
            "start_date": ["in", dates],
            "docstatus": ["!=", 2],
        },
        fields=["time_logs.name"],
    )
    if not timesheet_logs:
        return [data, total_hours]
    timesheet_logs = [
        frappe.get_doc("Timesheet Detail", ts.name) for ts in timesheet_logs
    ]

    task_ids = [ts.task for ts in timesheet_logs if ts.task]
    task_details = frappe.get_all(
        "Task",
        filters={"name": ["in", task_ids]},
        fields=[
            "name",
            "subject",
            "project.project_name as project_name",
            "project",
            "expected_time",
            "actual_time",
            "status",
            "_liked_by",
        ],
    )
    task_details_dict = {task["name"]: task for task in task_details}
    for log in timesheet_logs:
        total_hours += log.hours
        if not log.task:
            continue
        task = task_details_dict.get(log.task)
        if not task:
            continue
        task_name = task["name"]
        if task_name not in data:
            data[task_name] = {
                "name": task_name,
                "subject": task["subject"],
                "data": [],
                "project_name": task["project_name"],
                "project": task["project"],
                "expected_time": task["expected_time"],
                "actual_time": task["actual_time"],
                "status": task["status"],
                "_liked_by": task["_liked_by"],
            }
        data[task_name]["data"].append(log.as_dict())

    return [data, total_hours]
