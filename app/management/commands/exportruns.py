import csv
import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from app.models import TaskRun

JSON_COLUMNS = ('options', 'parent_options', 'stage_seconds')


class Command(BaseCommand):
    help = "Export task run records as CSV to stdout"

    def add_arguments(self, parser):
        parser.add_argument("--since", type=str, required=False, help="Only runs finished on or after this date (YYYY-MM-DD)")
        parser.add_argument("--status", type=str, required=False, help="Only runs with this status (e.g. COMPLETED)")
        super(Command, self).add_arguments(parser)

    def handle(self, **options):
        runs = TaskRun.objects.order_by('finished_at', 'id')

        if options.get('since'):
            try:
                since = datetime.strptime(options['since'], "%Y-%m-%d")
            except ValueError:
                raise CommandError("Invalid --since date: {} (expected YYYY-MM-DD)".format(options['since']))
            runs = runs.filter(finished_at__gte=timezone.make_aware(since))

        if options.get('status'):
            name = options['status'].upper()
            codes = {label: code for code, label in TaskRun.STATUS_CHOICES}
            if name not in codes:
                raise CommandError("Invalid status: {} (choose from {})".format(options['status'], ", ".join(codes)))
            runs = runs.filter(status=codes[name])

        columns = [f.attname for f in TaskRun._meta.concrete_fields]
        writer = csv.writer(self.stdout)
        writer.writerow(columns)
        for run in runs.iterator():
            row = []
            for c in columns:
                v = getattr(run, c)
                if c in JSON_COLUMNS:
                    v = json.dumps(v)
                elif c == 'status':
                    v = run.get_status_display()
                elif v is None:
                    v = ""
                elif hasattr(v, 'isoformat'):
                    v = v.isoformat()
                row.append(v)
            writer.writerow(row)
