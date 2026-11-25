from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone


@login_required
def dashboard_view(request):
    now = timezone.now()
    has_domain = apps.is_installed("domain_kit")
    has_cal = apps.is_installed("cal_kit")
    has_list = apps.is_installed("list_kit")
    has_site = apps.is_installed("site_kit")
    has_seed = apps.is_installed("seed_kit")
    ctx = {
        "has_domain": has_domain,
        "has_cal": has_cal,
        "has_list": has_list,
        "has_site": has_site,
        "has_seed": has_seed,
        "persons_count": 0,
        "upcoming_events_count": 0,
        "offerings_count": 0,
        "open_inbox_count": 0,
        "published_pages_count": 0,
        "upcoming_events": [],
        "recent_inbox": [],
    }

    if has_domain:
        from domain_kit.models import Person

        ctx["persons_count"] = Person.objects.count()

    if has_cal:
        from cal_kit.models import CalendarEvent, OfferingTemplate

        upcoming_qs = CalendarEvent.objects.select_related("category").filter(start_at__gte=now).order_by("start_at")
        ctx["upcoming_events_count"] = upcoming_qs.count()
        ctx["upcoming_events"] = list(upcoming_qs[:5])
        ctx["offerings_count"] = OfferingTemplate.objects.count()

    if has_list:
        from list_kit.models import Entry

        inbox_qs = (
            Entry.objects.select_related("collection")
            .filter(collection__template__content_type="form_inbox")
            .order_by("-created_at")
        )
        ctx["open_inbox_count"] = inbox_qs.filter(status="open").count()
        ctx["recent_inbox"] = list(inbox_qs[:5])

    if has_site:
        from site_kit.models import PublicPage

        ctx["published_pages_count"] = PublicPage.objects.filter(is_published=True).count()

    return render(request, "dashboard.html", ctx)
