class BusinessError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def invalid(message: str) -> BusinessError:
    return BusinessError(400, 'invalid_request', message)


def missing(message: str) -> BusinessError:
    return BusinessError(404, 'not_found', message)


def conflict(message: str) -> BusinessError:
    return BusinessError(409, 'conflict', message)


def name(value, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or not value.isprintable():
        raise invalid(f'{field} must be a nonempty printable identifier')
    return value


def positive(value, field: str) -> int:
    if type(value) is not int or value < 1:
        raise invalid(f'{field} must be a positive integer')
    return value
