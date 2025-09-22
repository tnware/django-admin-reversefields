"""
Business domain models for testing django-admin-reversefields package.
"""

from django.db import models


class Company(models.Model):
    """
    Root entity representing a business organization.

    This model serves as the parent for departments and projects,
    demonstrating one-to-many reverse relationships
    """

    name = models.CharField(max_length=100)
    founded_year = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "companies"

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return str(self.name)


class Department(models.Model):
    """
    Organizational unit within a company.

    Demonstrates a non-nullable foreign key relationship to Company
    """

    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="departments", null=True, blank=True
    )
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return f"{self.name} ({self.company.name if self.company else 'Unassigned'})"


class Employee(models.Model):
    """
    Individual worker within a department.

    Demonstrates a nullable foreign key relationship to Department
    """

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )
    hire_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        dept_name = self.department.name if self.department else "Unassigned"
        return f"{self.name} ({dept_name})"


class Project(models.Model):
    """
    Work initiative within a company.

    Demonstrates another non-nullable relationship to Company,
    and serves as the target for many-to-many relationships
    through Assignment model.
    """

    name = models.CharField(max_length=100)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="projects", null=True, blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return f"{self.name} ({self.company.name if self.company else 'Unassigned'})"


class Assignment(models.Model):
    """
    Junction model connecting employees to projects with additional data.

    Demonstrates a many-to-many relationship with additional fields
    """

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="assignments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assignments")
    role = models.CharField(max_length=50)
    hours_allocated = models.IntegerField(default=40)
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("employee", "project")

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return f"{self.employee.name} - {self.project.name} ({self.role})"


class CompanySettings(models.Model):
    """
    One-to-one relationship model for company configuration.

    Demonstrates a unique/one-to-one reverse relationship
    Uses nullable relationship to allow companies without settings.
    """

    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, related_name="settings", null=True, blank=True
    )
    timezone = models.CharField(max_length=50, default="UTC")
    fiscal_year_start = models.IntegerField(default=1)  # Month number
    allow_remote_work = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "company settings"

    def __str__(self) -> str:  # pragma: no cover - repr helper for admin/tests
        return f"Settings for {self.company.name}"
