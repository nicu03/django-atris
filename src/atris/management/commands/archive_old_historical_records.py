import logging
from datetime import timedelta
from optparse import make_option

from django.core.management import BaseCommand
from django.db import transaction, connection
from django.utils.timezone import now

from atris.models import HistoricalRecord

logger = logging.getLogger('old_history_archiving')


class Command(BaseCommand):
    help = (
        """
        Archives historical records older than the specified days or months.
        You must supply either the days or the weeks param.
        The historical entries older than the specified days will be moved to
        the "atris_archivedhistoricalrecord" table.
        """
    )
    PARAM_ERROR = 'You must supply either the days or the weeks param'

    option_list = BaseCommand.option_list + (
        make_option('--days',
                    dest='days',
                    type='int',
                    default=None,
                    help=('Any historical record older than the number of days'
                          ' specified gets archived.')),
        make_option('--weeks',
                    dest='weeks',
                    type='int',
                    default=None,
                    help=('Any historical record older than the number of'
                          ' months specified gets archived.')),
    )

    def handle(self, *args, **options):
        days = options.get('days')
        weeks = options.get('weeks')
        if not (days or weeks):
            self.stderr.write("{msg}\n".format(
                msg=self.PARAM_ERROR,
            ))
            return
        old_history_entries = HistoricalRecord.objects.older_than(days, weeks)
        handled_entries_nr = old_history_entries.count()
        self.migrate_data(days, weeks)
        self.stdout.write('{} archived.\n'.format(handled_entries_nr))

    @transaction.atomic
    def migrate_data(self, days=None, weeks=None):
        if days and weeks:
            logger.info('You supplied both days and weeks, weeks param'
                        ' will be used as the delimiter.')
        td = timedelta(weeks=weeks) if weeks else timedelta(days=days)
        older_than_date = now() - td
        cursor = connection.cursor()
        fields_str = ','.join(
            [field.attname for field in HistoricalRecord._meta.fields]
        )
        query = ("INSERT INTO atris_archivedhistoricalrecord ({}) "
                 "SELECT {} FROM atris_historicalrecord "
                 "WHERE history_date < '{}';".format(fields_str, fields_str,
                                                     older_than_date.date()))
        cursor.execute(query)
        query = ("DELETE FROM atris_historicalrecord "
                 "WHERE history_date < '{}';".format(older_than_date.date()))
        cursor.execute(query)
