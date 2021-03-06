from optparse import make_option

from django.core.management.base import BaseCommand
from xbrowse_server import xbrowse_controls

from xbrowse_server.base.models import Project
from optparse import make_option

from django.core.management.base import BaseCommand
from xbrowse_server import xbrowse_controls

from xbrowse_server.base.models import Project
from xbrowse_server.mall import get_datastore


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-p', "--project-id"),
    )

    def handle(self, *args, **options):

        project_id = options["project_id"]
        family_ids = args
        project = Project.objects.get(project_id=project_id)

        for vcf_file, families in project.families_by_vcf().items():
            families_to_load = []
            for family in families:
                family_id = family.family_id
                print("Checking id: " + family_id)
                if not family_ids or family.family_id not in family_ids:
                    continue

                # delete this family
                get_datastore(project_id).delete_family(project_id, family_id)

                families_to_load.append(family)
                # reload family

            print("Loading %(project_id)s %(families_to_load)s" % locals())
            xbrowse_controls.load_variants_for_family_list(project, families_to_load, vcf_file)



