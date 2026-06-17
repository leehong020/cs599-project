class MailflowError(Exception):
    """业务异常基类。

    后续服务层可以继承它区分可展示给用户的业务错误和系统内部错误。
    """
