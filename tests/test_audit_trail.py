# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


class AuditTrailTestCase(ModuleTestCase):
    'Test Audit Trail module'
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(AuditTrailTestCase))
    return suite
