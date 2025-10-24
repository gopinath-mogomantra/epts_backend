from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns all validation errors at once,
    formatted as key: message (cleaned for Postman & frontend).
    """
    response = exception_handler(exc, context)

    if response is not None and isinstance(response.data, dict):
        formatted_errors = {}
        for field, messages in response.data.items():
            if isinstance(messages, (list, tuple)):
                formatted_errors[field] = messages[0]
            else:
                formatted_errors[field] = str(messages)
        response.data = {"errors": formatted_errors}

    return response
