from functools import wraps
import flask


def check_login(
    username: str, password: str, cr_usernames: dict[str:str], cookie=False
):
    if not username:
        return False
    if username not in cr_usernames:
        return False
    if cookie:
        return True
    if password != cr_usernames[username]:
        return False
    return True


def check_auth(redirect: bool = True, cr_usernames: dict = {}):
    """
    Route decorator which can redirect users to login.

    If redirect is True, if the login attempt is unsuccessful,
    the user will be redirected to the home page. Else, a plaintext
    message is returned.
    """

    def decorator(fn):
        def wrapper(*args, **kwargs):
            # Make a copy of the redirect_url arg.
            # We cannot modify the one passed by the decorator, as
            # it would make it immediately a local var.
            # https://stackoverflow.com/questions/4962932/access-decorator-arguments-inside-the-decorators-wrapper-function

            username = flask.request.cookies.get("dqmsquare-mirror-cr-account")
            if not check_login(username, None, cr_usernames, True):
                if redirect:
                    return flask.redirect(flask.url_for("login"))
                else:
                    return "Please login ..."
            else:
                return fn(*args, **kwargs)

        # https://stackoverflow.com/questions/17256602/assertionerror-view-function-mapping-is-overwriting-an-existing-endpoint-functi
        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator
