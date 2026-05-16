# Copyright 2018-22 ForgeFlow <http://www.forgeflow.com>
# Copyright 2018 Odoo, S.A.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields

from odoo.addons.mail.models.mail_activity import MailActivity


def pre_init_hook(env):
    """The objective of this hook is to default to false all values of field
    'done' of mail.activity
    """
    cr = env.cr
    cr.execute(
        """SELECT column_name
    FROM information_schema.columns
    WHERE table_name='mail_activity' AND
    column_name='done'"""
    )
    if not cr.fetchone():
        cr.execute(
            """
            ALTER TABLE mail_activity ADD COLUMN done boolean;
            """
        )

    cr.execute(
        """
        UPDATE mail_activity
        SET done = False
        """
    )


def post_load_hook():
    def _new_action_done(self, feedback=False, attachment_ids=None):
        """Overwritten method"""
        if "done" not in self._fields:
            return self._action_done_original(
                feedback=feedback, attachment_ids=attachment_ids
            )
        # marking as 'done'
        messages = self.env["mail.message"]
        next_activities_values = []
        for activity in self:
            # extract value to generate next activities
            if activity.chaining_type == "trigger":
                vals = activity.with_context(
                    activity_previous_deadline=activity.date_deadline
                )._prepare_next_activity_values()
                next_activities_values.append(vals)

            # post message on activity, before deleting it
            record = self.env[activity.res_model].browse(activity.res_id)
            activity.done = True
            activity.active = False
            activity.date_done = fields.Date.today()
            record.message_post_with_source(
                "mail.message_activity_done",
                attachment_ids=attachment_ids,
                author_id=self.env.user.partner_id.id,
                render_values={
                    "activity": activity,
                    "feedback": feedback,
                    "display_assignee": activity.user_id != self.env.user,
                },
                mail_activity_type_id=activity.activity_type_id.id,
                subtype_xmlid="mail.mt_activities",
            )
            messages |= record.message_ids[0]

        next_activities = self.env["mail.activity"].create(next_activities_values)

        return messages, next_activities

    if not hasattr(MailActivity, "_action_done_original"):
        MailActivity._action_done_original = MailActivity._action_done
        MailActivity._action_done = _new_action_done


def uninstall_hook(env):
    """The objective of this hook is to remove all activities that are done
    upon module uninstall
    """
    env.cr.execute(
        """
        DELETE FROM mail_activity
        WHERE done=True
        """
    )
