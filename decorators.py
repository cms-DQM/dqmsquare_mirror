import math
import flask
import sqlalchemy


def check_login(
    username: str, password: str, cr_usernames: dict[str, str], cookie=False
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


def paginate(table):
    # TODO: Make sure it works
    # https://stackoverflow.com/a/5929165/6562491
    def paginate_decorator(func):
        def _paginate(*args, **kwargs):
            db = args[0]  # Passed as the "self" argument, hence the first of the args
            # Remove pagination-specific kwargs, so that we don't
            # pass unknown kwargs to the downstream wrapped method.
            items_per_page = kwargs.pop("items_per_page", 1)
            page = kwargs.pop("page", 1)
            query = func(*args, **kwargs)
            assert isinstance(query, sqlalchemy.sql.ClauseElement)
            order_by = kwargs.pop("order_by", None)
            cur = db.engine.connect()
            num_total_reports = cur.execute(
                sqlalchemy.text(f"SELECT COUNT (*) FROM {table};")
            ).first()[0]

            if num_total_reports <= 1:
                return {
                    "data": [],
                    "page": 1,
                    "total_pages": 1,
                }

            num_total_pages = math.ceil(num_total_reports / items_per_page)
            if page < 0:
                page = 1
            elif page > num_total_pages:
                page = num_total_pages
            offset = (page - 1) * items_per_page
            # Limit and offset the query
            query = query.offset(offset).limit(items_per_page)
            if order_by:
                query = query.order_by(order_by)
            return {
                "data": cur.execute(query),
                "page": 1,
                "total_pages": 1,
            }

        return _paginate

    return paginate_decorator
