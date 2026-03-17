from email.header import Header
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from collections import defaultdict
from datetime import datetime, timedelta

from trytond.model import ModelSQL, ModelView, fields, ModelSingleton
from trytond.pool import Pool, PoolMeta
import trytond.protocols.dispatcher
from trytond.transaction import Transaction
from trytond.config import config
from trytond.cache import Cache
from trytond.sendmail import sendmail
from trytond.i18n import gettext


OPERATIONS = [
    (None, ''),
    ('read', 'Read'),
    ('write', 'Write'),
    ('search', 'Search'),
    ('delete', 'Delete'),
]

class Log(ModelSQL, ModelView):
    'Log'
    __name__ = 'audit_trail.log'
    user = fields.Many2One('res.user', 'User')
    type = fields.Selection([
        (None, ''),
        ('model', 'Model'),
        ('report', 'Report'),
        ('wizard', 'Wizard'),
        ], 'Type')
    operation = fields.Selection(OPERATIONS, 'Operation')
    record_ids = fields.Char('Record IDS')
    request = fields.Text('Request')
    model = fields.Many2One('ir.model', 'Model')

    @classmethod
    def get_over_limit_by_user(cls, configuration):
        over_limit = []
        since = datetime.now() - timedelta(hours=24)
        for config_model in configuration.models:
            if not config_model.number or not config_model.model:
                continue
            domain = [
                ('model', '=', config_model.model.id),
                ('create_date', '>=', since),
                ]
            if config_model.operation:
                domain.append(('operation', '=', config_model.operation))

            counts = defaultdict(int)
            users = {}
            for log in cls.search(domain):
                user_id = log.user.id if log.user else None
                counts[user_id] += 1
                users[user_id] = log.user

            for user_id, count in counts.items():
                if count > config_model.number:
                    over_limit.append((users[user_id], config_model, count))
        return over_limit

    @classmethod
    def email_notify_cron(cls):
        pool = Pool()
        Configuration = pool.get('audit_trail.log.configuration')
        ElectronicMail = pool.get('electronic.mail')

        configuration = Configuration(1)
        if not configuration.notification_email:
            return

        over_limit = cls.get_over_limit_by_user(configuration)
        if not over_limit:
            return

        recipients = ElectronicMail.validate_emails(
            configuration.notification_email)
        if not recipients:
            return
        to_addrs = [e.strip() for e in recipients.split(',') if e.strip()]
        if not to_addrs:
            return

        from_addr = config.get('email', 'from')
        if not from_addr:
            return

        subject = gettext('audit_trail.msg_subject_audit_trail_notification')
        lines = [
            gettext('audit_trail.msg_body_audit_trail_notification'),
            '',
            ]
        for user, model, count in over_limit:
            user_name = user.rec_name if user else '-'
            operation = '-'
            if model.operation:
                operation = model.operation
            line = gettext(
                'audit_trail.msg_body_audit_trail_notification_line',
                user_name=user_name, model=model.model.model,
                logs=count, limit=model.number, operation=operation)
            lines.append(line)

        message = MIMEText('\n'.join(lines), _charset='utf-8')
        message['From'] = from_addr
        message['To'] = ', '.join(to_addrs)
        message['Date'] = formatdate(localtime=True)
        message['Message-Id'] = make_msgid()
        message['Subject'] = Header(subject, 'utf-8')
        sendmail(from_addr, to_addrs, message)


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Log Configuration'
    __name__ = 'audit_trail.log.configuration'

    models = fields.One2Many('audit_trail.log.configuration.model', 'configuration', 'Models')
    notification_email = fields.Char('Notification Email')
    _rules_cache = Cache('audit_trail_log_configuration.custom_dispatch')



class ConfigurationModel(ModelSQL, ModelView):
    'Log Configuration Model'
    __name__ = 'audit_trail.log.configuration.model'

    configuration = fields.Many2One('audit_trail.log.configuration', 'Configuration')
    model = fields.Many2One('ir.model', 'Model')
    operation = fields.Selection(OPERATIONS, 'Operation')
    form_field = fields.Char('Form Field',
        help='Field name used to detect when a form record is opened. '
        'Leave empty to log all requests, including list views.')
    number = fields.Integer('Number', required=True)

    @classmethod
    def write(cls, ids, vals):
        LogConfiguration = Pool().get('audit_trail.log.configuration')
        res = super(ConfigurationModel, cls).write(ids, vals)
        LogConfiguration._rules_cache.clear()
        return res

    @classmethod
    def create(cls, vals):
        LogConfiguration = Pool().get('audit_trail.log.configuration')
        res = super(ConfigurationModel, cls).create(vals)
        LogConfiguration._rules_cache.clear()
        return res

    @classmethod
    def delete(cls, records):
        LogConfiguration = Pool().get('audit_trail.log.configuration')
        res = super(ConfigurationModel, cls).delete(records)
        LogConfiguration._rules_cache.clear()
        return res

original_dispatch = trytond.protocols.dispatcher._dispatch


def _request_contains_field(data, field_name):
    if isinstance(data, dict):
        if field_name in data:
            return True
        return any(_request_contains_field(value, field_name)
            for value in data.values())
    if isinstance(data, (list, tuple, set)):
        return any(_request_contains_field(value, field_name) for value in data)
    return data == field_name


def custom_dispatch(request, pool, *args, **kwargs):
    result = original_dispatch(request, pool, *args, **kwargs)
    user = request.user_id
    database_name = getattr(pool, 'database_name', pool)
    with Transaction().start(database_name, user, readonly=False):
        _pool = Pool()
        LogConfiguration = _pool.get('audit_trail.log.configuration')
        model_operation_field = LogConfiguration._rules_cache.get('key')
        if not model_operation_field:
            log_config = LogConfiguration(1)
            model_operation_field = [
                (m.model.model, m.operation, m.form_field)
                for m in log_config.models if m.model]
            LogConfiguration._rules_cache.set('key', model_operation_field)
        request_data = getattr(request, 'json', None)
        if request_data is None:
            request_data = getattr(request, 'parsed_data', {})
        request_method = getattr(request, 'rpc_method', str(request))
        for model, operation, form_field in model_operation_field:
            event = 'model.%s.' % model
            if operation:
                event += operation
            if event not in request_method:
                continue
            if form_field and not _request_contains_field(request_data, form_field):
                continue
            Log = _pool.get('audit_trail.log')
            log = Log()
            log.user = user
            log.type = 'model'
            log.operation = operation
            log.request = str(request_data)
            params = request_data.get('params', []) if request_data else []
            log.record_ids = str(params[0]) if params else None
            log.model = _pool.get('ir.model').search([('model', '=', model)])[0]
            log.save()
    return result

if config.get('general', 'auditing') == 'True':
    trytond.protocols.dispatcher._dispatch = custom_dispatch


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.append(
            ('audit_trail.log|email_notify_cron',
            "Email Notify"),
            )
