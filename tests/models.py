from django.db import models


class Service(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return self.name


class Site(models.Model):
    name = models.CharField(max_length=50)
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True, related_name="sites"
    )

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return self.name


class Extension(models.Model):
    number = models.CharField(max_length=10)
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extensions",
    )

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return self.number


class UniqueExtension(models.Model):
    number = models.CharField(max_length=10)
    # Enforce at most one UniqueExtension per Service to simulate unique FK/O2O
    service = models.OneToOneField(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unique_extension",
    )

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return self.number
