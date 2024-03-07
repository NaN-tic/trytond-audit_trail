from trytond.model import ModelSQL, ModelView, fields, ModelSingleton
from trytond.pool import Pool, PoolMeta
import trytond.protocols.dispatcher
from trytond.transaction import Transaction
from datetime import datetime


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
    operation = fields.Selection([
        (None, ''),
        ('read', 'Read'),
        ('write', 'Write'),
        ('search', 'Search'),
        ('delete', 'Delete'),
        ], 'Operation')
    record_ids = fields.Char('Record IDS')
    request = fields.Text('Request')
    model = fields.Many2One('ir.model', 'Model')

    @classmethod
    def email_notify_cron(cls):
        ElectronicMail = Pool().get('electronic.mail')
        Mailbox = Pool().get('electronic.mail.mailbox')
        today = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0)
        logs = cls.search([('create_date', '>=', today)])
        user_logs_count = {}
        for log in logs:
            if (log.user, log.model, log.operation) in user_logs_count:
                user_logs_count[(log.user, log.model, log.operation)].append(log.record_ids)
            else:
                user_logs_count[(log.user, log.model, log.operation)] = [log.record_ids]
        ConfigurationLogs = Pool().get('audit_trail.log.configuration')
        configuration_logs = ConfigurationLogs(1)
        rules = configuration_logs.models
        for rule in rules:
            for user, model, operation in user_logs_count:
                if rule.model == model and rule.operation == operation:
                    if len(set(user_logs_count[(user, model, operation)])) >= rule.number:
                        electronic_mail = ElectronicMail()
                        electronic_mail.mailbox = Mailbox(1)
                        electronic_mail.from_ = 'jared.esparza@nan-tic.com'
                        electronic_mail.to = 'jared.esparza@nan-tic.com'
                        electronic_mail.subject = 'DETECTED ' + str(len(set(user_logs_count[(user, model, operation)]))) + ' ' + operation + ' ' + model.name + ' BY ' + user.name
                        electronic_mail.save()
                        ElectronicMail.send_email([electronic_mail])
                        print('DETECTED ' + str(len(set(user_logs_count[(user, model, operation)]))) + ' ' + operation + ' ' + model.name + ' BY ' + user.name)


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Log Configuration'
    __name__ = 'audit_trail.log.configuration'

    models = fields.One2Many('audit_trail.log.configuration.model', 'configuration', 'Models')
    notification_email = fields.Char('Notification Email')



class ConfigurationModel(ModelSQL, ModelView):
    'Log Configuration Model'
    __name__ = 'audit_trail.log.configuration.model'

    configuration = fields.Many2One('audit_trail.log.configuration', 'Configuration')
    model = fields.Many2One('ir.model', 'Model')
    operation = fields.Selection([
        (None, ''),
        ('read', 'Read'),
        ('write', 'Write'),
        ('search', 'Search'),
        ('delete', 'Delete'),
        ], 'Operation')
    number = fields.Integer('Number', required=True)

original_dispatch = trytond.protocols.dispatcher._dispatch

def custom_dispatch(request, pool, *args, **kwargs):
    result = original_dispatch(request, pool, *args, **kwargs)
    user = request.user_id
    with Transaction().start(pool, user, readonly=False) as transaction:
        _pool = Pool()
        LogConfiguration = _pool.get('audit_trail.log.configuration')
        log_config = LogConfiguration(1)
        model_operation = [(m.model.model, m.operation) for m in log_config.models]
        for model, operation in model_operation:
            event = 'model.' + model + '.' + operation
            if event in str(request):
                Log = _pool.get('audit_trail.log')
                log = Log()
                log.user = user
                log.type = 'model'
                log.operation = operation
                log.request = str(request.json)
                log.record_ids = str(request.json['params'][0])
                log.model = _pool.get('ir.model').search([('model', '=', model)])[0]
                log.save()
    return result
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