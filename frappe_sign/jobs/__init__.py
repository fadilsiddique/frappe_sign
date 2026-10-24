"""Background job entry points. Transaction boundaries only: call a service, then commit.

Every enqueued function lives here; services are never enqueued directly."""
