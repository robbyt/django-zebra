from django.http import HttpResponse
try:
    import json as simplejson
except:
    from django.utils import simplejson
    
from django.db.models import get_model
import stripe
from zebra.conf import options
from zebra.signals import *
from django.views.decorators.csrf import csrf_exempt

import logging
log = logging.getLogger("zebra.%s" % __name__)

stripe.api_key = options.STRIPE_SECRET

def _try_to_get_customer_from_customer_id(stripe_customer_id):
    if options.ZEBRA_CUSTOMER_MODEL:
        m = get_model(*options.ZEBRA_CUSTOMER_MODEL.split('.'))
        try:
            return m.objects.get(stripe_customer_id=stripe_customer_id)
        except:
            pass
    return None

@csrf_exempt
def webhooks(request):
    """
    Handles all known webhooks from stripe, and calls signals.
    Plug in as you need.
    """

    if request.method != "POST":
        return HttpResponse("Invalid Request.", status=400)

    json = simplejson.loads(request.POST["json"])
    
    try:
        # confirm the event came from stripe by requesting the event from their API
        event = stripe.Event.retrieve(json.get("id"))
    except stripe.InvalidRequestError:
        # if the event does not exist, return a 400 error
        return HttpResponse("Invalid Request.", status=400)

    if json["event"] == "recurring_payment_failed":
        zebra_webhook_recurring_payment_failed.send(sender=None, customer=_try_to_get_customer_from_customer_id(json["customer"]), full_json=json)

    elif json["event"] == "invoice_ready":
        zebra_webhook_invoice_ready.send(sender=None, customer=_try_to_get_customer_from_customer_id(json["customer"]), full_json=json)

    elif json["event"] == "recurring_payment_succeeded":
        zebra_webhook_recurring_payment_succeeded.send(sender=None, customer=_try_to_get_customer_from_customer_id(json["customer"]), full_json=json)

    elif json["event"] == "subscription_trial_ending":
        zebra_webhook_subscription_trial_ending.send(sender=None, customer=_try_to_get_customer_from_customer_id(json["customer"]), full_json=json)

    elif json["event"] == "subscription_final_payment_attempt_failed":
        zebra_webhook_subscription_final_payment_attempt_failed.send(sender=None, customer=_try_to_get_customer_from_customer_id(json["customer"]), full_json=json)

    elif json["event"] == "ping":
        zebra_webhook_subscription_ping_sent.send(sender=None)

    else:
        return HttpResponse(status=400)

    return HttpResponse(status=200)

@csrf_exempt
def webhooks_v2(request):
    """
    Handles all known webhooks from stripe, and calls signals.
    Plug in as you need.
    """
    if request.method != "POST":
        return HttpResponse("Invalid Request.", status=400)

    try:
        event_json = simplejson.loads(request.body)
    except AttributeError:
        # Backwords compatibility
        # Prior to Django 1.4, request.body was named request.raw_post_data
        event_json = simplejson.loads(request.raw_post_data)
    event_key = event_json['type'].replace('.', '_')

    try:
        # confirm the event came from stripe by requesting the event from their API
        event = stripe.Event.retrieve(event_json.get("id"))
    except stripe.InvalidRequestError:
        # if the event does not exist, return a 400 error
        return HttpResponse("Invalid Request.", status=400)
        
    if event_key in WEBHOOK_MAP:
        WEBHOOK_MAP[event_key].send(sender=None, full_json=event_json)

    return HttpResponse(status=200)
