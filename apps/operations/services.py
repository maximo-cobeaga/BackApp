"""Daily-control export services."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import Workbook

from apps.operations.models import DailyControlEntry
from apps.tenancy.models import Organization


DAILY_CONTROL_HEADERS = [
    "Fecha",
    "Cliente",
    "Sede",
    "Tarea",
    "Tecnología",
    "Objeto",
    "Resultado",
    "Observación",
    "Ticket",
]


def build_daily_control_workbook(*, organization: Organization, control_date: date) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Control diario"
    sheet.append(DAILY_CONTROL_HEADERS)

    entries = DailyControlEntry.objects.select_related(
        "backup_job__managed_customer",
        "backup_job__site",
        "backup_job__technology",
        "protected_object",
    ).filter(organization=organization, control_date=control_date)

    for entry in entries:
        sheet.append(
            [
                entry.control_date.isoformat(),
                entry.backup_job.managed_customer.name,
                entry.backup_job.site.name,
                entry.backup_job.name,
                entry.backup_job.technology.name,
                entry.protected_object.name if entry.protected_object else "",
                entry.get_result_display(),
                entry.manual_observation,
                entry.ticket_reference,
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
