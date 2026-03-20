
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from datetime import datetime, timedelta
from types import SimpleNamespace

from trytond.modules.audit_trail import log as audit_trail_log
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class AuditTrailTestCase(ModuleTestCase):
    'Test AuditTrail module'
    module = 'audit_trail'

    @with_transaction()
    def test_session_events(self):
        pool = Pool()
        User = pool.get('res.user')
        Session = pool.get('ir.session')
        Event = pool.get('ir.session.event')
        user, = User.create([{
                    'name': 'Test User',
                    'login': 'test',
                    'password': 'NaN-123456',
                    }])
        user_id = user.id
        with Transaction().set_user(user_id):
            session, = Session.create([{}])
            key = session.key
            event, = Event.search([('key', '=', key)])
            self.assertEqual(event.key, key)
            self.assertEqual(event.user, user)
            self.assertIsNotNone(event.login)
            self.assertEqual(event.login, event.create_date)
            self.assertIsNone(event.logout)
            Session.delete([session])
            event, = Event.search([('key', '=', key)])
            self.assertEqual(event.login, event.create_date)
            self.assertIsNotNone(event.logout)
            self.assertEqual(event.logout, event.write_date)

    @with_transaction()
    def test_request_contains_field_helper(self):
        request_data = {'params': [[1], ['name', 'login']]}

        self.assertTrue(audit_trail_log._request_contains_field(
                request_data, 'login'))
        self.assertFalse(audit_trail_log._request_contains_field(
                request_data, 'email'))

    @with_transaction()
    def test_get_over_limit_by_user(self):
        pool = Pool()
        Log = pool.get('audit_trail.log')
        Model = pool.get('ir.model')
        User = pool.get('res.user')

        model, = Model.search([('name', '=', 'res.user')], limit=1)
        user1, user2 = User.create([{
                    'name': 'User One',
                    'login': 'user_one',
                    'password': 'NaN-123456',
                    }, {
                    'name': 'User Two',
                    'login': 'user_two',
                    'password': 'NaN-123456',
                    }])
        logs = Log.create([{
                    'user': user1.id,
                    'type': 'model',
                    'operation': 'read',
                    'record_ids': '[0]',
                    'request': '{}',
                    'model': model.id,
                    }, {
                    'user': user1.id,
                    'type': 'model',
                    'operation': 'read',
                    'record_ids': '[1]',
                    'request': '{}',
                    'model': model.id,
                    }, {
                    'user': user1.id,
                    'type': 'model',
                    'operation': 'read',
                    'record_ids': '[2]',
                    'request': '{}',
                    'model': model.id,
                    }, {
                    'user': user2.id,
                    'type': 'model',
                    'operation': 'read',
                    'record_ids': '[3]',
                    'request': '{}',
                    'model': model.id,
                    }, {
                    'user': user1.id,
                    'type': 'model',
                    'operation': 'write',
                    'record_ids': '[4]',
                    'request': '{}',
                    'model': model.id,
                    }])
        cursor = Transaction().connection.cursor()
        table = Log.__table__()
        cursor.execute(*table.update(
                columns=[table.create_date],
                values=[datetime.now() - timedelta(days=2)],
                where=table.id == logs[0].id))

        configuration = SimpleNamespace(models=[SimpleNamespace(
                    number=1,
                    model=model,
                    operation='read',
                    )])
        over_limit = Log.get_over_limit_by_user(configuration)

        self.assertEqual(len(over_limit), 1)
        user, config_model, count = over_limit[0]
        self.assertEqual(user, user1)
        self.assertEqual(config_model.model, model)
        self.assertEqual(count, 2)


del ModuleTestCase
