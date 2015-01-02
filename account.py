# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import tools
import openerp.addons.decimal_precision as dp
from openerp.osv import fields,osv

class account_invoice_report(osv.osv):
    _name = "account.invoice.report"
    _inherit = "account.invoice.report"


    _columns = {
        'supplier_id': fields.many2one('res.partner', 'Supplier', readonly=True),
        'subrubro_id': fields.many2one('product.subrubro', 'SubRubro', readonly=True),
    }
    _order = 'date desc'


    def _select(self):
        select_str = """
            SELECT sub.id, sub.date, sub.product_id, sub.supplier_id,sub.subrubro_id, sub.section_id, sub.partner_id, sub.country_id,
                sub.payment_term, sub.period_id, sub.uom_name, sub.currency_id, sub.journal_id,
                sub.fiscal_position, sub.user_id, sub.company_id, sub.nbr, sub.type, sub.state,
                sub.categ_id, sub.date_due, sub.account_id, sub.account_line_id, sub.partner_bank_id,
                sub.product_qty, sub.price_total / cr.rate as price_total, sub.price_average /cr.rate as price_average,
                cr.rate as currency_rate, sub.residual / cr.rate as residual, sub.commercial_partner_id as commercial_partner_id
        """
        return select_str

    def _sub_select(self):
        select_str = """
                SELECT min(ail.id) AS id,
                    ai.date_invoice AS date,
                    ail.product_id, pr.supplier_id, pr.subrubro_id, ai.section_id, ai.partner_id, ai.payment_term, ai.period_id,
                    CASE
                     WHEN u.uom_type::text <> 'reference'::text
                        THEN ( SELECT product_uom.name
                               FROM product_uom
                               WHERE product_uom.uom_type::text = 'reference'::text
                                AND product_uom.active
                                AND product_uom.category_id = u.category_id LIMIT 1)
                        ELSE u.name
                    END AS uom_name,
                    ai.currency_id, ai.journal_id, ai.fiscal_position, ai.user_id, ai.company_id,
                    count(ail.*) AS nbr,
                    ai.type, ai.state, pt.categ_id, ai.date_due, ai.account_id, ail.account_id AS account_line_id,
                    ai.partner_bank_id,
                    SUM(CASE
                         WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                            THEN (- ail.quantity) / u.factor
                            ELSE ail.quantity / u.factor
                        END) AS product_qty,
                    SUM(CASE
                         WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                            THEN - ail.price_subtotal
                            ELSE ail.price_subtotal
                        END) AS price_total,
                    CASE
                     WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                        THEN SUM(- ail.price_subtotal)
                        ELSE SUM(ail.price_subtotal)
                    END / CASE
                           WHEN SUM(ail.quantity / u.factor) <> 0::numeric
                               THEN CASE
                                     WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                                        THEN SUM((- ail.quantity) / u.factor)
                                        ELSE SUM(ail.quantity / u.factor)
                                    END
                               ELSE 1::numeric
                          END AS price_average,
                    CASE
                     WHEN ai.type::text = ANY (ARRAY['out_refund'::character varying::text, 'in_invoice'::character varying::text])
                        THEN - ai.residual
                        ELSE ai.residual
                    END / CASE
                           WHEN (( SELECT count(l.id) AS count
                                   FROM account_invoice_line l
                                   LEFT JOIN account_invoice a ON a.id = l.invoice_id
                                   WHERE a.id = ai.id)) <> 0
                               THEN ( SELECT count(l.id) AS count
                                      FROM account_invoice_line l
                                      LEFT JOIN account_invoice a ON a.id = l.invoice_id
                                      WHERE a.id = ai.id)
                               ELSE 1::bigint
                          END::numeric AS residual,
                    ai.commercial_partner_id as commercial_partner_id,
                    partner.country_id
        """
        return select_str

    def _from(self):
        from_str = """
                FROM account_invoice_line ail
                JOIN account_invoice ai ON ai.id = ail.invoice_id
                JOIN res_partner partner ON ai.commercial_partner_id = partner.id
                LEFT JOIN product_product pr ON pr.id = ail.product_id
                left JOIN product_template pt ON pt.id = pr.product_tmpl_id
                LEFT JOIN product_uom u ON u.id = ail.uos_id
        """
        return from_str

    def _group_by(self):
        group_by_str = """
                GROUP BY ail.product_id, ai.date_invoice, ai.id,
                    pr.supplier_id,pr.subrubro_id,ai.section_id,ai.partner_id, ai.payment_term, ai.period_id, u.name, ai.currency_id, ai.journal_id,
                    ai.fiscal_position, ai.user_id, ai.company_id, ai.type, ai.state, pt.categ_id,
                    ai.date_due, ai.account_id, ail.account_id, ai.partner_bank_id, ai.residual,
                    ai.amount_total, u.uom_type, u.category_id, ai.commercial_partner_id, partner.country_id
        """
        return group_by_str

    def init(self, cr):
        # self._table = account_invoice_report
        tools.drop_view_if_exists(cr, self._table)
        cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            FROM (
                %s %s %s
            ) AS sub
            JOIN res_currency_rate cr ON (cr.currency_id = sub.currency_id)
            WHERE
                cr.id IN (SELECT id
                          FROM res_currency_rate cr2
                          WHERE (cr2.currency_id = sub.currency_id)
                              AND ((sub.date IS NOT NULL AND cr2.name <= sub.date)
                                    OR (sub.date IS NULL AND cr2.name <= NOW()))
                          ORDER BY name DESC LIMIT 1)
        )""" % (
                    self._table,
                    self._select(), self._sub_select(), self._from(), self._group_by()))


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
