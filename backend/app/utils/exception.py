"""自定义异常层次。

业务异常按语义分层：
- NotFoundError: 资源不存在（推荐替代直接抛 ServiceException）
- ValidationError: 参数校验失败
- AuthError: 认证/授权失败
- InternalError: 内部错误
"""


class ServiceException(Exception):
    """业务异常基类。"""

    def __init__(self, code: int, message: str, data: object | None = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(self.message)


class NotFoundError(ServiceException):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在", data: object | None = None):
        super().__init__(code=404, message=message, data=data)


class ValidationError(ServiceException):
    """参数校验失败。"""

    def __init__(self, message: str = "参数错误", data: object | None = None):
        super().__init__(code=400, message=message, data=data)


class AuthError(ServiceException):
    """认证/授权失败。"""

    def __init__(self, message: str = "认证失败", data: object | None = None):
        super().__init__(code=401, message=message, data=data)


class InternalError(ServiceException):
    """内部错误。"""

    def __init__(self, message: str = "服务器内部错误", data: object | None = None):
        super().__init__(code=500, message=message, data=data)
