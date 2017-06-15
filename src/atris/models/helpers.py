from django.core.exceptions import ObjectDoesNotExist
from django.db import router


def get_diff_fields(model, data, previous_data, excluded_fields_names):
    """
    Returns the fields of `data` for which the values differ in
    `previous_data`. The fields that are given in `excluded_fields_names` are
    not registered as having changed, but are returned in the secod list of the
    result. If there is no previous data, 2 empty lists are returned.
    :param model: - the Django model or an instance of that model.
    """
    diff = []
    excluded = []
    if not previous_data:
        return diff, excluded
    for f, v in data.items():
        if previous_data.get(f) != v:
            if f in excluded_fields_names:
                excluded.append(f)
            else:
                diff.append(model._meta.get_field(f).name)
    return diff, excluded


def get_instance_field_data(instance, removed_data={}):
    """
    Returns a dictionary with the attribute values of instance, serialized as
    strings. `removed_data` is a dictionary of field name to IDs list for the
    objects that are to be removed from the many-to-many fields.
    """
    data = {}
    instance_meta = instance._meta
    for field in instance_meta.get_fields():
        name = field.name
        if name in instance_meta.history_logging.excluded_fields_names:
            continue
        if hasattr(field, 'attname'):  # regular field or foreign key
            attname = field.attname
        elif hasattr(field, 'get_accessor_name'):  # many-to-* relation feild
            attname = field.get_accessor_name()
        elif hasattr(field, 'fk_field'):  # generic foreign key
            attname = field.fk_field
        try:
            value = getattr(instance, attname)
        except ObjectDoesNotExist:
            value = None
        if field.many_to_many or field.one_to_many:
            ids = from_writable_db(value).values_list('pk', flat=True)
            if name in removed_data:
                ids = ([] if removed_data[name] is None
                       else ids.exclude(pk__in=removed_data[name]))
            data[name] = ', '.join([str(e) for e in ids])
        elif field.one_to_one and not field.concrete:
            data[name] = str(value.pk) if value is not None else None
        else:
            data[name] = str(value) if value is not None else None
    return data


def from_writable_db(manager):
    """
    When using a DB router in which the reads are done through a different
    connection than the writes, the data may differ, resulting in incorrect
    history logging. Use the writable DB whenever it is essential to get the
    latest data.
    """
    writable_db = router.db_for_write(manager.model)
    return manager.using(writable_db)
