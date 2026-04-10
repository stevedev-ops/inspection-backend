from django.core.management.base import BaseCommand
import pandas as pd
import math
from inspections.models import Business
from users.models import User

class Command(BaseCommand):
    help = 'Seeds local SQLite / PostgreSQL backend with data from excel files'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding superadmin / sample PHO users...")
        
        # Superadmin
        if not User.objects.filter(email='admin@example.com').exists():
            User.objects.create_superuser(
                username='admin@example.com',
                email='admin@example.com',
                password='admin',
                role='super_admin',
                full_name='Super Admin',
                status='active'
            )
            self.stdout.write(self.style.SUCCESS('Created default superadmin (admin@example.com / admin)'))

        # Standard PHO
        if not User.objects.filter(email='pho@example.com').exists():
            User.objects.create_user(
                username='pho@example.com',
                email='pho@example.com',
                password='pho',
                role='pho',
                full_name='Sample Field Inspector',
                status='active'
            )
            self.stdout.write(self.style.SUCCESS('Created default PHO user (pho@example.com / pho)'))


        self.stdout.write("Wiping existing businesses for a fresh seed...")
        Business.objects.all().delete()

        self.stdout.write("Loading SIMPLIFIED DATA.xlsx for businesses...")
        
        file_path = 'data/SIMPLIFIED DATA.xlsx'
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not load excel file: {e}"))
            return

        businesses_created = 0
        
        for index, row in df.iterrows():
            business_name = str(row.get('Business Name', '')).strip()
            if not business_name or business_name.lower() == 'nan':
                continue
                
            permit_no = str(row.get('Permit No.', '')).strip()
            if permit_no.lower() == 'nan':
                permit_no = None

            subcounty_name = str(row.get('Subcounty Name', '')).strip()
            if subcounty_name.lower() == 'nan': subcounty_name = None
            
            ward_name = str(row.get('Ward Name', '')).strip()
            if ward_name.lower() == 'nan': ward_name = None

            building_name = str(row.get('Building Name', '')).strip()
            if building_name.lower() == 'nan': building_name = None
            
            street_name = str(row.get('Street Name', '')).strip()
            if street_name.lower() == 'nan': street_name = None
            
            plot_no = str(row.get('Plot No.', '')).strip()
            if plot_no.lower() == 'nan': plot_no = None

            contact_phone = str(row.get('Contact Person Mobile No', '')).strip()
            if contact_phone.lower() == 'nan': contact_phone = None

            contact_email = str(row.get('Contact Person Email', '')).strip()
            if contact_email.lower() == 'nan': contact_email = None

            Business.objects.create(
                business_name=business_name,
                permit_no=permit_no,
                subcounty_name=subcounty_name,
                ward_name=ward_name,
                building_name=building_name,
                street_name=street_name,
                plot_no=plot_no,
                contact_phone=contact_phone,
                contact_email=contact_email
            )
            businesses_created += 1

            if businesses_created % 500 == 0:
                self.stdout.write(f"Created {businesses_created} businesses...")

        self.stdout.write(self.style.SUCCESS(f"Finished inserting {businesses_created} businesses."))
