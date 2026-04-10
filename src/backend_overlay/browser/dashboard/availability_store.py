from backend_overlay.browser.dashboard.repository import (
    DASHBOARD_AVAILABILITY_SCHEMA_VERSION,
    DashboardAvailabilityCoverage,
    DashboardAvailabilityRepository,
)


AVAILABILITY_STORE_SCHEMA_VERSION = DASHBOARD_AVAILABILITY_SCHEMA_VERSION
DashboardAvailabilityStore = DashboardAvailabilityRepository
