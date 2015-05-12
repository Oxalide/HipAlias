import logging
import os
import asyncio
from bottle_ac import create_addon_app, RoomNotificationArgumentParser, validate_mention_name, HtmlNotification

log = logging.getLogger(__name__)
app = create_addon_app(__name__,
                       plugin_key="hc-alias",
                       addon_name="HC Alias",
                       from_name="Alias",
                       base_url="http://192.168.33.1:5000")

app.config['MONGO_URL'] = os.environ.get("MONGO_URL", None)
app.config['REDIS_URL'] = os.environ.get("REDISTOGO_URL", None)


def init():
    @asyncio.coroutine
    def _send_welcome(event):
        client = event['client']
        yield from client.send_notification(app.addon, text="HC Alias was added to this room")
        parser = _create_parser(client)
        parser.send_usage()
        yield from parser.task

    app.addon.register_event('install', _send_welcome)
app.add_hook('before_first_request', init)


# noinspection PyUnusedLocal
@app.route('/')
def capabilities(request, response):
    return {
        "links": {
            "self":         app.config.get("BASE_URL"),
            "homepage":     app.config.get("BASE_URL")
        },
        "key": app.config.get("PLUGIN_KEY"),
        "name": app.config.get("ADDON_NAME"),
        "description": "HipChat connect add-on that sends supports aliases for group mention",
        "vendor": {
            "name": "Atlassian Labs",
            "url": "https://atlassian.com"
        },
        "capabilities": {
            "installable": {
                "allowGlobal": False,
                "allowRoom": True,
                "callbackUrl": app.config.get("BASE_URL") + "/installable/"
            },
            "hipchatApiConsumer": {
                "scopes": [
                    "view_group",
                    "send_notification",
                    "admin_room"
                ],
                "fromName": app.config.get("FROM_NAME")
            },
            "webhook": [
                {
                    "url": app.config.get("BASE_URL") + "/alias",
                    "event": "room_message",
                    "pattern": "^/alias(\s|$).*"
                }
            ],
        }
    }


@app.route('/alias', method='POST')
@asyncio.coroutine
def alias(request, response):
    body = request.json
    client_id = body['oauth_client_id']
    client = yield from app.addon.load_client(client_id)
    parser = _create_parser(client)

    yield from parser.handle_webhook(body)
    response.status = 204


@app.route('/mention/<alias_name>', method='POST')
@asyncio.coroutine
def mention(request, response, alias_name):
    body = request.json
    client_id = body['oauth_client_id']
    client = yield from app.addon.load_client(client_id)

    existing = yield from find_alias(app.addon, client, alias_name)
    if existing:
        mentions = existing['mentions']

        txt = "said: {original} /cc {mentions}".format(
            original=body['item']["message"]["message"],
            mentions=" ".join(mentions))
        from_mention = body['item']['message']['from']['mention_name']
        yield from client.send_notification(app.addon, from_mention=from_mention, text=txt)
        response.status = 204
    else:
        log.error("Mention name '%s' not found for client %s" % (alias_name, client_id))
        response.status = 400


@asyncio.coroutine
def find_alias(addon, client, name):
    result = yield from _aliases_db(addon).find_one({
        "client_id": client.id,
        "group_id": client.group_id,
        "capabilities_url": client.capabilities_url,
        "alias": name
    })
    return result


@asyncio.coroutine
def find_all_alias(addon, client):
    results = yield from _aliases_db(addon).find({
        "client_id": client.id,
        "group_id": client.group_id,
        "capabilities_url": client.capabilities_url
    })
    return results


def create_webhook_pattern(alias):
    return "(?:(?:^[^/]|\/[^a]|\/a[^l]|\/ali[^a]|\/alia[^s]).*|^)%s(?:$| ).*" % alias


def _create_parser(client):

    @asyncio.coroutine
    def list_aliases(_):
        aliases = yield from find_all_alias(app.addon, client)
        if not aliases:
            return "No aliases registered. Register one with '/alias set @ALIAS @MENTION...'"
        else:
            return "Aliases registered: %s" % ", ".join([a['alias'] for a in aliases])

    @asyncio.coroutine
    def set_alias(args):
        try:
            for item in args.mentions + [args.alias]:
                validate_mention_name(item)
        except ValueError as e:
            return str(e)

        existing = yield from find_alias(app.addon, client, args.alias)
        if existing and 'webhook_url' in existing:
            yield from client.delete_webhook(app.addon, existing['webhook_url'])

        webhook_url = yield from client.post_webhook(app.addon,
                                                     url="%s/mention/%s" % (app.config.get("BASE_URL"), args.alias),
                                                     pattern=create_webhook_pattern(args.alias),
                                                     name="Alias %s" % args.alias)
        if webhook_url:
            aliases = _aliases_db(app.addon)
            spec = {
                "client_id": client.id,
                "group_id": client.group_id,
                "capabilities_url": client.capabilities_url,
                "alias": args.alias
            }
            data = {
                'mentions': args.mentions,
                'webhook_url': webhook_url
            }
            if existing:
                existing.update(data)
                yield from aliases.update(spec, existing)
            else:
                data.update(spec)
                yield from aliases.insert(data)
            return "Alias %s added" % args.alias
        else:
            return "Problem registering webhook"

    @asyncio.coroutine
    def remove_alias(args):
        try:
            validate_mention_name(args.alias)
        except ValueError as e:
            return str(e)

        existing = yield from find_alias(app.addon, client, args.alias)
        if existing and 'webhook_url' in existing:
            yield from client.delete_webhook(app.addon, existing['webhook_url'])
            yield from _aliases_db(app.addon).remove(existing)
            return "Alias %s removed" % args.alias
        else:
            return "Alias %s not found" % args.alias

    @asyncio.coroutine
    def show_alias(args):
        try:
            validate_mention_name(args.alias)
        except ValueError as e:
            return str(e)

        existing = yield from find_alias(app.addon, client, args.alias)
        if existing and 'webhook_url' in existing:
            mentions = ['&commat;%s' % x[1:] for x in existing['mentions']]
            return HtmlNotification("Alias %s is mapped to %s" % (args.alias, ", ".join(mentions)))
        else:
            return "Alias %s not found" % args.alias

    parser = RoomNotificationArgumentParser(app, "/alias", client)
    subparsers = parser.add_subparsers(help='Available commands')

    subparsers.add_parser('list', help='List existing aliases', handler=list_aliases)

    parser_set = subparsers.add_parser('set', help='Sets a group mention alias', handler=set_alias)
    parser_set.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')
    parser_set.add_argument('mentions', metavar='@MENTION', nargs='+', type=str,
                            help='The mention names, beginning with an "@"')

    parser_set = subparsers.add_parser('remove', help='Removes a group mention alias', handler=remove_alias)
    parser_set.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')

    parser_show = subparsers.add_parser('show', help='Shows the names for an existing alias', handler=show_alias)
    parser_show.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')

    return parser


def _aliases_db(addon):
    return addon.mongo_db.default_database['aliases']


if __name__ == "__main__":
    app.run(host="", reloader=True, debug=True)
