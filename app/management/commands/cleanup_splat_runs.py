from django.core.management.base import BaseCommand

from app.services import opensplat


class Command(BaseCommand):
    help = 'Remove snapshots and results of finished LS6 splat training runs'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Only runs finished more than this many days ago (default: 30)')
        parser.add_argument('--dry-run', action='store_true', help='List what would be removed without deleting')
        super(Command, self).add_arguments(parser)

    def handle(self, **options):
        if options['days'] < 0:
            self.stderr.write('--days must not be negative')
            return

        dry_run = options['dry_run']
        removed = opensplat.cleanup_runs(options['days'], dry_run=dry_run)
        for path in removed:
            self.stdout.write('{} {}'.format('Would remove' if dry_run else 'Removed', path))
        self.stdout.write('{} {} directories'.format('Found' if dry_run else 'Removed', len(removed)))
