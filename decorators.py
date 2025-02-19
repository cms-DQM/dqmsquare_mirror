import math
import flask
from collections.abc import Callable
from sqlalchemy import select, func as sql_func, sql
from sqlalchemy.engine.row import RowMapping

PAGINATION_DEFAULT_ITEMS_PER_PAGE = 10


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


def paginate(table) -> Callable:
    """
    Pagination decorator to wrap db calls.

    There is definitely something similar that works out of the
    box, but I didn't find it, especially given the structure
    of the current project.

    The function it wraps should return an sql.ClauseElement (e.g. select).
    It then counts the results of the query, and splits into pages.

    The page argument controls which page to return.
    The paginate argument, if given, can control whether the pagination
    is skipped or not.

    Since pagination can be skipped, this function returns, in that case,
    the result of running the query with the mappings, i.e., returns
    a RowMapping.

    If pagination is active, a dict is returned instead, with the
    actual data in the 'data' key, and two extra keys: 'page' and 'total_pages'.
    """

    # https://stackoverflow.com/a/5929165/6562491
    def paginate_decorator(func) -> Callable:
        def _paginate(*args, **kwargs) -> dict | RowMapping:
            db = args[0]  # Passed as the "self" argument, hence the first of the args
            # Then, we remove pagination-specific kwargs, so that we don't
            # pass unknown kwargs to the downstream wrapped method.
            items_per_page = kwargs.pop(
                "items_per_page", PAGINATION_DEFAULT_ITEMS_PER_PAGE
            )
            page = kwargs.pop("page", 1)
            order_by = kwargs.pop("order_by", None)
            paginate = kwargs.pop("paginate", True)

            # Run the actual function, expect an SQL query.
            query = func(*args, **kwargs)
            assert isinstance(query, sql.ClauseElement)

            with db.engine.connect() as cur:
                # Allow bypassing pagination if needed
                if not paginate:
                    return cur.execute(query).mappings().all()

                num_total_rows = cur.execute(
                    select(sql_func.count("*")).select_from(db.db_meta.tables[table])
                ).scalar()
            if num_total_rows < 1:
                return {
                    "data": [],
                    "page": 1,
                    "total_pages": 1,
                }

            num_total_pages = math.ceil(num_total_rows / items_per_page)
            if page < 0:
                page = 1
            elif page > num_total_pages:
                page = num_total_pages
            offset = (page - 1) * items_per_page
            # Limit and offset the query
            query = query.offset(offset).limit(items_per_page)
            if order_by:
                query = query.order_by(order_by)
            data = []
            with db.engine.connect() as cur:
                data = cur.execute(query).mappings().all()
            return {
                "data": data,
                "page": page,
                "total_pages": num_total_pages,
            }

        return _paginate

    return paginate_decorator
