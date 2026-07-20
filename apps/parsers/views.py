"""Tenant-scoped parser and manual-review views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
    if request.method == "POST":
        form = ParsedItemReviewForm(request.POST)
        if form.is_valid():
            mark_parsed_item_reviewed(
                item=item,
                user=request.user,
                note=form.cleaned_data["review_note"],
            )
            return redirect("parser_review_queue")
    else:
        form = ParsedItemReviewForm()
    return render(request, "parsers/review_form.html", {"form": form, "item": item})
