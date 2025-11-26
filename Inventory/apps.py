from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """
    Configuration for the Inventory application.
    """
    # Sets the primary key field type for models to BigAutoField (recommended for new projects)
    default_auto_field = 'django.db.models.BigAutoField'
    
    # The name Django uses internally to reference the application
    name = 'Inventory'
    
    # A human-readable name used in the Django Admin and other interfaces
    verbose_name = 'POS Inventory Management'
