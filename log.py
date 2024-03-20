from trytond.model import ModelSQL, ModelView, fields, ModelSingleton
from trytond.pool import Pool, PoolMeta
import trytond.protocols.dispatcher
from trytond.transaction import Transaction
from trytond.config import config
from trytond.cache import Cache
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
    operation = fields.Selection([
        (None, ''),
        ('read', 'Read'),
        ('write', 'Write'),
        ('search', 'Search'),
        ('delete', 'Delete'),
        ], 'Operation')
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
    def delete(cls, ids):
        LogConfiguration = Pool().get('audit_trail.log.configuration')
        res = super(ConfigurationModel, cls).delete(ids)
        LogConfiguration._rules_cache.clear()
        return res

original_dispatch = trytond.protocols.dispatcher._dispatch

def custom_dispatch(request, pool, *args, **kwargs):
    result = original_dispatch(request, pool, *args, **kwargs)
    user = request.user_id
    with Transaction().start(pool, user, readonly=False) as transaction:
        _pool = Pool()
        LogConfiguration = _pool.get('audit_trail.log.configuration')
        model_operation = LogConfiguration._rules_cache.get('key')
        if not model_operation:
            print('Cache miss')
            log_config = LogConfiguration(1)
            model_operation = [(m.model.model, m.operation) for m in log_config.models]
            LogConfiguration._rules_cache.set('key', model_operation)
        else:
            print('Cache hit')
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