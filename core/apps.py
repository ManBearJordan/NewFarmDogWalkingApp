import logging
from django.apps import AppConfig
from django.conf import settings


logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """
        Called when Django is ready and all models are loaded.
        This is where we implement the automatic Stripe sync on app startup.
        """
        # Only run sync in production/development, not during migrations or tests
        import sys
        
        # Skip sync during migrations, tests, or certain management commands
        skip_commands = [
            'migrate', 'makemigrations', 'test', 'collectstatic',
            'shell', 'showmigrations', 'sqlmigrate', 'check'
        ]
        
        if any(cmd in sys.argv for cmd in skip_commands):
            logger.info("Skipping Stripe sync during management command")
            return
        
        # Skip during testing
        if 'test' in sys.argv or getattr(settings, 'TESTING', False):
            logger.info("Skipping Stripe sync during testing")
            return
            
        try:
            # Import here to avoid circular imports and ensure Django is fully loaded
            from core.services.stripe_sync import sync_stripe_data_on_startup
            
            logger.info("Django app ready - starting automatic Stripe sync")
            
            # Run sync in background to avoid blocking startup
            import threading
            
            def run_sync():
                try:
                    result = sync_stripe_data_on_startup(horizon_days=90)
                    if result.get('success'):
                        logger.info(f"Startup Stripe sync completed successfully: {result['stats']}")
                    else:
                        logger.error(f"Startup Stripe sync failed: {result.get('error')}")
                except Exception as e:
                    logger.error(f"Startup Stripe sync encountered an error: {e}", exc_info=True)
            
            # Start sync thread with a small delay to ensure Django is fully ready
            sync_thread = threading.Timer(2.0, run_sync)
            sync_thread.daemon = True  # Don't prevent app shutdown
            sync_thread.start()
            
            logger.info("Automatic Stripe sync scheduled to run in 2 seconds")
            
        except ImportError as e:
            logger.warning(f"Could not import Stripe sync service: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize automatic Stripe sync: {e}", exc_info=True)
