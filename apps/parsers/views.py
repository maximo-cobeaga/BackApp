"""Tenant-scoped parser and manual-review views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.operations.services import (
    backup_execution_candidates_for_parsed_item,
    backup_execution_result_from_parsed_item,
    create_backup_execution_from_parsed_item,
)
from apps.parsers.forms import ParsedItemReviewForm
from apps.parsers.models import ParsedReportItem
from apps.parsers.services import mark_parsed_item_reviewed, parse_unprocessed_messages
from apps.tenancy.services import get_tenant_context, require_admin


@login_required
def review_queue(request):
    context = get_tenant_context(request)
    items = ParsedReportItem.objects.select_related("message", "message__connector").filter(
        organization=context.organization,
        review_status=ParsedReportItem.ReviewStatus.NEEDS_REVIEW,
    )
    return render(request, "parsers/review_queue.html", {"items": items})


@login_required
def parse_unprocessed(request):
    context = require_admin(request)
    if request.method == "POST":
        result = parse_unprocessed_messages(organization=context.organization)
        messages.success(
            request,
            (
                "Procesamiento completo: "
                f"{result.processed_messages} mensajes, "
                f"{result.created_items} resultados nuevos."
            ),
        )
    return redirect("parser_review_queue")


@login_required
def parsed_item_review(request, item_id):
    context = require_admin(request)
    item = get_object_or_404(
        ParsedReportItem,
        id=item_id,
        organization=context.organization,
    )
    initial_result = backup_execution_result_from_parsed_item(item)
    matching_candidates = backup_execution_candidates_for_parsed_item(parsed_item=item)
    if request.method == "POST":
        form = ParsedItemReviewForm(
            request.POST,
            organization=context.organization,
            initial_result=initial_result,
            matching_candidates=matching_candidates,
        )
        if form.is_valid():
            expected_execution = form.cleaned_data["expected_execution"]
            if expected_execution:
                create_backup_execution_from_parsed_item(
                    parsed_item=item,
                    expected_execution=expected_execution,
                    result=form.cleaned_data["result"],
                    user=request.user,
                    operator_note=form.cleaned_data["review_note"],
                )
            else:
                mark_parsed_item_reviewed(
                    item=item,
                    user=request.user,
                    note=form.cleaned_data["review_note"],
                )
            return redirect("parser_review_queue")
    else:
        form = ParsedItemReviewForm(
            organization=context.organization,
            initial_result=initial_result,
            matching_candidates=matching_candidates,
        )
    return render(
        request,
        "parsers/review_form.html",
        {"form": form, "item": item, "matching_candidates": matching_candidates},
    )
