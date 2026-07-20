"""自定义异常。"""


class ServiceException(Exception):
    """业务异常，包含错误码和错误信息。"""

    def __init__(self, code: int, message: str, data: object | None = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(self.message)
