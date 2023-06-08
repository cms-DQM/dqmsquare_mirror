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
