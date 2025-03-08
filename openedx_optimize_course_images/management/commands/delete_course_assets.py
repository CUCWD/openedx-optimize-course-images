import argparse

from django.core.management.base import BaseCommand, CommandError

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import AssetKey, CourseKey
from cms.djangoapps.contentstore.views import assets as asset_views
from cms.djangoapps.contentstore.exceptions import AssetNotFoundException
from xmodule.contentstore.utils import empty_asset_trashcan
from xmodule.modulestore.django import modulestore


def _delete_assets(course_key, asset_key_strings):
    """
    Delete assets from the MongoDB contentstore and put them in the trashcan.
    """
    # Traverse the list of asset key strings and delete each asset
    for asset_key_string in asset_key_strings:
        asset_key = AssetKey.from_string(asset_key_string) if asset_key_string else None

        try:
            asset_views.delete_asset(course_key, asset_key)
            print(f'Asset deleted successfully: {asset_key_string}')
        except AssetNotFoundException:
            print(f'Asset not found: {asset_key_string}')

    # Empty the trashcan for the course to remove the unused images permanently.
    # This is a separate step to ensure that the course assets are permanently deleted from the platform.
    # When the assets are deleted from the contentstore, they are moved to the trashcan.
    # The trashcan must be emptied to permanently delete the assets.
    print(f"Emptying trashcan for course: {course_key}")
    empty_asset_trashcan([course_key])

class Command(BaseCommand):
    """
    Deletes course assets from an Open edX course.
    """
    help = "Deletes course assets from an Open edX course."

    def add_arguments(self, parser):
        parser = argparse.ArgumentParser(description='Delete course assets from an Open edX course.')
        parser.add_argument('course_id', type=str, help='The course ID of the Open edX course.')
        parser.add_argument('asset_key_strings', nargs='+', help='List of asset key strings to be deleted.')

    def handle(self, *args, **options):
        try:
            course_key = CourseKey.from_string(options['course_id'])
            asset_key_strings = options['asset_key_strings']
        except InvalidKeyError:
            raise CommandError("Invalid course_key: '%s'." % options['course_id'])  # lint-amnesty, pylint: disable=raise-missing-from

        if not modulestore().get_course(course_key):
            raise CommandError("Course with %s key not found." % options['course_id'])
        
        # Delete assets from the MongoDB contentstore and put them in the trashcan.
        _delete_assets(course_key, asset_key_strings)
