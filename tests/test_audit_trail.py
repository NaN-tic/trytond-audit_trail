# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class TestCase(unittest.TestCase):
    'Test module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('audit_trail')
        self.user = POOL.get('res.user')
        self.session = POOL.get('ir.session')
        self.event = POOL.get('ir.session.event')

    def test0005views(self):
        'Test views'
        test_view('audit_trail')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test_session_events(self):
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            user, = self.user.create([{
                        'name': 'Test User',
                        'login': 'test',
                        'password': '123456',
                        }])
            user_id = user.id
            with transaction.set_user(user_id):
                session, = self.session.create([{}])
                key = session.key
                event, = self.event.search([('key', '=', key)])
                self.assertEqual(event.key, key)
                self.assertEqual(event.user, user)
                self.assertIsNotNone(event.login)
                self.assertEqual(event.login, event.create_date)
                self.assertIsNone(event.logout)
                self.session.delete([session])
                event, = self.event.search([('key', '=', key)])
                self.assertEqual(event.login, event.create_date)
                self.assertIsNotNone(event.logout)
                self.assertEqual(event.logout, event.write_date)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
