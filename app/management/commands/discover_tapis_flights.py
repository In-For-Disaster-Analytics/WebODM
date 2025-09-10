from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from app.models.oauth2 import TapisOAuth2Client
from app.services.tapis_storage import TapisFlightDiscoveryService
import logging

logger = logging.getLogger('app.logger')


class Command(BaseCommand):
    help = 'Discover flight directories from Tapis storage systems and create WebODM projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            required=True,
            help='Username of the user to create projects for'
        )
        parser.add_argument(
            '--client-id',
            type=str,
            help='Tapis OAuth2 client ID (optional, uses first active client if not specified)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating projects'
        )
        parser.add_argument(
            '--systems',
            type=str,
            nargs='*',
            help='Specific system IDs to scan (optional, scans all ptdatax.project.* if not specified)'
        )

    def handle(self, *args, **options):
        try:
            # Get user
            try:
                user = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                raise CommandError(f"User '{options['user']}' not found")

            # Get Tapis client
            if options.get('client_id'):
                try:
                    client = TapisOAuth2Client.objects.get(
                        client_id=options['client_id'],
                        is_active=True
                    )
                except TapisOAuth2Client.DoesNotExist:
                    raise CommandError(f"Tapis client '{options['client_id']}' not found or inactive")
            else:
                client = TapisOAuth2Client.objects.filter(is_active=True).first()
                if not client:
                    raise CommandError("No active Tapis OAuth2 client found")

            self.stdout.write(f"Using Tapis client: {client.name} ({client.client_id})")
            self.stdout.write(f"Target user: {user.username}")

            # Check if user has valid token
            from app.models.oauth2 import TapisOAuth2Token
            try:
                token = TapisOAuth2Token.objects.get(user=user, client=client)
                if not token.is_valid:
                    raise CommandError(f"User {user.username} has expired Tapis token. Please re-authenticate.")
            except TapisOAuth2Token.DoesNotExist:
                raise CommandError(f"User {user.username} has no Tapis token. Please authenticate first.")

            self.stdout.write(self.style.SUCCESS("✓ Token validation passed"))

            if options['dry_run']:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No projects will be created"))

            # Perform discovery
            self.stdout.write("Starting flight discovery...")
            
            if not options['dry_run']:
                results = TapisFlightDiscoveryService.discover_and_create_projects(user, client)
            else:
                # For dry run, just discover without creating
                from app.services.tapis_storage import TapisStorageService
                storage_service = TapisStorageService(user, client)
                
                systems = storage_service.discover_project_systems()
                all_flights = []
                
                for system in systems:
                    system_id = system.get('id')
                    if system_id:
                        if options.get('systems') and system_id not in options['systems']:
                            continue
                        flights = storage_service.scan_system_for_flights(system_id)
                        all_flights.extend(flights)
                
                results = {
                    'systems_scanned': len(systems),
                    'flights_discovered': len(all_flights),
                    'projects_created': 0,  # Dry run
                    'errors': [],
                    'created_projects': []
                }
                
                # Show what would be created
                self.stdout.write(f"\nFlights that would create projects:")
                for flight in all_flights:
                    self.stdout.write(f"  - {flight['flight_name']} in {flight['system_id']} ({flight['image_count']} images)")

            # Display results
            self.stdout.write("\n" + "="*60)
            self.stdout.write("DISCOVERY RESULTS")
            self.stdout.write("="*60)
            
            self.stdout.write(f"Systems scanned: {results['systems_scanned']}")
            self.stdout.write(f"Flights discovered: {results['flights_discovered']}")
            self.stdout.write(f"Projects created: {results['projects_created']}")
            
            if results['errors']:
                self.stdout.write(self.style.ERROR(f"Errors encountered: {len(results['errors'])}"))
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
            
            if results['created_projects']:
                self.stdout.write(self.style.SUCCESS("\nCreated projects:"))
                for project in results['created_projects']:
                    self.stdout.write(self.style.SUCCESS(
                        f"  - Project {project['project_id']}: {project['project_name']} "
                        f"({project['image_count']} images from {project['flight_name']})"
                    ))
            
            if results['projects_created'] > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"\n✓ Successfully created {results['projects_created']} projects!"
                ))
            elif results['flights_discovered'] > 0 and not options['dry_run']:
                self.stdout.write(self.style.WARNING(
                    "⚠ Flights were discovered but no projects were created. Check for existing projects or errors above."
                ))
            elif results['flights_discovered'] == 0:
                self.stdout.write(self.style.WARNING(
                    "⚠ No flight directories found matching the required pattern: <Flight>/code/images/*.jpg"
                ))

        except Exception as e:
            logger.error(f"Flight discovery command failed: {e}")
            raise CommandError(f"Command failed: {e}")