from django.core.management.base import BaseCommand

from xbrowse_server.base.models import Project
from xbrowse.parsers import fam_stuff
from collections import defaultdict

from optparse import make_option
import re
import os

def fix_id(id_string):
    """Return a standardized individual id: remove repetative _ and - and replace all _ with -"""
    i_id = id_string
    i_id = re.sub("_+", "_", i_id)
    i_id = re.sub("-+", "-", i_id)
    i_id = i_id.replace("_", "-")
    i_id = i_id.replace("Sample-", "")
    return i_id

class Command(BaseCommand):
    """Command to generate PED file(s) for the given project(s). Takes 1 or more project_ids."""
    option_list = BaseCommand.option_list + (
        make_option('--merge', action="store_true", help="Merge the PED info from all projects into one PED file, "
                                                         "while properly handling fields that are missing or conflict"
                                                         "between projects."),
    )

    def handle(self, *args, **options):
        if not options.get('merge'):
            for project_name in args:
                project = Project.objects.get(project_id=project_name)
                individuals = project.get_individuals()
                filename = project.project_id + ".ped"
                print("Writing %s individuals to %s" % (len(individuals), filename))

                with open(filename, "w") as f:
                    fam_stuff.write_individuals_to_ped_file(f, individuals)
        else:
            # Merge PED information from all projects into 1 PED file.
            print("Merging: " + str(args))

            all_individuals = []


            individual_family_id = defaultdict(list)  # maps inidiv id to their family name. This is a list of family_ids because an individual may have different family ids in different projects.
            individual_paternal_id = {}
            individual_maternal_id = {}
            individual_gender = {}
            individual_affected = {}
            individual_projects = defaultdict(list)  # maps indiv id to project names where this individual appears
            individual_vcfs = defaultdict(list)   # maps indiv id to all vcfs containing this individ

            for project_name in args:
                project = Project.objects.get(project_id=project_name)
                for i in project.get_individuals():
                    i_id = fix_id(i.indiv_id)

                    if i_id.startswith("NA128"):
                        print("SKIPPING: 1kg sample " + i_id)
                        continue

                    if i_id not in all_individuals:
                        all_individuals.append(i_id)

                    individual_projects[i_id].append(project_name)
                    individual_vcfs[i_id].extend([os.path.basename(vcf.file_path) for vcf in i.get_vcf_files()])

                    if i.family:
                        family_id = i.family.family_id.replace("Sample-", "")
                        individual_family_id[i_id].append(family_id)

                    paternal_id = fix_id(i.paternal_id or ".")
                    if paternal_id not in [".", "U"]:
                        if i_id in individual_paternal_id and individual_paternal_id[i_id] != paternal_id:
                            #prev_paternal_id = individual_paternal_id[i_id]
                            #print("ERROR: %(project_name)s : %(i_id)s has paternal ids: %(prev_paternal_id)s and %(paternal_id)s" % locals())
                            individual_paternal_id[i_id] = "conflict"
                        else:
                            individual_paternal_id[i_id] = paternal_id

                    maternal_id = fix_id(i.maternal_id or ".")
                    if maternal_id not in [".", "U"]:
                        if i_id in individual_maternal_id and individual_maternal_id[i_id] != maternal_id:
                            #prev_maternal_id = individual_maternal_id[i_id]
                            #print("ERROR: %(project_name)s : %(i_id)s has maternal ids: %(prev_maternal_id)s and %(maternal_id)s" % locals())
                            individual_maternal_id[i_id] = "conflict"
                        else:
                            individual_maternal_id[i_id] = maternal_id

                    gender = i.gender
                    if gender not in [".", "U"]:
                        if i_id in individual_gender and individual_gender[i_id] != gender:
                            #prev_gender = individual_gender[i_id]
                            #print("ERROR: %(project_name)s : %(i_id)s has gender ids: %(prev_gender)s and %(gender)s" % locals())
                            individual_gender[i_id] = "conflict"
                        else:
                            individual_gender[i_id] = gender

                    affected = i.affected
                    if affected not in [".", "U"]:
                        if i_id in individual_affected and individual_affected[i_id] != affected:
                            #prev_affected = individual_affected[i_id]
                            #print("ERROR: %(project_name)s : %(i_id)s has affected ids: %(prev_affected)s and %(affected)s" % locals())
                            individual_affected[i_id] = "conflict"
                        else:
                            individual_affected[i_id] = affected

            # replace list of family ids with a string to use as the family id in the merged PED file
            for i_id in individual_family_id:
                family_id = "__".join(list(set(individual_family_id.get(i_id, []))))
                individual_family_id[i_id] = family_id

            # write out the merged ped file
            filename = "all_%s_projects.ped" % len(args)
            print("Writing %s individuals to %s" % (len(all_individuals), filename))

            f = open(filename, "w")
            header = ["family", "individual", "paternal_id", "maternal_id", "gender", "affected"]
            f.write("# %s\n" % "\t".join(header))
            print("\t".join(["family", "individual", "paternal_id", "maternal_id", "gender", "affected"]))
            for i_id in sorted(all_individuals, key=lambda x: individual_family_id[x]):
                family_id = individual_family_id[i_id]
                maternal_id = individual_maternal_id.get(i_id, None)
                paternal_id = individual_paternal_id.get(i_id, None)
                gender = individual_gender.get(i_id, None) or "unknown"  # if None or empty string, set it to unknown
                affected = individual_affected.get(i_id, None) or "unknown"

                fields = [family_id, i_id, paternal_id or ".", maternal_id or ".", gender, affected]

                print("\t".join(fields + [", ".join(individual_projects[i_id])] + [", ".join(individual_vcfs[i_id])]))
                f.write("\t".join(fields) + "\n")
            f.close()

            print("\nFinished")