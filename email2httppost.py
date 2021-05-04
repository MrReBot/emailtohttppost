# Command to deploy
# gcloud app deploy --promote --stop-previous-version
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import mail
import os
from poster.encode import MultipartParam, multipart_encode
from google.appengine.ext import db
import logging
from google.appengine.ext import ereporter
import json

ereporter.register_logger()

class Email(db.Model):
    created = db.DateTimeProperty(auto_now_add=True)
    sender = db.StringProperty(multiline=True)
    to = db.StringProperty(multiline=True)
    cc = db.StringProperty(multiline=True)
    bcc = db.StringProperty(multiline=True)
    message_id = db.StringProperty(multiline=True)
    subject = db.TextProperty()
    body = db.TextProperty()
    html_body = db.TextProperty()

class PostToUrl(InboundMailHandler):
    def recipients_as_string(self, mail_message_field):
        if not mail_message_field:
            return None
        return mail_message_field if isinstance(mail_message_field, basestring) else ','.join(mail_message_field)

    def log_complete_message(self, complete_message):
        if complete_message:
            for item in complete_message.items():
                logging.error("%s=%s" % (item[0], item[1]))

    def get_body_parts(self, mail_message, mime_type):
        body_parts = []
        for _, payload in mail_message.bodies(mime_type):
            # FIXME(andi): Remove this when issue 2383 is fixed.
            # 8bit encoding results in UnknownEncodingError, see
            # http://code.google.com/p/googleappengine/issues/detail?id=2383
            # As a workaround we try to decode the payload ourselves.
            if payload.encoding == '8bit' and payload.charset:
                body_parts.append(payload.payload.decode(payload.charset))
            else:
                body_parts.append(payload.decode())
        return body_parts

    def receive(self, mail_message):
        try:
            complete_message = mail_message.original

            sender = mail_message.sender
            to = self.recipients_as_string(mail_message.to) if hasattr(mail_message, 'to') else None
            cc = self.recipients_as_string(mail_message.cc) if hasattr(mail_message, 'cc') else None
            bcc = self.recipients_as_string(complete_message.bcc) if hasattr(complete_message, 'bcc') else None
            message_id = complete_message.get('message-id', None)

            subject = mail_message.subject if hasattr(mail_message, 'subject') else ''

            body = ''.join(self.get_body_parts(mail_message, 'text/plain'))


            params = {'sender': sender,
                      'to': to,
                      'subject': subject,
                      'body': body.strip().rstrip(),
            }

        # Should Probably Fix This Eventually
        #    if hasattr(mail_message, 'attachments') and mail_message.attachments:
                # Only process the first
        #        name, content = mail_message.attachments[0]
        #        params.append(MultipartParam(
        #            'picture',
        #            filename=name,
        #            value=content.decode()))

            #payloadgen, headers = multipart_encode(params)
            #payload = str().join(payloadgen)
            headers = { 'Content-Type': "application/json" }
            payload = json.JSONEncoder().encode(params)

            result = urlfetch.fetch(
                url=os.environ.get('DESTINATION_URL'),
                payload=payload,
                method=urlfetch.POST,
                headers=headers,
                deadline=60)

            self.response.out.write('HTTP RESPONSE STATUS: %s<br />' % result.status_code)
            self.response.out.write(result.content)
        except:
            logging.exception('Other unexpected error, logging')
            self.log_complete_message(complete_message)


    def persist(self, message_id, sender, to, cc, bcc, subject, body, html_body):
        email = Email(message_id=message_id, sender=sender, to=to, cc=cc, bcc=bcc, subject=subject, body=body, html_body=html_body)
        email.put()


app = webapp.WSGIApplication([PostToUrl.mapping()], debug=True)
