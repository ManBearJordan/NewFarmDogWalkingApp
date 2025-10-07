"""
Admin views for managing timetable blocks and capacity.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta
from .models import TimetableBlock, BlockCapacity


@staff_member_required
def capacity_edit(request):
    """
    Simple timetable editor for a given date. Add/edit blocks and per-service capacities.
    """
    date_str = request.GET.get("date")
    if date_str:
        date = datetime.fromisoformat(date_str).date()
    else:
        date = timezone.localdate()

    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "copy_yesterday":
            y = date - timedelta(days=1)
            # clear existing
            TimetableBlock.objects.filter(date=date).delete()
            # copy
            for blk in TimetableBlock.objects.filter(date=y):
                new_blk = TimetableBlock.objects.create(
                    date=date,
                    start_time=blk.start_time,
                    end_time=blk.end_time,
                    label=blk.label
                )
                for bc in blk.capacities.all():
                    BlockCapacity.objects.create(
                        block=new_blk,
                        service_code=bc.service_code,
                        capacity=bc.capacity,
                        allow_overlap=bc.allow_overlap
                    )
            return redirect(f"{request.path}?date={date.isoformat()}")

        if action == "add_block":
            start = request.POST.get("start_time")  # "HH:MM"
            end = request.POST.get("end_time")
            label = request.POST.get("label") or ""
            TimetableBlock.objects.create(date=date, start_time=start, end_time=end, label=label)
            return redirect(f"{request.path}?date={date.isoformat()}")

        if action == "set_capacity":
            block_id = request.POST.get("block_id")
            service_code = request.POST.get("service_code")
            cap = int(request.POST.get("capacity") or 0)
            allow_overlap = bool(request.POST.get("allow_overlap"))
            blk = get_object_or_404(TimetableBlock, id=block_id, date=date)
            obj, _ = BlockCapacity.objects.get_or_create(block=blk, service_code=service_code)
            obj.capacity = cap
            obj.allow_overlap = allow_overlap
            obj.save()
            return redirect(f"{request.path}?date={date.isoformat()}")

    blocks = TimetableBlock.objects.filter(date=date).order_by("start_time").prefetch_related("capacities")
    return render(request, "core/admin_capacity_edit.html", {"date": date, "blocks": blocks})
