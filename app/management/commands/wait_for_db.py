import time
import logging
from django.core.management.base import BaseCommand
from django.db import connections, OperationalError

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Django command to pause execution until database is available"""
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Timeout in seconds (default: 60)'
        )
    
    def handle(self, *args, **options):
        timeout = options['timeout']
        start_time = time.time()
        
        self.stdout.write('Waiting for database...')
        
        db_conn = None
        while not db_conn:
            try:
                db_conn = connections['default']
                db_conn.cursor()
            except OperationalError:
                if time.time() - start_time > timeout:
                    self.stderr.write(
                        self.style.ERROR(
                            f'Database unavailable after {timeout} seconds'
                        )
                    )
                    return
                
                self.stdout.write('Database unavailable, waiting 1 second...')
                time.sleep(1)
        
        self.stdout.write(
            self.style.SUCCESS('Database available!')
        )