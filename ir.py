# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, ModelView, Model, fields
from trytond.transaction import Transaction

__all__ = ['Session', 'SessionEvent']


class Session(metaclass=PoolMeta):
    __name__ = 'ir.session'

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Event = pool.get('ir.session.event')

        records = super(Session, cls).create(vlist)

        to_create = []
        for record in records:
            to_create.append({'key': record.key})
        if to_create:
            with Transaction().set_context(_check_access=False):
                Event.create(to_create)
        return records

    @classmethod
    def delete(cls, sessions):
        pool = Pool()
        Event = pool.get('ir.session.event')

        keys = []
        for session in sessions:
            keys.append(session.key)
        events = Event.search([('key', 'in', keys), ('write_date', '=', None)])
        with Transaction().set_context(_check_access=False):
            Event.write(events, {})
        super(Session, cls).delete(sessions)


class SessionEvent(ModelSQL, ModelView):
    'Session Event'
    __name__ = 'ir.session.event'
    user = fields.Function(fields.Many2One('res.user', 'User'),
        'get_audit_field', searcher='search_audit_field')
    login = fields.Function(fields.DateTime('Login Date'),
        'get_audit_field', searcher='search_audit_field')
    logout = fields.Function(fields.DateTime('Logout Date'),
        'get_audit_field', searcher='search_audit_field')
    key = fields.Char('Session Key', required=True, select=True)
    _field_mapping = {
            'login': 'create_date',
            'logout': 'write_date',
            'user': 'create_uid',
            }

    @classmethod
    def get_audit_field(cls, events, names):
        result = {}
        event_ids = [e.id for e in events]
        for name in names:
            result[name] = {}.fromkeys(event_ids, None)
        for event in events:
            for name in names:
                value = getattr(event, cls._field_mapping[name])
                if isinstance(value, Model):
                    value = value.id
                result[name][event.id] = value
        return result

    @classmethod
    def search_audit_field(cls, name, clause):
        return [(cls._field_mapping.get(name),) + tuple(clause[1:])]
