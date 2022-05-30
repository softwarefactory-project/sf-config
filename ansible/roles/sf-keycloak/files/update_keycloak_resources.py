#!/usr/bin/python3


import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
import time


def get_with_retries(*args, **kwargs):
    retries = 10
    delay = 2

    i = 0
    while i < retries:
        result = requests.get(*args, **kwargs)
        if result.status_code < 400:
            return result
        time.sleep(delay)
        i += 1
    result.raise_for_status()


def get_managesf_groups():
    resources = get_with_retries(MANAGESF_RESOURCES_URL).json()
    return resources['resources'].get('groups')


def get_admin_token():
    endpoint = "/realms/master/protocol/openid-connect/token"
    token_url = KC_BASE_ADMIN_URL + endpoint
    payload = {
        'username': 'admin',
        'password': KC_PASSWORD,
        'client_id': 'admin-cli',
        'grant_type': 'password',
    }
    token_response = requests.post(
        token_url,
        data=payload
    ).json()
    return token_response.get('access_token')


def _kc_get(url):
    headers = {
        'Authorization': 'Bearer ' + get_admin_token()
    }
    # TODO figure out pagination support/need
    return requests.get(url, headers=headers).json()


def _kc_delete(url):
    headers = {
        'Authorization': 'Bearer ' + get_admin_token()
    }
    return requests.delete(url, headers=headers)


def _kc_post(url, *args, **kwargs):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + get_admin_token()
    }
    return requests.post(url, headers=headers, *args, **kwargs)


def _kc_put(url, *args, **kwargs):
    headers = {
        'Authorization': 'Bearer ' + get_admin_token()
    }
    return requests.put(url, headers=headers, *args, **kwargs)


def get_kc_groups():
    groups_url = KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM + "/groups"
    return _kc_get(groups_url)


def get_kc_users():
    users_url = KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM + "/users"
    return _kc_get(users_url)


def get_kc_group_members(group_id):
    members_url = (KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM
                   + "/groups/" + group_id + "/members")
    return _kc_get(members_url)


def add_user_to_group(user_id, group_id):
    add_url = (KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM
               + "/users/" + user_id + "/groups/" + group_id)
    response = _kc_put(add_url)
    if response.status_code < 400:
        return True
    error_dict = {
        'url': add_url,
        'status_code': response.status_code,
        'headers': response.headers,
        'text': response.text}
    raise Exception(
        'Error adding %s to %s: %r' % (user_id, group_id, error_dict)
    )


def remove_user_from_group(user_id, group_id):
    del_url = (KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM
               + "/users/" + user_id + "/groups/" + group_id)
    response = _kc_delete(del_url)
    if response.status_code == 204:
        return True
    error_dict = {
        'url': del_url,
        'status_code': response.status_code,
        'headers': response.headers,
        'text': response.text}
    raise Exception(
        'Error removing %s from %s: %r' % (user_id, group_id, error_dict)
    )


def create_kc_group(name):
    create_url = KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM + "/groups"
    response = _kc_post(create_url, json={'name': name})
    response.raise_for_status()
    if 'Location' in response.headers:
        return _kc_get(response.headers['Location'])
    error_dict = {
       'url': create_url,
       'status_code': response.status_code,
       'headers': response.headers,
       'text': response.text}
    raise Exception(
        'No new resource returned when creating %s: %r' % (name, error_dict)
    )


def delete_kc_group(group_id):
    del_url = (KC_BASE_ADMIN_URL + "/admin/realms/" + SF_REALM
               + "/groups/" + group_id)
    response = _kc_delete(del_url)
    if response.status_code == 204:
        return True
    error_dict = {
        'url': del_url,
        'status_code': response.status_code,
        'headers': response.headers,
        'text': response.text}
    raise Exception('Error deleting %s: %r' % (group_id, error_dict))


def update_groups_dry(sf_groups, current_kc_groups):
    list_new = [sf_groups[x]['name'] for x in sf_groups]
    list_current = [x['name'] for x in current_kc_groups]

    groups_by_name = dict([(x['name'], x['id']) for x in current_kc_groups])

    groups_to_delete = list(set(list_current) - set(list_new))
    groups_to_create = list(set(list_new) - set(list_current))

    ids_to_delete = [groups_by_name[g] for g in groups_to_delete]

    return ids_to_delete, groups_to_create

# TODO change @asyncio.coroutine to async when mockbuild
# module is update to python >2.7
# remove loop.run_until_complete and uncommante lines


@asyncio.coroutine
def update_groups(ids_to_delete, groups_to_create):
    with ThreadPoolExecutor(max_workers=5) as executor_del:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor_del,
                delete_kc_group,
                g
            ) for g in ids_to_delete
        ]
        for response in asyncio.gather(*tasks):
            pass

    with ThreadPoolExecutor(max_workers=5) as executor_create:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor_create,
                create_kc_group,
                g
            ) for g in groups_to_create
        ]
        for response in asyncio.gather(*tasks):
            pass


def update_group_memberships_dry(sf_group, kc_group_id, userids_by_email):
    new_members = sf_group['members']
    current_members = get_kc_group_members(kc_group_id)
    current_members_emails = [x['email'] for x in current_members]

    members_to_remove = list(set(current_members_emails) - set(new_members))
    members_to_add = list(set(new_members) - set(current_members_emails))

    ids_to_remove = [userids_by_email[u] for u in members_to_remove]
    ids_to_add = [userids_by_email[u] for u in members_to_add]

    return ids_to_remove, ids_to_add

# TODO change @asyncio.coroutine to async when mockbuild
# module is update to python >2.7
# remove loop.run_until_complete and uncommante lines


@asyncio.coroutine
def update_group_memberships(kc_group_id, ids_to_remove, ids_to_add):
    with ThreadPoolExecutor(max_workers=5) as executor_del:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor_del,
                remove_user_from_group,
                *(user_id, kc_group_id)
            ) for user_id in ids_to_remove
        ]
        for response in asyncio.gather(*tasks):
            pass

    with ThreadPoolExecutor(max_workers=5) as executor_add:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor_add,
                add_user_to_group,
                *(user_id, kc_group_id)
            ) for user_id in ids_to_add
        ]
        for response in asyncio.gather(*tasks):
            pass


def main(args):
    loop = asyncio.get_event_loop()

    sf_groups = get_managesf_groups()
    current_kc_groups = get_kc_groups()
    kc_users = get_kc_users()
    userids_by_email = dict([(x['email'], x['id']) for x in kc_users])

    ids_to_delete, groups_to_create = update_groups_dry(
        sf_groups, current_kc_groups
    )
    print("These groups will be deleted: %s" % ' '.join(ids_to_delete))
    print("These groups will be created: %s" % ' '.join(groups_to_create))
    if not args.dry_run:
        future = asyncio.ensure_future(
            update_groups(ids_to_delete, groups_to_create)
        )
        loop.run_until_complete(future)
    # refresh groups
    current_kc_groups = get_kc_groups()
    futures = {}
    for group in current_kc_groups:
        sf_group = sf_groups[group['name']]
        kc_group_id = group['id']
        ids_to_remove, ids_to_add = update_group_memberships_dry(
            sf_group, kc_group_id, userids_by_email
        )
        if len(ids_to_remove) > 0:
            print("Removing from %s: %s" % (kc_group_id,
                                            ' '.join(ids_to_remove)))
        if len(ids_to_add) > 0:
            print("Adding %s: %s" % (kc_group_id,
                                     ' '.join(ids_to_add)))
        if not args.dry_run:
            futures[kc_group_id] = asyncio.ensure_future(
                update_group_memberships(kc_group_id,
                                         ids_to_remove,
                                         ids_to_add)
            )
            loop.run_until_complete(futures[kc_group_id])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KC groups updating utility")
    parser.add_argument('--dry-run', action='store_true',
                        help='Do not apply modifications')
    parser.add_argument('--resources-url',
                        help='SF resources url')
    parser.add_argument('--keycloak-url',
                        help='Keycloak url')
    parser.add_argument('--admin-password',
                        help='Admin password')
    parser.add_argument('--realm',
                        help='Keycloak Realm')
    args = parser.parse_args()

    MANAGESF_RESOURCES_URL = args.resources_url
    KC_BASE_ADMIN_URL = args.keycloak_url
    KC_PASSWORD = args.admin_password
    SF_REALM = args.realm

    main(args)
