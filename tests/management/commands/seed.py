from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from tests.models import Company, CompanySettings, Department, Employee, Project


class Command(BaseCommand):
    help = "Seed the database with sample data for interactive testing."

    def handle(self, *args, **options):
        if Company.objects.exists():
            self.stdout.write(self.style.WARNING("Data already exists — skipping seed."))
            return

        # Companies
        acme = Company.objects.create(name="Acme Corp", founded_year=2010)
        globex = Company.objects.create(name="Globex Inc", founded_year=2015)
        Company.objects.create(name="Initech", founded_year=2020)

        # Departments — mix of bound and unbound
        Department.objects.create(name="Engineering", company=acme)
        Department.objects.create(name="Marketing")
        Department.objects.create(name="Sales")
        dept_hr = Department.objects.create(name="HR", company=globex)
        Department.objects.create(name="Finance")

        # Projects — mix of bound and unbound
        Project.objects.create(name="Project Alpha", company=acme)
        Project.objects.create(name="Project Beta")
        Project.objects.create(name="Project Gamma")
        Project.objects.create(name="Project Delta", company=globex)
        Project.objects.create(name="Project Epsilon")

        # Employees — mix of assigned and unassigned
        Employee.objects.create(name="Alice", email="alice@test.com", department=dept_hr)
        Employee.objects.create(name="Bob", email="bob@test.com")
        Employee.objects.create(name="Charlie", email="charlie@test.com")

        # CompanySettings — one bound, one unbound
        CompanySettings.objects.create(company=acme, timezone="US/Eastern", allow_remote_work=True)
        CompanySettings.objects.create(timezone="Europe/London", fiscal_year_start=4)

        # Superuser
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@test.com", "admin")
            self.stdout.write("  Superuser created: admin / admin")

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: {Company.objects.count()} companies, "
                f"{Department.objects.count()} departments, "
                f"{Project.objects.count()} projects, "
                f"{Employee.objects.count()} employees, "
                f"{CompanySettings.objects.count()} company settings"
            )
        )
