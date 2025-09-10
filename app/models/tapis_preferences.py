from django.db import models
from django.contrib.auth.models import User


class TapisUserPreferences(models.Model):
    """
    User preferences for Tapis integration behavior
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tapis_preferences')
    
    # Flight discovery preferences
    auto_discover_on_login = models.BooleanField(
        default=True, 
        help_text="Automatically discover and create projects from flight data on Tapis login"
    )
    
    # Discovery behavior settings
    max_projects_per_discovery = models.IntegerField(
        default=50,
        help_text="Maximum number of projects to create in a single discovery session"
    )
    
    discovery_cooldown_hours = models.IntegerField(
        default=24,
        help_text="Hours to wait between automatic discovery runs for the same user"
    )
    
    # Notification preferences
    notify_on_discovery_complete = models.BooleanField(
        default=True,
        help_text="Send notification when flight discovery creates new projects"
    )
    
    notify_on_discovery_errors = models.BooleanField(
        default=True,
        help_text="Send notification when flight discovery encounters errors"
    )
    
    # System preferences
    preferred_systems = models.TextField(
        blank=True,
        help_text="Comma-separated list of preferred ptdatax.project.* systems to scan (empty = all systems)"
    )
    
    # Timestamps
    last_auto_discovery = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp of last automatic discovery run"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tapis User Preferences"
        verbose_name_plural = "Tapis User Preferences"
    
    def __str__(self):
        return f"Tapis preferences for {self.user.username}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create preferences for a user with defaults"""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'auto_discover_on_login': True,
                'max_projects_per_discovery': 50,
                'discovery_cooldown_hours': 24,
                'notify_on_discovery_complete': True,
                'notify_on_discovery_errors': True
            }
        )
        return preferences
    
    def should_run_auto_discovery(self):
        """Check if auto discovery should run based on preferences and cooldown"""
        if not self.auto_discover_on_login:
            return False
            
        # Check cooldown period
        if self.last_auto_discovery:
            from django.utils import timezone
            from datetime import timedelta
            
            cooldown_delta = timedelta(hours=self.discovery_cooldown_hours)
            if timezone.now() - self.last_auto_discovery < cooldown_delta:
                return False
                
        return True
    
    def get_preferred_systems_list(self):
        """Get list of preferred systems, or empty list if none specified"""
        if not self.preferred_systems.strip():
            return []
        return [s.strip() for s in self.preferred_systems.split(',') if s.strip()]
    
    def update_last_discovery(self):
        """Update the last discovery timestamp"""
        from django.utils import timezone
        self.last_auto_discovery = timezone.now()
        self.save(update_fields=['last_auto_discovery'])