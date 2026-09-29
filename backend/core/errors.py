from rest_framework.views import exception_handler


def handler(exc, context):
    return exception_handler(exc, context)
