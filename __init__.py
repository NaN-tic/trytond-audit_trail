# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import ir
from . import log


def register():
    Pool.register(
        ir.Session,
        ir.SessionEvent,
        log.Log,
        log.Configuration,
        log.ConfigurationModel,
        module='audit_trail', type_='model')
